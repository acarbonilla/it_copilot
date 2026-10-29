from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from .uploads import InvalidUpload, UploadCompensationError, UploadFailed, create_document_upload


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


@method_decorator(csrf_protect, name="dispatch")
class DocumentUploadView(APIView):
    permission_classes = []

    def post(self, request):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return _error("authentication_required", "Authentication required", 401)
        try:
            request_length = int(request.META.get("CONTENT_LENGTH", ""))
        except (TypeError, ValueError):
            return _error("invalid_upload", "Document upload is invalid", 400)
        if request_length <= 0 or request_length > settings.DOCUMENT_MAX_REQUEST_BYTES:
            return _error("request_too_large", "Document upload is too large", 413)
        if not request.content_type or not request.content_type.lower().startswith("multipart/form-data"):
            return _error("invalid_upload", "Document upload is invalid", 400)
        if len(request.FILES) != 1 or "file" not in request.FILES:
            return _error("invalid_upload", "Document upload is invalid", 400)
        allowed_fields = {"file", "title", "description"}
        if set(request.data) - allowed_fields:
            return _error("invalid_upload", "Document upload is invalid", 400)
        title = request.data.get("title")
        description = request.data.get("description", "")
        if not isinstance(title, str) or not isinstance(description, str):
            return _error("invalid_upload", "Document upload is invalid", 400)
        try:
            result = create_document_upload(
                actor=user,
                title=title,
                description=description,
                uploaded_file=request.FILES["file"],
            )
        except PermissionDenied:
            return _error("permission_denied", "Permission denied", 403)
        except (InvalidUpload, ValidationError):
            return _error("invalid_upload", "Document upload is invalid", 400)
        except (UploadCompensationError, UploadFailed):
            return _error("upload_failed", "Document upload could not be completed", 500)
        return Response(
            {
                "document": {
                    "id": str(result.document.pk),
                    "version_id": str(result.version.pk),
                    "status": result.version.processing_state.lower(),
                }
            },
            status=201,
        )
