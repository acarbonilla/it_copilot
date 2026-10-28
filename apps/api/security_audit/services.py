import logging
import re

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.transaction import TransactionManagementError

from .models import SecurityAuditEvent


logger = logging.getLogger(__name__)

_TARGET_IDENTIFIER = re.compile(
    r"^(?:[1-9][0-9]{0,18}|[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$"
)
_REQUEST_IDENTIFIER = re.compile(
    r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$"
)


def _choice_value(value, choices, field_name):
    allowed = {choice.value for choice in choices}
    if value not in allowed:
        raise ValidationError({field_name: "Value is not in the controlled vocabulary"})
    return value


def _optional_identifier(value, *, field_name, max_length, pattern):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > max_length or not pattern.fullmatch(value):
        raise ValidationError({field_name: "Value is not a safe opaque identifier"})
    return value


def _actor_snapshot(actor_user_id):
    if actor_user_id is None:
        return None
    if isinstance(actor_user_id, bool) or not isinstance(actor_user_id, int) or actor_user_id <= 0:
        raise ValidationError({"actor_user_id": "Value must be a positive integer or null"})
    return actor_user_id


def record_security_event(*, action, actor_user_id, target_type, target_id, outcome, request_id=None):
    """Persist exactly one allowlisted event, raising when validation or persistence fails."""
    event = SecurityAuditEvent(
        action=_choice_value(action, SecurityAuditEvent.Action, "action"),
        actor_user_id=_actor_snapshot(actor_user_id),
        target_type=_choice_value(target_type, SecurityAuditEvent.TargetType, "target_type"),
        target_id=_optional_identifier(target_id, field_name="target_id", max_length=128, pattern=_TARGET_IDENTIFIER),
        outcome=_choice_value(outcome, SecurityAuditEvent.Outcome, "outcome"),
        request_id=_optional_identifier(request_id, field_name="request_id", max_length=64, pattern=_REQUEST_IDENTIFIER),
    )
    event.full_clean(validate_unique=False, validate_constraints=True)
    event.save(force_insert=True)
    return event


def record_critical_event(*, action, actor_user_id, target_type, target_id, outcome, request_id=None):
    """Persist an event only inside the same atomic block as its critical mutation."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("Critical audit recording requires an atomic transaction")
    return record_security_event(
        action=action,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_id=request_id,
    )


def record_denied_event_best_effort(*, action, actor_user_id, target_type, target_id, request_id=None):
    """Make one bounded autocommit attempt; never write inside an atomic block."""
    if connection.in_atomic_block or not connection.get_autocommit():
        logger.warning("Security audit denial event skipped because autocommit is unavailable")
        return None
    try:
        return record_security_event(
            action=action,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            outcome=SecurityAuditEvent.Outcome.DENIED,
            request_id=request_id,
        )
    except Exception:  # Authorization denial must not depend on audit availability.
        logger.warning("Security audit denial event could not be persisted")
        return None
