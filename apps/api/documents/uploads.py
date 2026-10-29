import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .models import Document, DocumentVersion, OriginalArtifact, ProcessingJob
from .policies import DocumentCapability, authorize_document
from .storage import ArtifactStorageError, ArtifactTooLarge, PrivateArtifactStore


class InvalidUpload(Exception):
    pass


class UploadCompensationError(Exception):
    pass


class UploadFailed(Exception):
    pass


@dataclass(frozen=True)
class UploadResult:
    document: Document
    version: DocumentVersion
    job: ProcessingJob


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_DECLARED_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}
_DETECTED_TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}


def _fresh_upload_actor(actor):
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        record_denied_event_best_effort(
            action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED,
            actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=None,
        )
        raise PermissionDenied("Document upload is not permitted")
    current = User.objects.filter(pk=actor_id).first()
    if not authorize_document(current, DocumentCapability.CREATE).allowed:
        record_denied_event_best_effort(
            action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED,
            actor_user_id=actor_id,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=None,
        )
        raise PermissionDenied("Document upload is not permitted")
    return current


def _safe_display_filename(name):
    if not isinstance(name, str):
        raise InvalidUpload
    normalized = name.replace("\\", "/").split("/")[-1].strip()
    if not normalized or len(normalized) > 255 or _CONTROL_CHARACTERS.search(normalized):
        raise InvalidUpload
    return normalized


def _validate_pdf(path):
    try:
        with path.open("rb") as source:
            if source.read(5) != b"%PDF-":
                raise InvalidUpload
            source.seek(0)
            reader = PdfReader(source, strict=True)
            if reader.is_encrypted:
                raise InvalidUpload
            page_count = len(reader.pages)
            root = reader.trailer.get("/Root")
            if root:
                root = root.get_object()
                if any(key in root for key in ("/OpenAction", "/AA")):
                    raise InvalidUpload
                names = root.get("/Names")
                if names:
                    names = names.get_object()
                    if any(key in names for key in ("/JavaScript", "/EmbeddedFiles")):
                        raise InvalidUpload
            for page in reader.pages:
                if any(key in page for key in ("/AA", "/OpenAction")):
                    raise InvalidUpload
                annotations = page.get("/Annots") or ()
                for annotation in annotations:
                    annotation = annotation.get_object()
                    if annotation.get("/Subtype") in {"/FileAttachment", "/RichMedia"}:
                        raise InvalidUpload
                    action = annotation.get("/A")
                    if action and action.get_object().get("/S") in {"/JavaScript", "/Launch", "/SubmitForm", "/ImportData"}:
                        raise InvalidUpload
    except InvalidUpload:
        raise
    except Exception as exc:
        raise InvalidUpload from exc
    if page_count < 1 or page_count > settings.DOCUMENT_MAX_PDF_PAGES:
        raise InvalidUpload


def _validate_text(path):
    try:
        content = path.read_bytes().decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        raise InvalidUpload from exc
    if not content or "\x00" in content:
        raise InvalidUpload


def _validate_artifact(*, store, stored, filename, declared_type):
    extension = Path(filename).suffix.lower()
    if extension not in _DECLARED_TYPES or declared_type not in _DECLARED_TYPES[extension]:
        raise InvalidUpload
    path = store.resolve(stored.storage_key)
    if extension == ".pdf":
        _validate_pdf(path)
    else:
        _validate_text(path)
    return _DETECTED_TYPES[extension]


def _compensate(store, storage_key):
    try:
        store.delete(storage_key)
        return
    except Exception:
        try:
            store.quarantine(storage_key)
            return
        except Exception as exc:
            raise UploadCompensationError("Private upload compensation requires reconciliation") from exc


def create_document_upload(*, actor, title, description, uploaded_file, store=None):
    actor = _fresh_upload_actor(actor)
    if not uploaded_file or getattr(uploaded_file, "size", 0) > settings.DOCUMENT_MAX_FILE_BYTES:
        raise InvalidUpload
    filename = _safe_display_filename(getattr(uploaded_file, "name", None))
    store = store or PrivateArtifactStore()
    stored = None
    try:
        try:
            stored = store.write_upload(uploaded_file)
            detected_type = _validate_artifact(
                store=store,
                stored=stored,
                filename=filename,
                declared_type=(getattr(uploaded_file, "content_type", "") or "").lower(),
            )
        except ArtifactTooLarge as exc:
            raise InvalidUpload from exc
        except ArtifactStorageError as exc:
            raise UploadFailed from exc
        except InvalidUpload:
            raise

        with transaction.atomic():
            actor = _fresh_upload_actor(actor)
            document = Document(
                owner=actor,
                title=title.strip() if isinstance(title, str) else title,
                description=description.strip() if isinstance(description, str) else description,
            )
            document.full_clean()
            document.save(force_insert=True)
            version = DocumentVersion.objects.create(
                document=document,
                sequence=1,
                processing_state=DocumentVersion.ProcessingState.QUEUED,
                created_by_user_id=actor.pk,
            )
            OriginalArtifact.objects.create(
                document_version=version,
                storage_key=stored.storage_key,
                original_filename=filename,
                sha256_digest=stored.sha256_digest,
                byte_length=stored.byte_length,
                detected_media_type=detected_type,
            )
            job = ProcessingJob.objects.create(document_version=version, available_at=timezone.now())
            document.candidate_version = version
            document.save(update_fields=("candidate_version", "updated_at"))
            record_critical_event(
                action=SecurityAuditEvent.Action.DOCUMENT_CREATED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
                target_id=str(document.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            record_critical_event(
                action=SecurityAuditEvent.Action.DOCUMENT_UPLOAD_CREATED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
                target_id=str(document.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            return UploadResult(document=document, version=version, job=job)
    except Exception:
        if stored is not None:
            _compensate(store, stored.storage_key)
        raise
