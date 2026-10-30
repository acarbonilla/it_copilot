import hashlib
from collections.abc import Mapping
from math import ceil

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import Document, DocumentVersion
from .policies import DocumentCapability, authorize_document, is_active_identity, visible_documents
from .services import (DocumentConflictError, DocumentUnavailableError, archive_document, delete_document,
                       restore_document, retry_document_processing, update_document_metadata)
from .storage import ArtifactStorageError, PrivateArtifactStore
from .uploads import InvalidUpload, UploadCompensationError, UploadFailed, create_document_upload


def _error(code, message, status): return Response({"error": {"code": code, "message": message}}, status=status)
def _identity(request): return request.user if is_active_identity(request.user) else None


def _processing(document):
    version = document.candidate_version or document.current_version
    return None if version is None else {"version_id": str(version.pk), "sequence": version.sequence,
                                        "status": version.processing_state.lower()}


def _payload(user, document, operational=False):
    capabilities = {name: authorize_document(user, capability, document=document).allowed for name, capability in {
        "edit": DocumentCapability.EDIT_METADATA, "download": DocumentCapability.DOWNLOAD,
        "archive": DocumentCapability.ARCHIVE, "restore": DocumentCapability.RESTORE,
        "delete": DocumentCapability.DELETE, "retry": DocumentCapability.PROCESS}.items()}
    data = {"id": str(document.pk), "visibility": document.visibility.lower(),
            "metadata_revision": document.metadata_revision, "created_at": document.created_at,
            "updated_at": document.updated_at, "processing": _processing(document), "capabilities": capabilities}
    if not operational:
        data.update(title=document.title, description=document.description, owner_id=document.owner_id)
    return data


def _get(user, document_id, capability=DocumentCapability.VIEW_METADATA):
    document = Document.objects.select_related("current_version", "candidate_version").filter(pk=document_id).first()
    if document is None or not authorize_document(user, capability, document=document).allowed:
        raise DocumentUnavailableError
    return document


def _mutation(call):
    try: return call()
    except (DocumentUnavailableError, PermissionDenied): return _error("not_found", "Document not found", 404)
    except DocumentConflictError: return _error("conflict", "Document was modified or is not in the required state", 409)
    except (ValidationError, TypeError, ValueError): return _error("invalid_request", "Request is invalid", 400)


@method_decorator(csrf_protect, name="dispatch")
class DocumentCollectionView(APIView):
    permission_classes = []
    def get(self, request):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        operational = user.is_app_admin and user.it_role == User.ITRole.NONE
        queryset = Document.objects.exclude(visibility="DELETED") if operational else visible_documents(user)
        if not operational and user.it_role == User.ITRole.NONE: return _error("permission_denied", "Permission denied", 403)
        visibility = request.query_params.get("visibility")
        if visibility:
            value = visibility.upper()
            if value not in {Document.Visibility.ACTIVE, Document.Visibility.ARCHIVED}:
                return _error("invalid_request", "Filter is invalid", 400)
            queryset = queryset.filter(visibility=value)
        owner = request.query_params.get("owner")
        if owner:
            if user.it_role != User.ITRole.IT_DOC_ADMIN: return _error("permission_denied", "Permission denied", 403)
            try: queryset = queryset.filter(owner_id=int(owner))
            except ValueError: return _error("invalid_request", "Filter is invalid", 400)
        ordering = request.query_params.get("ordering", "-created")
        order_map = {"created": "created_at", "-created": "-created_at", "title": "title", "-title": "-title"}
        if ordering not in order_map or (operational and "title" in ordering):
            return _error("invalid_request", "Ordering is invalid", 400)
        try: page, page_size = int(request.query_params.get("page", 1)), int(request.query_params.get("page_size", 25))
        except (TypeError, ValueError): return _error("invalid_request", "Pagination is invalid", 400)
        if page < 1 or not 1 <= page_size <= 100: return _error("invalid_request", "Pagination is invalid", 400)
        queryset = queryset.select_related("current_version", "candidate_version").order_by(order_map[ordering], "id")
        count, start = queryset.count(), (page - 1) * page_size
        return Response({"documents": [_payload(user, item, operational) for item in queryset[start:start + page_size]],
                         "pagination": {"page": page, "page_size": page_size, "count": count,
                                        "total_pages": ceil(count / page_size) if count else 0}})

    def post(self, request):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        try: request_length = int(request.META.get("CONTENT_LENGTH", ""))
        except (TypeError, ValueError): return _error("invalid_upload", "Document upload is invalid", 400)
        if request_length <= 0 or request_length > settings.DOCUMENT_MAX_REQUEST_BYTES:
            return _error("request_too_large", "Document upload is too large", 413)
        if not request.content_type or not request.content_type.lower().startswith("multipart/form-data"):
            return _error("invalid_upload", "Document upload is invalid", 400)
        if len(request.FILES) != 1 or "file" not in request.FILES or set(request.data) - {"file", "title", "description"}:
            return _error("invalid_upload", "Document upload is invalid", 400)
        try: result = create_document_upload(actor=user, title=request.data.get("title"),
                description=request.data.get("description", ""), uploaded_file=request.FILES["file"])
        except PermissionDenied: return _error("permission_denied", "Permission denied", 403)
        except (InvalidUpload, ValidationError): return _error("invalid_upload", "Document upload is invalid", 400)
        except (UploadCompensationError, UploadFailed): return _error("upload_failed", "Document upload could not be completed", 500)
        return Response({"document": {"id": str(result.document.pk), "version_id": str(result.version.pk),
                                      "status": result.version.processing_state.lower()}}, status=201)


