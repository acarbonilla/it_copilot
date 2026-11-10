from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from session_auth.views import active_authenticated_user

from .services import VaultUnavailableError, get_credential_metadata, list_credentials, metadata_payload


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


def _identity(request):
    return active_authenticated_user(request)


def _sensitive_disabled():
    return _error("sensitive_operation_unavailable", "Sensitive vault operation is unavailable", 503)


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialCollectionView(APIView):
    permission_classes = []

    def get(self, request):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        try:
            limit = int(request.query_params.get("limit", "25"))
            credential_type = request.query_params.get("type")
            page = list_credentials(actor=user, credential_type=credential_type,
                                    prefix=request.query_params.get("prefix"), cursor=request.query_params.get("cursor"), limit=limit)
        except (ValueError, ValidationError):
            return _error("invalid_request", "Request is invalid", 400)
        return Response({"credentials": [metadata_payload(record) for record in page.records], "nextCursor": page.next_cursor})

    def post(self, request):
        if _identity(request) is None:
            return _error("authentication_required", "Authentication required", 401)
        return _sensitive_disabled()


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialDetailView(APIView):
    permission_classes = []

    def get(self, request, credential_id):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        try:
            record = get_credential_metadata(actor=user, record_id=credential_id)
        except VaultUnavailableError:
            return _error("credential_unavailable", "Credential is unavailable", 404)
        return Response({"credential": metadata_payload(record)})

    def patch(self, request, credential_id):
        if _identity(request) is None:
            return _error("authentication_required", "Authentication required", 401)
        return _sensitive_disabled()

    def delete(self, request, credential_id):
        if _identity(request) is None:
            return _error("authentication_required", "Authentication required", 401)
        return _sensitive_disabled()


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialRevealView(APIView):
    permission_classes = []

    def post(self, request, credential_id):
        if _identity(request) is None:
            return _error("authentication_required", "Authentication required", 401)
        return _sensitive_disabled()


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialRestoreView(APIView):
    permission_classes = []

    def post(self, request, credential_id):
        if _identity(request) is None:
            return _error("authentication_required", "Authentication required", 401)
        return _sensitive_disabled()
