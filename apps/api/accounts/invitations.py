import hashlib
import json
import os
import re
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .models import AccountInvitation, User, canonicalize_email


_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class InvitationConflict(Exception):
    pass


class InvalidInvitationRequest(Exception):
    pass


class InvalidActivation(Exception):
    pass


class PasswordPolicyFailure(Exception):
    pass


def _token_digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _invitation_id():
    return uuid.uuid4()


def _delivery_file(invitation, *, email, token):
    if not settings.DEBUG or settings.INVITATION_DELIVERY_MODE != "file":
        raise ImproperlyConfigured("Invitation delivery requires the explicitly enabled development file sink")
    mailbox_root = Path(settings.INVITATION_MAILBOX_ROOT).resolve()
    mailbox_root.mkdir(parents=True, exist_ok=True)
    if not mailbox_root.is_dir():
        raise ImproperlyConfigured("Invitation mailbox root is not a directory")
    destination = (mailbox_root / f"{invitation.pk}.json").resolve()
    if destination.parent != mailbox_root:
        raise ImproperlyConfigured("Invitation mailbox path escaped its configured root")
    activation_url = f"{settings.INVITATION_ACTIVATION_BASE_URL.rstrip('/')}#token={token}"
    created = False
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8") as mailbox_file:
            json.dump({"recipient": email, "activation_url": activation_url}, mailbox_file)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return destination


def _remove_delivery_artifact(path):
    if path is not None:
        path.unlink(missing_ok=True)


def create_or_reissue_invitation(*, actor, email, it_role, is_app_admin):
    if it_role not in {choice.value for choice in User.ITRole} or not isinstance(is_app_admin, bool):
        raise InvalidInvitationRequest
    try:
        normalized_email = canonicalize_email(email)
        validate_email(normalized_email)
    except (AttributeError, ValueError) as exc:
        raise InvalidInvitationRequest from exc
    except ValidationError as exc:
        raise InvalidInvitationRequest from exc

    token = secrets.token_urlsafe(32)
    now = timezone.now()
    artifact = None
    try:
        with transaction.atomic():
            # Invitation replacement and legacy remediation can target the same
            # pending account. Serialize both through the lifecycle guard before
            # either path locks or mutates the user/invitation rows.
            from .lifecycle import _lock_guard

            _lock_guard()
            try:
                user = User.objects.select_for_update().get(email=normalized_email)
            except User.DoesNotExist:
                user = User(
                    email=normalized_email,
                    is_active=False,
                    is_app_admin=is_app_admin,
                    it_role=it_role,
                    lifecycle_state=User.LifecycleState.PENDING_INVITATION,
                )
                user.set_unusable_password()
                try:
                    user.full_clean()
                    user.save(force_insert=True)
                except (ValidationError, IntegrityError) as exc:
                    raise InvitationConflict from exc
            else:
                if (
                    user.lifecycle_state != User.LifecycleState.PENDING_INVITATION
                    or user.is_active
                    or user.has_usable_password()
                ):
                    raise InvitationConflict
                user.it_role = it_role
                user.is_app_admin = is_app_admin
                user.save(update_fields=("it_role", "is_app_admin"))

            AccountInvitation.objects.select_for_update().filter(
                user=user,
                consumed_at__isnull=True,
                revoked_at__isnull=True,
            ).update(revoked_at=now)
            invitation = AccountInvitation.objects.create(
                id=_invitation_id(),
                user=user,
                token_digest=_token_digest(token),
                expires_at=now + timedelta(hours=settings.INVITATION_TOKEN_TTL_HOURS),
                invited_by_user_id=actor.pk,
                delivery_format=AccountInvitation.DeliveryFormat.FRAGMENT_V1,
            )
            record_critical_event(
                action=SecurityAuditEvent.Action.ACCOUNT_INVITE_CREATED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.ACCOUNT,
                target_id=str(user.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
            artifact = _delivery_file(invitation, email=normalized_email, token=token)
        return invitation
    except Exception:
        _remove_delivery_artifact(artifact)
        raise


def activate_invitation(*, token, password):
    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
        raise InvalidActivation
    digest = _token_digest(token)
    with transaction.atomic():
        # Activation can add an active App Admin, so it participates in the
        # same guard-before-target lock order as every IC-007 membership change.
        from .lifecycle import _lock_guard

        _lock_guard()
        try:
            invitation = AccountInvitation.objects.select_for_update().get(token_digest=digest)
        except AccountInvitation.DoesNotExist as exc:
            raise InvalidActivation from exc
        user = User.objects.select_for_update().get(pk=invitation.user_id)
        now = timezone.now()
        if (
            invitation.consumed_at is not None
            or invitation.revoked_at is not None
            or invitation.expires_at <= now
            or user.lifecycle_state != User.LifecycleState.PENDING_INVITATION
            or user.is_active
            or user.has_usable_password()
        ):
            raise InvalidActivation
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            raise PasswordPolicyFailure from exc

        user.set_password(password)
        user.is_active = True
        user.lifecycle_state = User.LifecycleState.ACTIVE
        user.save(update_fields=("password", "is_active", "lifecycle_state"))
        invitation.consumed_at = now
        invitation.save(update_fields=("consumed_at",))
        record_critical_event(
            action=SecurityAuditEvent.Action.ACCOUNT_ACTIVATION_SUCCEEDED,
            actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.ACCOUNT,
            target_id=str(user.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return user


def record_activation_denial(*, invitation_id=None):
    record_denied_event_best_effort(
        action=SecurityAuditEvent.Action.ACCOUNT_ACTIVATION_DENIED,
        actor_user_id=None,
        target_type=SecurityAuditEvent.TargetType.ACCOUNT_INVITATION,
        target_id=str(invitation_id) if invitation_id else None,
    )
