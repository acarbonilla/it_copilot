from django.conf import settings
from django.http import JsonResponse


class DocumentUploadSizeMiddleware:
    """Reject oversized upload requests before CSRF or multipart parsing reads the body."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == "/api/v1/documents":
            try:
                content_length = int(request.META.get("CONTENT_LENGTH", ""))
            except (TypeError, ValueError):
                return JsonResponse(
                    {"error": {"code": "invalid_upload", "message": "Document upload is invalid"}},
                    status=400,
                )
            if content_length <= 0:
                return JsonResponse(
                    {"error": {"code": "invalid_upload", "message": "Document upload is invalid"}},
                    status=400,
                )
            if content_length > settings.DOCUMENT_MAX_REQUEST_BYTES:
                return JsonResponse(
                    {"error": {"code": "request_too_large", "message": "Document upload is too large"}},
                    status=413,
                )
        return self.get_response(request)
