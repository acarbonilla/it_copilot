import hashlib
import hmac
import math
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .models import SensitiveOperationGrant, SessionReauthenticationThrottle, UserReauthenticationThrottle


GRANT_TTL = timedelta(minutes=2)
THROTTLE_WINDOW = timedelta(minutes=15)
FAILURE_LIMIT = 5
ISSUANCE_LIMIT = 10
LIVE_SESSION_GRANT_LIMIT = 3
_PROOF_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$", re.ASCII)


class GrantDenied(Exception):
    pass


class GrantServiceError(Exception):
    pass


class ReauthenticationDenied(Exception):
    def __init__(self, *, throttled=False, retry_after=0):
        self.throttled = throttled
        self.retry_after = retry_after


@dataclass(frozen=True)
class IssuedGrant:
    proof: str
    expires_at: object


def _pepper():
    value = getattr(settings, "VAULT_GRANT_PEPPER", "")
    if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
        raise ImproperlyConfigured("VAULT_GRANT_PEPPER must be a server-only secret of at least 32 bytes")
    return value.encode("utf-8")


def _digest(domain, value):
    if not isinstance(value, str) or not value:
        raise GrantDenied
    return hmac.new(_pepper(), domain + b"\x00" + value.encode("utf-8"), hashlib.sha256).hexdigest()


def proof_digest(proof):
    if not isinstance(proof, str) or not _PROOF_PATTERN.fullmatch(proof):
        raise GrantDenied
    return _digest(b"vault-grant-proof-v1", proof)


def session_digest(session_key):
    if not isinstance(session_key, str) or not 1 <= len(session_key) <= 64:
        raise GrantDenied
    return _digest(b"vault-grant-session-v1", session_key)


def _locked_session(session_key, user_id, now):
    if not isinstance(session_key, str) or not session_key:
        raise GrantDenied
    session = Session.objects.select_for_update().filter(session_key=session_key, expire_date__gt=now).first()
    if session is None:
        raise GrantDenied
    try:
        decoded = session.get_decoded()
    except Exception as exc:
        raise GrantDenied from exc
    if not isinstance(decoded, dict) or str(decoded.get("_auth_user_id")) != str(user_id):
        raise GrantDenied
    return session


def _reset_window(start, count, now):
    if start is None or now >= start + THROTTLE_WINDOW:
        return now, 0
    return start, count


def _retry_after_minutes(start, now):
    seconds = max(1, int((start + THROTTLE_WINDOW - now).total_seconds()))
    return max(60, math.ceil(seconds / 60) * 60)


def _get_or_create_locked(model, defaults, **lookup):
    row = model.objects.select_for_update().filter(**lookup).first()
    if row is not None:
        return row
    try:
        with transaction.atomic():
            model.objects.create(**lookup, **defaults)
    except IntegrityError:
        pass
    return model.objects.select_for_update().get(**lookup)


