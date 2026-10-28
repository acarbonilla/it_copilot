from django.contrib.sessions.models import Session
from django.db import transaction

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event

from .models import AccountDeletionReview, AdminLifecycleGuard, User


class InvalidLifecycleState(Exception):
    pass


class InvalidLifecycleRequest(Exception):
    pass


class LastActiveAdmin(Exception):
    pass


def lifecycle_status(user):
    if user.lifecycle_state == User.LifecycleState.PENDING_INVITATION:
        return "pending_invitation"
    if user.lifecycle_state == User.LifecycleState.DEACTIVATED:
        return "deactivated"
    return "active" if user.is_active else "inactive_legacy"


def user_payload(user):
    return {
        "id": user.pk,
        "email": user.email,
        "is_active": user.is_active,
        "is_app_admin": user.is_app_admin,
        "it_role": user.it_role,
        "lifecycle_status": lifecycle_status(user),
    }


def _lock_guard():
    return AdminLifecycleGuard.objects.select_for_update().get(pk=1)


def _active_admin_count():
    return User.objects.filter(
        is_active=True,
        is_app_admin=True,
        lifecycle_state=User.LifecycleState.ACTIVE,
    ).count()


def _protect_last_admin(target, *, removing_admin):
    if removing_admin and target.is_active and target.is_app_admin and target.lifecycle_state == User.LifecycleState.ACTIVE:
        if _active_admin_count() <= 1:
            raise LastActiveAdmin


def _revoke_sessions(user_id):
    matching_ids = []
    for session in Session.objects.all().iterator():
        try:
            if str(session.get_decoded().get("_auth_user_id")) == str(user_id):
                matching_ids.append(session.session_key)
        except Exception:
            continue
    if matching_ids:
        Session.objects.filter(session_key__in=matching_ids).delete()
    return len(matching_ids)


def update_user_roles(*, actor, target_id, changes):
    if not changes or set(changes) - {"it_role", "is_app_admin"}:
        raise InvalidLifecycleRequest
    if "it_role" in changes and changes["it_role"] not in {choice.value for choice in User.ITRole}:
        raise InvalidLifecycleRequest
    if "is_app_admin" in changes and not isinstance(changes["is_app_admin"], bool):
        raise InvalidLifecycleRequest
    with transaction.atomic():
        _lock_guard()
        target = User.objects.select_for_update().get(pk=target_id)
        removing_admin = target.is_app_admin and changes.get("is_app_admin") is False
        _protect_last_admin(target, removing_admin=removing_admin)
        update_fields = []
        for field in ("it_role", "is_app_admin"):
            if field in changes and getattr(target, field) != changes[field]:
                setattr(target, field, changes[field])
                update_fields.append(field)
        if update_fields:
            target.save(update_fields=tuple(update_fields))
            record_critical_event(
                action=SecurityAuditEvent.Action.ACCOUNT_ROLE_CHANGED,
                actor_user_id=actor.pk,
                target_type=SecurityAuditEvent.TargetType.ACCOUNT,
                target_id=str(target.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            )
        return target


def deactivate_user(*, actor, target_id):
    with transaction.atomic():
        _lock_guard()
        target = User.objects.select_for_update().get(pk=target_id)
        if target.lifecycle_state != User.LifecycleState.ACTIVE or not target.is_active:
            raise InvalidLifecycleState
        _protect_last_admin(target, removing_admin=True)
        target.is_active = False
        target.lifecycle_state = User.LifecycleState.DEACTIVATED
        target.save(update_fields=("is_active", "lifecycle_state"))
        _revoke_sessions(target.pk)
        record_critical_event(
            action=SecurityAuditEvent.Action.ACCOUNT_DEACTIVATED,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.ACCOUNT,
            target_id=str(target.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return target


def reactivate_user(*, actor, target_id):
    with transaction.atomic():
        target = User.objects.select_for_update().get(pk=target_id)
        if (
            target.lifecycle_state != User.LifecycleState.DEACTIVATED
            or target.is_active
            or not target.has_usable_password()
        ):
            raise InvalidLifecycleState
        target.is_active = True
        target.lifecycle_state = User.LifecycleState.ACTIVE
        target.save(update_fields=("is_active", "lifecycle_state"))
        record_critical_event(
            action=SecurityAuditEvent.Action.ACCOUNT_REACTIVATED,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.ACCOUNT,
            target_id=str(target.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return target


def request_deletion_review(*, actor, target_id, reason_code):
    if reason_code not in {choice.value for choice in AccountDeletionReview.Reason}:
        raise InvalidLifecycleRequest
    with transaction.atomic():
        _lock_guard()
        target = User.objects.select_for_update().get(pk=target_id)
        if target.lifecycle_state == User.LifecycleState.PENDING_INVITATION:
            raise InvalidLifecycleState
        _protect_last_admin(target, removing_admin=True)
        review = AccountDeletionReview.objects.create(
            target=target,
            requested_by_user_id=actor.pk,
            reason_code=reason_code,
        )
        record_critical_event(
            action=SecurityAuditEvent.Action.ACCOUNT_DELETION_REVIEW_REQUESTED,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.ACCOUNT,
            target_id=str(target.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return review
