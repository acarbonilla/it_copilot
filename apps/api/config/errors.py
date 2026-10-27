from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import exception_handler


def structured_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return Response({"error": {"code": "internal_error", "message": "Request could not be completed"}}, status=500)
    code = getattr(exc, "default_code", "api_error")
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    message = str(detail) if detail else "Request could not be completed"
    response.data = {"error": {"code": str(code), "message": message}}
    return response


def structured_not_found(request, exception):
    return JsonResponse({"error": {"code": "not_found", "message": "Not found"}}, status=404)


def csrf_failure(request, reason=""):
    return JsonResponse({"error": {"code": "csrf_failed", "message": "CSRF validation failed"}}, status=403)
