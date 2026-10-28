from collections.abc import Mapping

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from .invitations import (
    InvalidActivation,
    InvalidInvitationRequest,
    InvitationConflict,
    PasswordPolicyFailure,
    activate_invitation,
    create_or_reissue_invitation,
    record_activation_denial,
)
from .policies import can_invite_accounts


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


@method_decorator(csrf_protect, name="dispatch")
class InvitationCreateView(APIView):
    permission_classes = []

    def post(self, request):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return _error("authentication_required", "Authentication required", 401)
        if not can_invite_accounts(user):
            return _error("permission_denied", "Permission denied", 403)
        if not isinstance(request.data, Mapping):
            return _error("invalid_request", "Invitation request is invalid", 400)
        try:
            invitation = create_or_reissue_invitation(
                actor=user,
                email=request.data.get("email"),
                it_role=request.data.get("it_role"),
                is_app_admin=request.data.get("is_app_admin"),
            )
        except InvalidInvitationRequest:
            return _error("invalid_request", "Invitation request is invalid", 400)
        except InvitationConflict:
            return _error("invitation_conflict", "Account cannot be invited", 409)
        return Response(
            {
                "invitation": {
                    "id": str(invitation.pk),
                    "status": "pending",
                    "expires_at": invitation.expires_at.isoformat(),
                }
            },
            status=201,
        )


@method_decorator(csrf_protect, name="dispatch")
class ActivationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not isinstance(request.data, Mapping):
            return _error("invalid_activation", "Activation request is invalid", 400)
        token = request.data.get("token")
        password = request.data.get("password")
        if not isinstance(token, str) or not isinstance(password, str):
            record_activation_denial()
            return _error("invalid_activation", "Activation request is invalid", 400)
        try:
            activate_invitation(token=token, password=password)
        except PasswordPolicyFailure:
            record_activation_denial()
            return _error("password_policy_failed", "Password does not meet requirements", 400)
        except InvalidActivation:
            record_activation_denial()
            return _error("invalid_activation", "Activation request is invalid", 400)
        return Response({"status": "activated"}, status=200)
