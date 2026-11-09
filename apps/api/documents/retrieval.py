import hashlib
import io
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F

from accounts.models import User

from .artifact_coordination import lock_artifact_publication, reject_quarantined_key
from .models import (
    Document,
    DocumentRetrievalChange,
    DocumentVersion,
    ExtractedTextArtifact,
    OriginalArtifact,
)
from .policies import DocumentCapability, authorize_document
from .storage import ArtifactStorageError, PrivateArtifactStore


MAX_INDEX_PAGE = 256
MAX_AUTHORIZATION_CANDIDATES = 40


class RetrievalBoundaryError(Exception):
    """Controlled fail-closed error with no private storage details."""


@dataclass(frozen=True)
class IndexableVersion:
    document_id: uuid.UUID
    version_id: uuid.UUID
    digest: str
    document_updated_at: object


@dataclass(frozen=True)
class IndexableVersionPage:
    items: tuple[IndexableVersion, ...]
    next_cursor: uuid.UUID | None
    complete: bool


@dataclass(frozen=True)
class VerifiedExtractedText:
    document_id: uuid.UUID
    version_id: uuid.UUID
    digest: str
    character_count: int
    stream: io.StringIO


@dataclass(frozen=True)
class RetrievalCandidate:
    document_id: uuid.UUID
    version_id: uuid.UUID
    digest: str


@dataclass(frozen=True)
class AuthorizedRetrievalCandidate:
    document_id: uuid.UUID
    version_id: uuid.UUID
    digest: str
    title: str
    version_sequence: int


def queue_retrieval_change(*, document, version=None, reason):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Retrieval changes must be recorded transactionally")
    return DocumentRetrievalChange.objects.create(
        document=document,
        document_version_id=getattr(version, "pk", version),
        reason=str(reason)[:32],
    )


def list_indexable_versions(*, cursor=None, limit=MAX_INDEX_PAGE):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_INDEX_PAGE:
        raise ValueError("Index page limit is invalid")
    queryset = (
        DocumentVersion.objects
        .filter(
            document__visibility=Document.Visibility.ACTIVE,
            document__current_version_id=F("id"),
            processing_state=DocumentVersion.ProcessingState.READY,
            extracted_text_artifact__isnull=False,
        )
        .select_related("document", "extracted_text_artifact")
        .order_by("id")
    )
    if cursor is not None:
        try:
            cursor = uuid.UUID(str(cursor))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Index cursor is invalid") from exc
        queryset = queryset.filter(id__gt=cursor)
    rows = list(queryset[: limit + 1])
    complete = len(rows) <= limit
    rows = rows[:limit]
    items = tuple(
        IndexableVersion(
            document_id=row.document_id,
            version_id=row.pk,
            digest=row.extracted_text_artifact.sha256_digest,
            document_updated_at=row.document.updated_at,
        )
        for row in rows
    )
    return IndexableVersionPage(items, None if complete or not rows else rows[-1].pk, complete)


