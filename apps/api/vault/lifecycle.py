import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from accounts.models import User

from .models import (
    VaultBackupSet,
    VaultMaintenanceConfirmation,
    VaultMaintenanceHold,
    VaultMaintenanceJournal,
    VaultMaintenanceOperation,
    VaultRecord,
)


@dataclass(frozen=True)
class DeletedCredentialPage:
    records: list
    next_cursor: str | None


@dataclass(frozen=True)
class PurgeEligibility:
    eligible: bool
    reasons: tuple[str, ...]


def restore_is_eligible(record, *, now=None):
    now = now or timezone.now()
    return bool(
        record.lifecycle == VaultRecord.Lifecycle.DELETED
        and record.restore_expires_at is not None
        and now < record.restore_expires_at
    )


def purge_time_is_eligible(record, *, now=None):
    now = now or timezone.now()
    return bool(
        record.lifecycle == VaultRecord.Lifecycle.DELETED
        and record.restore_expires_at is not None
        and now >= record.restore_expires_at
    )


def deleted_metadata_payload(record, *, now=None):
    return {
        "id": str(record.pk),
        "credential_type": record.credential_type,
        "label": record.label,
        "service_label": record.service_label,
        "origin": record.origin,
        "revision": record.revision,
        "restorationEligible": restore_is_eligible(record, now=now),
        "restorationExpiresAt": record.restore_expires_at.isoformat(),
    }


def _encode_cursor(record):
    raw = json.dumps(
        {"created_at": record.created_at.isoformat(), "id": str(record.pk)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value):
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValidationError({"cursor": "Cursor is invalid"})
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        data = json.loads(raw.decode("utf-8"))
        created_at = datetime.fromisoformat(data["created_at"])
        record_id = uuid.UUID(data["id"])
    except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError({"cursor": "Cursor is invalid"}) from exc
    if created_at.tzinfo is None or set(data) != {"created_at", "id"}:
        raise ValidationError({"cursor": "Cursor is invalid"})
    return created_at, record_id


def list_deleted_credentials(*, actor, cursor=None, limit=25):
    actor_id = getattr(actor, "pk", None)
    owner = User.objects.filter(pk=actor_id, is_active=True).exclude(
        lifecycle_state=User.LifecycleState.DEACTIVATED
    ).first()
    if owner is None:
        raise ValidationError("Vault is unavailable")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValidationError({"limit": "Must be between 1 and 100"})
    queryset = VaultRecord.objects.filter(owner=owner, lifecycle=VaultRecord.Lifecycle.DELETED)
    if cursor is not None:
        created_at, record_id = _decode_cursor(cursor)
        queryset = queryset.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=record_id))
    records = list(queryset[: limit + 1])
    next_cursor = _encode_cursor(records[limit - 1]) if len(records) > limit else None
    return DeletedCredentialPage(records=records[:limit], next_cursor=next_cursor)


def evaluate_purge_eligibility(*, record, expected_revision, operation=None, confirmation=None,
                               capability_authorized=False, now=None):
    """Read-only T02A predicate. It never mutates or purges a credential."""
    now = now or timezone.now()
    reasons = []
    if not purge_time_is_eligible(record, now=now):
        reasons.append("retention_not_elapsed")
    if record.revision != expected_revision:
        reasons.append("revision_mismatch")
    if VaultMaintenanceHold.objects.filter(owner_id=record.owner_id, released_at__isnull=True).filter(
            Q(scope=VaultMaintenanceHold.Scope.OWNER) |
            Q(scope=VaultMaintenanceHold.Scope.RECORD, record=record)).exists():
        reasons.append("active_hold")
    if VaultMaintenanceJournal.objects.filter(
            Q(owner_id=record.owner_id) | Q(record=record),
            state__in=(VaultMaintenanceJournal.State.PENDING, VaultMaintenanceJournal.State.RUNNING,
                       VaultMaintenanceJournal.State.PAUSED)).exclude(
            operation=operation).exists():
        reasons.append("conflicting_journal")
    if not VaultBackupSet.objects.filter(state=VaultBackupSet.State.VERIFIED).exists():
        reasons.append("verified_checkpoint_missing")
    if not capability_authorized:
        reasons.append("capability_missing")
    if not operation or operation.mode != VaultMaintenanceOperation.Mode.EXECUTE or not operation.parent_dry_run_id:
        reasons.append("completed_dry_run_missing")
    elif operation.parent_dry_run.state != VaultMaintenanceOperation.State.COMPLETED:
        reasons.append("completed_dry_run_missing")
    if not isinstance(confirmation, VaultMaintenanceConfirmation) or confirmation.operation_id != getattr(operation, "pk", None):
        reasons.append("confirmation_missing")
    elif confirmation.consumed_at is not None or confirmation.expires_at <= now or (
            confirmation.parameter_digest != operation.parameter_digest):
        reasons.append("confirmation_invalid")
    return PurgeEligibility(eligible=not reasons, reasons=tuple(dict.fromkeys(reasons)))
