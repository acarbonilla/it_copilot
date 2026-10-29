import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event

from .invitations import _delivery_file, _invitation_id, _remove_delivery_artifact, _token_digest
from .lifecycle import _lock_guard
from .models import AccountInvitation, User


@dataclass(frozen=True)
class RemediationResult:
    invitation_id: str
    outcome: str
    replacement_id: str | None = None


def validate_remediation_actor(actor):
    if (
        actor is None
        or not actor.is_active
        or not actor.is_app_admin
        or actor.lifecycle_state != User.LifecycleState.ACTIVE
        or not actor.has_usable_password()
    ):
        raise ValueError("Audit actor must be an active, activated App Admin")
    return actor


def legacy_candidate_ids():
    return list(
        AccountInvitation.objects.filter(
            delivery_format=AccountInvitation.DeliveryFormat.LEGACY_PATH,
            consumed_at__isnull=True,
            revoked_at__isnull=True,
        )
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)
    )


def remediate_legacy_invitation(*, actor, invitation_id):
    """Revoke one legacy secret and reissue only a still-valid pending invitation."""
    validate_remediation_actor(actor)
    artifact = None
    try:
        with transaction.atomic():
            _lock_guard()
            actor = User.objects.select_for_update().get(pk=actor.pk)
            validate_remediation_actor(actor)
            snapshot = AccountInvitation.objects.only("user_id").get(pk=invitation_id)
            user = User.objects.select_for_update().get(pk=snapshot.user_id)
            invitation = AccountInvitation.objects.select_for_update().get(pk=invitation_id)
            if (
                invitation.delivery_format != AccountInvitation.DeliveryFormat.LEGACY_PATH
                or invitation.consumed_at is not None
                or invitation.revoked_at is not None
            ):
                return RemediationResult(str(invitation_id), "already_remediated")

            now = timezone.now()
            invitation.revoked_at = now
            invitation.save(update_fields=("revoked_at",))
            record_critical_event(
                action=SecurityAuditEvent.Action.ACCOUNT_INVITE_REVOKED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.ACCOUNT_INVITATION,
                target_id=str(invitation.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )

            can_reissue = (
                invitation.expires_at > now
                and user.lifecycle_state == User.LifecycleState.PENDING_INVITATION
                and not user.is_active
                and not user.has_usable_password()
            )
            if not can_reissue:
                return RemediationResult(str(invitation.pk), "revoked_without_reissue")

            token = secrets.token_urlsafe(32)
            replacement = AccountInvitation.objects.create(
                id=_invitation_id(),
                user=user,
                token_digest=_token_digest(token),
                expires_at=now + timedelta(hours=settings.INVITATION_TOKEN_TTL_HOURS),
                invited_by_user_id=actor.pk,
                delivery_format=AccountInvitation.DeliveryFormat.FRAGMENT_V1,
            )
            record_critical_event(
                action=SecurityAuditEvent.Action.ACCOUNT_INVITE_REISSUED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.ACCOUNT_INVITATION,
                target_id=str(replacement.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            artifact = _delivery_file(replacement, email=user.email, token=token)
        return RemediationResult(str(invitation.pk), "reissued", str(replacement.pk))
    except Exception:
        _remove_delivery_artifact(artifact)
        raise