def _issue_grant_once(*, actor, session_key, password, now=None):
    now = now or timezone.now()
    actor_id = getattr(actor, "pk", None)
    checked_password_hash = getattr(actor, "password", None)
    checker = getattr(actor, "check_password", None)
    password_ok = bool(
        callable(checker)
        and checker(password if isinstance(password, str) else "")
        and isinstance(password, str)
        and password
    )
    session_hash = session_digest(session_key)
    denial = None
    issued = None
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=actor_id).first()
        if user is None:
            raise ReauthenticationDenied
        try:
            _locked_session(session_key, user.pk, now)
        except GrantDenied:
            record_critical_event(
                action=SecurityAuditEvent.Action.VAULT_REAUTHENTICATION_DENIED,
                actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.AUTHENTICATION,
                target_id=None, outcome=SecurityAuditEvent.Outcome.DENIED,
            )
            raise ReauthenticationDenied

        defaults = {
            "failure_window_started_at": now, "failure_count": 0,
            "issuance_window_started_at": now, "issuance_count": 0,
        }
        user_throttle = _get_or_create_locked(UserReauthenticationThrottle, defaults, user=user)
        session_throttle = _get_or_create_locked(
            SessionReauthenticationThrottle,
            {"failure_window_started_at": now, "failure_count": 0},
            user=user, session_digest=session_hash,
        )
        user_throttle.failure_window_started_at, user_throttle.failure_count = _reset_window(
            user_throttle.failure_window_started_at, user_throttle.failure_count, now
        )
        session_throttle.failure_window_started_at, session_throttle.failure_count = _reset_window(
            session_throttle.failure_window_started_at, session_throttle.failure_count, now
        )
        user_throttle.issuance_window_started_at, user_throttle.issuance_count = _reset_window(
            user_throttle.issuance_window_started_at, user_throttle.issuance_count, now
        )

        blocked = user_throttle.failure_count >= FAILURE_LIMIT or session_throttle.failure_count >= FAILURE_LIMIT
        valid_identity = bool(
            user.is_active and user.lifecycle_state != User.LifecycleState.DEACTIVATED
            and password_ok and user.password == checked_password_hash
        )
        if blocked or not valid_identity:
            if not blocked:
                user_throttle.failure_count += 1
                session_throttle.failure_count += 1
                blocked = user_throttle.failure_count >= FAILURE_LIMIT or session_throttle.failure_count >= FAILURE_LIMIT
            user_throttle.save(update_fields=("failure_window_started_at", "failure_count", "issuance_window_started_at", "issuance_count"))
            session_throttle.save(update_fields=("failure_window_started_at", "failure_count"))
            record_critical_event(
                action=SecurityAuditEvent.Action.VAULT_REAUTHENTICATION_DENIED,
                actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.AUTHENTICATION,
                target_id=None, outcome=SecurityAuditEvent.Outcome.DENIED,
            )
            start = max(user_throttle.failure_window_started_at, session_throttle.failure_window_started_at)
            denial = ReauthenticationDenied(throttled=blocked, retry_after=_retry_after_minutes(start, now) if blocked else 0)
        else:
            live_count = SensitiveOperationGrant.objects.filter(
                user=user, session_digest=session_hash, expires_at__gt=now,
                consumed_at__isnull=True, revoked_at__isnull=True,
            ).count()
            capped = user_throttle.issuance_count >= ISSUANCE_LIMIT or live_count >= LIVE_SESSION_GRANT_LIMIT
            if capped:
                record_critical_event(
                    action=SecurityAuditEvent.Action.VAULT_REAUTHENTICATION_DENIED,
                    actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.AUTHENTICATION,
                    target_id=None, outcome=SecurityAuditEvent.Outcome.DENIED,
                )
                denial = ReauthenticationDenied()
            else:
                user_throttle.failure_count = 0
                session_throttle.failure_count = 0
                user_throttle.issuance_count += 1
                user_throttle.save(update_fields=("failure_window_started_at", "failure_count", "issuance_window_started_at", "issuance_count"))
                session_throttle.save(update_fields=("failure_window_started_at", "failure_count"))
                proof = secrets.token_urlsafe(32)
                expires_at = now + GRANT_TTL
                grant = SensitiveOperationGrant.objects.create(
                    user=user, session_digest=session_hash, proof_digest=proof_digest(proof),
                    scope=SensitiveOperationGrant.Scope.VAULT_SENSITIVE, issued_at=now, expires_at=expires_at,
                )
                record_critical_event(
                    action=SecurityAuditEvent.Action.VAULT_REAUTHENTICATION_SUCCEEDED,
                    actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.AUTHENTICATION,
                    target_id=None, outcome=SecurityAuditEvent.Outcome.SUCCESS,
                )
                record_critical_event(
                    action=SecurityAuditEvent.Action.VAULT_GRANT_ISSUED,
                    actor_user_id=user.pk, target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
                    target_id=str(grant.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS,
                )
                issued = IssuedGrant(proof=proof, expires_at=expires_at)
    if denial:
        raise denial
    return issued


def _mysql_retryable(error):
    values = list(getattr(error, "args", ()))
    values.extend(getattr(getattr(error, "__cause__", None), "args", ()))
    return any(value in (1205, 1213) for value in values if isinstance(value, int))


def issue_grant(*, actor, session_key, password, now=None):
    for attempt in range(2):
        try:
            return _issue_grant_once(actor=actor, session_key=session_key, password=password, now=now)
        except DatabaseError as exc:
            if attempt or not _mysql_retryable(exc):
                raise
    raise ReauthenticationDenied


def lock_valid_grant(*, actor, session_key, proof, now=None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Grant validation requires an active transaction")
    now = now or timezone.now()
    user_id = getattr(actor, "pk", None)
    _locked_session(session_key, user_id, now)
    digest = proof_digest(proof)
    grant = SensitiveOperationGrant.objects.select_for_update().filter(proof_digest=digest).first()
    expected_session = session_digest(session_key)
    if not (
        grant
        and grant.user_id == user_id
        and hmac.compare_digest(grant.session_digest, expected_session)
        and grant.scope == SensitiveOperationGrant.Scope.VAULT_SENSITIVE
        and grant.expires_at > now
        and grant.consumed_at is None
        and grant.revoked_at is None
    ):
        raise GrantDenied
    return grant


def consume_grant(grant, *, actor_user_id, denied=False, now=None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Grant consumption requires an active transaction")
    grant.consumed_at = now or timezone.now()
    grant.save(update_fields=("consumed_at",))
    try:
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_GRANT_DENIED if denied else SecurityAuditEvent.Action.VAULT_GRANT_USED,
            actor_user_id=actor_user_id,
            target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
            target_id=str(grant.pk),
            outcome=SecurityAuditEvent.Outcome.DENIED if denied else SecurityAuditEvent.Outcome.SUCCESS,
        )
    except Exception as exc:
        raise GrantServiceError("Grant audit could not be completed") from exc


def audit_invalid_grant(actor):
    record_denied_event_best_effort(
        action=SecurityAuditEvent.Action.VAULT_GRANT_DENIED,
        actor_user_id=getattr(actor, "pk", None),
        target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
        target_id=None,
    )


def revoke_session_grants(*, user, session_key, reason, audit_actor_id=None, now=None):
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Grant revocation requires an active transaction")
    now = now or timezone.now()
    _locked_session(session_key, user.pk, now)
    digest = session_digest(session_key)
    grants = list(SensitiveOperationGrant.objects.select_for_update().filter(
        user=user, session_digest=digest, consumed_at__isnull=True, revoked_at__isnull=True,
    ).order_by("id"))
    if grants:
        SensitiveOperationGrant.objects.filter(pk__in=[grant.pk for grant in grants]).update(
            revoked_at=now, revocation_reason=reason)
    try:
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_GRANT_REVOKED,
            actor_user_id=audit_actor_id or user.pk,
            target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
            target_id=None,
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
    except Exception as exc:
        raise GrantServiceError("Grant revocation audit could not be completed") from exc
    return len(grants)


def revoke_all_user_grants(*, user, reason, audit_actor_id=None, now=None):
    """Revoke all grants after the caller locks the user and affected sessions."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Grant revocation requires an active transaction")
    now = now or timezone.now()
    grants = list(SensitiveOperationGrant.objects.select_for_update().filter(
        user=user, consumed_at__isnull=True, revoked_at__isnull=True,
    ).order_by("id"))
    if grants:
        SensitiveOperationGrant.objects.filter(pk__in=[grant.pk for grant in grants]).update(
            revoked_at=now, revocation_reason=reason)
    try:
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_GRANT_REVOKED,
            actor_user_id=audit_actor_id or user.pk,
            target_type=SecurityAuditEvent.TargetType.PRIVATE_RESOURCE,
            target_id=None,
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
    except Exception as exc:
        raise GrantServiceError("Grant revocation audit could not be completed") from exc
    return len(grants)