def _validated_locked_version(*, version_id, expected_digest, store):
    try:
        version_id = uuid.UUID(str(version_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise RetrievalBoundaryError("Document evidence is unavailable") from exc
    version = (
        DocumentVersion.objects.select_for_update()
        .select_related("document", "extracted_text_artifact", "original_artifact")
        .filter(pk=version_id)
        .first()
    )
    if (
        version is None
        or version.document.visibility != Document.Visibility.ACTIVE
        or version.document.current_version_id != version.pk
        or version.processing_state != DocumentVersion.ProcessingState.READY
    ):
        raise RetrievalBoundaryError("Document evidence is unavailable")
    try:
        extracted = version.extracted_text_artifact
        original = version.original_artifact
    except (ExtractedTextArtifact.DoesNotExist, OriginalArtifact.DoesNotExist) as exc:
        raise RetrievalBoundaryError("Document evidence is unavailable") from exc
    if not isinstance(expected_digest, str) or extracted.sha256_digest != expected_digest:
        raise RetrievalBoundaryError("Document evidence is unavailable")
    try:
        reject_quarantined_key(original.storage_key)
        reject_quarantined_key(extracted.storage_key)
        store.validate_integrity(
            original.storage_key,
            expected_byte_length=original.byte_length,
            expected_sha256_digest=original.sha256_digest,
        )
        path = store.validate_integrity(
            extracted.storage_key,
            expected_byte_length=extracted.byte_length,
            expected_sha256_digest=extracted.sha256_digest,
        )
    except Exception as exc:
        raise RetrievalBoundaryError("Document evidence is unavailable") from exc
    return version, extracted, path


def validate_indexable_version(*, version_id, expected_digest, store=None):
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        with transaction.atomic():
            lock_artifact_publication()
            version, _, _ = _validated_locked_version(
                version_id=version_id, expected_digest=expected_digest, store=store,
            )
            return IndexableVersion(
                version.document_id, version.pk, expected_digest, version.document.updated_at,
            )
    finally:
        if owns_store:
            store.close()


def open_verified_extracted_text(*, version_id, expected_digest, store=None):
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        with transaction.atomic():
            lock_artifact_publication()
            version, artifact, path = _validated_locked_version(
                version_id=version_id, expected_digest=expected_digest, store=store,
            )
            digest = hashlib.sha256()
            content = bytearray()
            try:
                with path.open("rb") as source:
                    while chunk := source.read(64 * 1024):
                        content.extend(chunk)
                        digest.update(chunk)
                        if len(content) > artifact.byte_length:
                            raise RetrievalBoundaryError("Document evidence is unavailable")
                text = bytes(content).decode("utf-8", errors="strict")
            except (OSError, UnicodeDecodeError) as exc:
                raise RetrievalBoundaryError("Document evidence is unavailable") from exc
            if (
                len(content) != artifact.byte_length
                or digest.hexdigest() != artifact.sha256_digest
                or len(text) != artifact.character_count
                or not text
                or len(text) > settings.DOCUMENT_EXTRACTION_MAX_CHARACTERS
            ):
                raise RetrievalBoundaryError("Document evidence is unavailable")
            return VerifiedExtractedText(
                version.document_id, version.pk, artifact.sha256_digest,
                artifact.character_count, io.StringIO(text),
            )
    finally:
        if owns_store:
            store.close()


def _authorize_retrieval_candidates_locked(*, actor, candidates, store):
    """Authorize candidates while the caller holds the publication guard transaction."""
    actor_id = getattr(actor, "pk", None)
    fresh_actor = User.objects.select_for_update().filter(pk=actor_id).first() if actor_id else None
    document_ids = {item.document_id for item in candidates}
    documents = {
        item.pk: item
        for item in Document.objects.select_for_update().filter(pk__in=document_ids)
    }
    authorized = []
    seen = set()
    for candidate in candidates:
        key = (candidate.document_id, candidate.version_id, candidate.digest)
        if key in seen:
            continue
        seen.add(key)
        document = documents.get(candidate.document_id)
        if not authorize_document(
            fresh_actor, DocumentCapability.VIEW_CONTENT, document=document,
        ).allowed:
            continue
        try:
            version, _, _ = _validated_locked_version(
                version_id=candidate.version_id,
                expected_digest=candidate.digest,
                store=store,
            )
        except RetrievalBoundaryError:
            continue
        if version.document_id != document.pk:
            continue
        authorized.append(AuthorizedRetrievalCandidate(
            document.pk, version.pk, candidate.digest, document.title, version.sequence,
        ))
    return tuple(authorized)


def _normalize_candidates(candidates):
    candidates = tuple(candidates)
    if len(candidates) > MAX_AUTHORIZATION_CANDIDATES:
        raise ValueError("Too many retrieval candidates")
    for candidate in candidates:
        if not isinstance(candidate, RetrievalCandidate):
            raise ValueError("Retrieval candidate is invalid")
    return candidates


def authorize_retrieval_candidates(*, actor, candidates, store=None):
    candidates = _normalize_candidates(candidates)
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        with transaction.atomic():
            lock_artifact_publication()
            return _authorize_retrieval_candidates_locked(
                actor=actor, candidates=candidates, store=store,
            )
    finally:
        if owns_store:
            store.close()


def release_authorized_evidence(*, actor, candidates, materialize, store=None):
    """Materialize evidence at the guarded F-03 authorization linearization point.

    The internal materializer receives safe authorization metadata only and must
    return the final immutable evidence value. Actor, document and version locks,
    plus the artifact publication guard, remain held until it returns.
    """
    candidates = _normalize_candidates(candidates)
    if not callable(materialize):
        raise ValueError("Evidence materializer is invalid")
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        with transaction.atomic():
            lock_artifact_publication()
            authorized = _authorize_retrieval_candidates_locked(
                actor=actor, candidates=candidates, store=store,
            )
            return materialize(authorized)
    finally:
        if owns_store:
            store.close()
