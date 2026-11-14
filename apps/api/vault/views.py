from collections.abc import Mapping
import re

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from session_auth.views import active_authenticated_user
from accounts.models import User

from .authorization import SensitiveAuthorization
from .grants import GrantDenied, ReauthenticationDenied, audit_invalid_grant, issue_grant, revoke_session_grants
from .lifecycle import deleted_metadata_payload, list_deleted_credentials
from .models import SensitiveOperationGrant
from .services import (
    VaultConflictError, VaultSensitiveAuthorizationRequired, VaultServiceUnavailable, VaultUnavailableError,
    create_credential, delete_credential, get_credential_metadata, list_credentials, metadata_payload,
    restore_credential, reveal_credential, update_credential,
)


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


def _identity(request):
    return active_authenticated_user(request)


_GRANT_PROOF = re.compile(r"^[A-Za-z0-9_-]{43}$", re.ASCII)


def _authorization(request):
    proof = request.headers.get("X-Vault-Grant")
    session_key = request.session.session_key
    if not isinstance(proof, str) or not _GRANT_PROOF.fullmatch(proof) or not isinstance(session_key, str):
        return None
    return SensitiveAuthorization(proof=proof, session_key=session_key)


def _sensitive_error(exc, actor):
    if isinstance(exc, VaultSensitiveAuthorizationRequired):
        audit_invalid_grant(actor)
        return _error("invalid_grant", "Sensitive authorization is invalid", 403)
    if isinstance(exc, VaultUnavailableError):
        return _error("credential_unavailable", "Credential is unavailable", 404)
    if isinstance(exc, VaultConflictError):
        return _error("conflict", "Credential state conflicts with the request", 409)
    if isinstance(exc, ValidationError):
        return _error("invalid_request", "Request is invalid", 400)
    return _error("service_unavailable", "Vault operation could not be completed", 503)


class VaultReauthenticationView(APIView):
    permission_classes = []

    @method_decorator(csrf_protect)
    def post(self, request):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        password = request.data.get("password") if isinstance(request.data, Mapping) else None
        try:
            issued = issue_grant(actor=user, session_key=request.session.session_key, password=password)
        except ReauthenticationDenied as exc:
            response = _error("reauthentication_failed", "Reauthentication failed", 429 if exc.throttled else 403)
            if exc.throttled:
                response["Retry-After"] = str(exc.retry_after)
            return response
        except (DatabaseError, ImproperlyConfigured):
            return _error("service_unavailable", "Vault operation could not be completed", 503)
        response = Response({"grant": issued.proof, "expiresAt": issued.expires_at.isoformat()}, status=201)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class VaultGrantRevokeView(APIView):
    permission_classes = []

    @method_decorator(csrf_protect)
    def post(self, request):
        actor = _identity(request)
        if actor is None:
            return _error("authentication_required", "Authentication required", 401)
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(pk=actor.pk, is_active=True).exclude(
                    lifecycle_state=User.LifecycleState.DEACTIVATED).first()
                if user is None:
                    return _error("authentication_required", "Authentication required", 401)
                revoke_session_grants(user=user, session_key=request.session.session_key,
                    reason=SensitiveOperationGrant.RevocationReason.EXPLICIT)
        except GrantDenied:
            return _error("authentication_required", "Authentication required", 401)
        except Exception:
            return _error("service_unavailable", "Vault operation could not be completed", 503)
        return Response(status=204)


class VaultDeletedCredentialCollectionView(APIView):
    permission_classes = []

    def get(self, request):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        try:
            limit = int(request.query_params.get("limit", "25"))
            page = list_deleted_credentials(actor=user, cursor=request.query_params.get("cursor"), limit=limit)
        except (ValueError, ValidationError):
            return _error("invalid_request", "Request is invalid", 400)
        now = timezone.now()
        response = Response({
            "credentials": [deleted_metadata_payload(record, now=now) for record in page.records],
            "nextCursor": page.next_cursor,
        })
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response


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
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        data = request.data if isinstance(request.data, Mapping) else {}
        try:
            record = create_credential(actor=user, authorization=_authorization(request),
                credential_type=data.get("credentialType"), label=data.get("label"),
                secret_fields=data.get("secretFields"), service_label=data.get("serviceLabel", ""),
                origin=data.get("origin", ""))
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError, VaultConflictError,
                ValidationError, VaultServiceUnavailable) as exc:
            return _sensitive_error(exc, user)
        return Response({"credential": metadata_payload(record)}, status=201)


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
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        data = request.data if isinstance(request.data, Mapping) else {}
        try:
            record = update_credential(actor=user, authorization=_authorization(request), record_id=credential_id,
                expected_revision=data.get("expectedRevision"), metadata_changes=data.get("metadata"),
                secret_fields=data.get("secretFields"))
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError, VaultConflictError,
                ValidationError, VaultServiceUnavailable) as exc:
            return _sensitive_error(exc, user)
        return Response({"credential": metadata_payload(record)})

    def delete(self, request, credential_id):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        data = request.data if isinstance(request.data, Mapping) else {}
        try:
            delete_credential(actor=user, authorization=_authorization(request), record_id=credential_id,
                expected_revision=data.get("expectedRevision"))
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError, VaultConflictError,
                ValidationError, VaultServiceUnavailable) as exc:
            return _sensitive_error(exc, user)
        return Response(status=204)


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialRevealView(APIView):
    permission_classes = []

    def post(self, request, credential_id):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        try:
            deferred = reveal_credential(actor=user, authorization=_authorization(request), record_id=credential_id)
            revealed = deferred.release()
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError, VaultConflictError,
                ValidationError, VaultServiceUnavailable) as exc:
            return _sensitive_error(exc, user)
        response = Response({"credential": {"id": str(credential_id), "revealed": revealed}})
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response


@method_decorator(csrf_protect, name="dispatch")
class VaultCredentialRestoreView(APIView):
    permission_classes = []

    def post(self, request, credential_id):
        user = _identity(request)
        if user is None:
            return _error("authentication_required", "Authentication required", 401)
        data = request.data if isinstance(request.data, Mapping) else {}
        try:
            record = restore_credential(actor=user, authorization=_authorization(request), record_id=credential_id,
                expected_revision=data.get("expectedRevision"))
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError, VaultConflictError,
                ValidationError, VaultServiceUnavailable) as exc:
            return _sensitive_error(exc, user)
        return Response({"credential": metadata_payload(record)})