@method_decorator(csrf_protect, name="dispatch")
class DocumentDetailView(APIView):
    permission_classes = []
    def get(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        operational = user.is_app_admin and user.it_role == User.ITRole.NONE
        if operational:
            document = Document.objects.select_related("current_version", "candidate_version").filter(pk=document_id).exclude(visibility="DELETED").first()
            return _error("not_found", "Document not found", 404) if document is None else Response({"document": _payload(user, document, True)})
        try: return Response({"document": _payload(user, _get(user, document_id))})
        except DocumentUnavailableError: return _error("not_found", "Document not found", 404)
    def patch(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        if not isinstance(request.data, Mapping) or set(request.data) - {"title", "description", "expected_revision"}:
            return _error("invalid_request", "Request is invalid", 400)
        result = _mutation(lambda: update_document_metadata(actor=user, document_id=document_id,
            expected_revision=request.data.get("expected_revision"), title=request.data.get("title"),
            description=request.data.get("description")))
        return result if isinstance(result, Response) else Response({"document": _payload(user, result)})


class DocumentStatusView(APIView):
    permission_classes = []
    def get(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        try: return Response({"processing": _processing(_get(user, document_id))})
        except DocumentUnavailableError: return _error("not_found", "Document not found", 404)


class _StreamingPrivateArtifact:
    def __init__(self, source, store):
        self.source = source
        self.store = store

    def __getattr__(self, name):
        return getattr(self.source, name)

    def read(self, size=-1):
        return self.source.read(size)

    def close(self):
        try:
            if self.source is not None:
                self.source.close()
                self.source = None
        finally:
            if self.store is not None:
                self.store.close()
                self.store = None


class DocumentDownloadView(APIView):
    permission_classes = []
    def get(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        store = None
        source = None
        try:
            document = _get(user, document_id, DocumentCapability.DOWNLOAD)
            version = document.current_version or document.candidate_version
            if version is None or version.processing_state == DocumentVersion.ProcessingState.STAGED: raise DocumentUnavailableError
            artifact = version.original_artifact
            store = PrivateArtifactStore()
            path = store.resolve(artifact.storage_key)
            digest, size = hashlib.sha256(), 0
            source = path.open("rb")
            while chunk := source.read(65536): digest.update(chunk); size += len(chunk)
            if digest.hexdigest() != artifact.sha256_digest or size != artifact.byte_length: raise ArtifactStorageError
            source.seek(0)
            streaming_artifact = _StreamingPrivateArtifact(source, store)
            source = store = None
            response = FileResponse(streaming_artifact, as_attachment=True, filename=artifact.original_filename,
                                    content_type=artifact.detected_media_type)
            response["X-Content-Type-Options"], response["Cache-Control"] = "nosniff", "private, no-store"
            return response
        except (DocumentUnavailableError, ArtifactStorageError, AttributeError):
            if source is not None: source.close()
            if store is not None: store.close()
            return _error("not_found", "Document not found", 404)
        except Exception:
            if source is not None: source.close()
            if store is not None: store.close()
            raise


class DocumentActionView(APIView):
    permission_classes = []; operation = None
    @method_decorator(csrf_protect)
    def post(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        if not isinstance(request.data, Mapping) or set(request.data) != {"expected_revision"}:
            return _error("invalid_request", "Request is invalid", 400)
        result = _mutation(lambda: self.operation(actor=user, document_id=document_id,
                                                   expected_revision=request.data["expected_revision"]))
        return result if isinstance(result, Response) else Response({"document": _payload(user, result.document)})

class DocumentArchiveView(DocumentActionView): operation = staticmethod(archive_document)
class DocumentRestoreView(DocumentActionView): operation = staticmethod(restore_document)
class DocumentDeleteView(DocumentActionView): operation = staticmethod(delete_document)


class DocumentRetryView(APIView):
    permission_classes = []
    @method_decorator(csrf_protect)
    def post(self, request, document_id):
        user = _identity(request)
        if user is None: return _error("authentication_required", "Authentication required", 401)
        if not isinstance(request.data, Mapping) or set(request.data) != {"expected_revision", "version_id"}:
            return _error("invalid_request", "Request is invalid", 400)
        result = _mutation(lambda: retry_document_processing(actor=user, document_id=document_id,
            version_id=request.data["version_id"], expected_revision=request.data["expected_revision"]))
        return result if isinstance(result, Response) else Response({"job": {"id": str(result.pk), "status": "pending"}}, status=202)


DocumentUploadView = DocumentCollectionView
