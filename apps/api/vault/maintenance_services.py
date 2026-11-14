import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .lifecycle import purge_time_is_eligible
from .maintenance import MaintenancePrincipal, digest_parameters
from .models import (
    VaultBackupSet,
    VaultMaintenanceHold,
    VaultMaintenanceJournal,
    VaultMaintenanceOperation,
    VaultRecord,
)


class MaintenanceStateError(Exception):
    pass


def audit_maintenance_denial():
    record_denied_event_best_effort(
        action=SecurityAuditEvent.Action.VAULT_MAINTENANCE_DENIED,
        actor_user_id=None,
        target_type=SecurityAuditEvent.TargetType.VAULT_MAINTENANCE_OPERATION,
        target_id=None,
    )


def _version():
    return getattr(settings, "APPLICATION_COMMIT", "unknown")[:64]


def transition_operation(operation, state, *, failure_code=None, now=None):
    allowed = {
        VaultMaintenanceOperation.State.PENDING: {VaultMaintenanceOperation.State.RUNNING,
                                                  VaultMaintenanceOperation.State.FAILED},
        VaultMaintenanceOperation.State.RUNNING: {VaultMaintenanceOperation.State.COMPLETED,
                                                  VaultMaintenanceOperation.State.FAILED},
    }
    if state not in allowed.get(operation.state, set()):
        raise MaintenanceStateError("Maintenance operation transition is invalid")
    now = now or timezone.now()
    operation.state = state
    fields = ["state"]
    if state == VaultMaintenanceOperation.State.RUNNING:
        operation.started_at = now
        fields.append("started_at")
    elif state == VaultMaintenanceOperation.State.COMPLETED:
        operation.completed_at = now
        fields.append("completed_at")
    else:
        operation.failed_at = now
        operation.failure_code = failure_code or "operation_failed"
        fields.extend(("failed_at", "failure_code"))
    operation.save(update_fields=fields)
    return operation


def create_hold(*, principal, owner, scope, reason, record=None):
    if not isinstance(principal, MaintenancePrincipal) or "credential.hold.create" not in principal.capabilities:
        raise MaintenanceStateError("Maintenance capability is required")
    parameters = {"ownerId": owner.pk, "recordId": str(record.pk) if record else None,
                  "scope": scope, "reason": reason}
    with transaction.atomic():
        operation = VaultMaintenanceOperation.objects.create(
            operator_id=principal.operator_id,
            capability=VaultMaintenanceOperation.Capability.HOLD_CREATE,
            mode=VaultMaintenanceOperation.Mode.CONTROL,
            parameter_digest=digest_parameters(parameters),
            application_version=_version(), schema_version="vault-hold-v1",
            state=VaultMaintenanceOperation.State.RUNNING, started_at=timezone.now(),
        )
        hold = VaultMaintenanceHold.objects.create(
            scope=scope, owner=owner, record=record, reason=reason,
            created_by_operator_id=principal.operator_id, created_operation=operation,
        )
        operation.state = VaultMaintenanceOperation.State.COMPLETED
        operation.completed_at = timezone.now()
        operation.save(update_fields=("state", "completed_at"))
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_HOLD_CREATED, actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.VAULT_MAINTENANCE_OPERATION,
            target_id=str(operation.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS,
            request_id=str(operation.pk),
        )
    return hold


def release_hold(*, principal, hold):
    if not isinstance(principal, MaintenancePrincipal) or "credential.hold.release" not in principal.capabilities:
        raise MaintenanceStateError("Maintenance capability is required")
    if hold.released_at is not None:
        return hold
    with transaction.atomic():
        locked = VaultMaintenanceHold.objects.select_for_update().get(pk=hold.pk)
        if locked.released_at is not None:
            return locked
        operation = VaultMaintenanceOperation.objects.create(
            operator_id=principal.operator_id,
            capability=VaultMaintenanceOperation.Capability.HOLD_RELEASE,
            mode=VaultMaintenanceOperation.Mode.CONTROL,
            parameter_digest=digest_parameters({"holdId": str(locked.pk)}),
            application_version=_version(), schema_version="vault-hold-v1",
            state=VaultMaintenanceOperation.State.RUNNING, started_at=timezone.now(),
        )
        locked.released_by_operator_id = principal.operator_id
        locked.released_operation = operation
        locked.released_at = timezone.now()
        locked.save(update_fields=("released_by_operator_id", "released_operation", "released_at"))
        operation.state = VaultMaintenanceOperation.State.COMPLETED
        operation.completed_at = timezone.now()
        operation.save(update_fields=("state", "completed_at"))
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_HOLD_RELEASED, actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.VAULT_MAINTENANCE_OPERATION,
            target_id=str(operation.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS,
            request_id=str(operation.pk),
        )
    return locked


def assess_purge(*, principal, owner_id=None, limit=100, now=None):
    """Persist a bounded read-only purge assessment. No credential is changed."""
    if not isinstance(principal, MaintenancePrincipal) or "credential.purge" not in principal.capabilities:
        raise MaintenanceStateError("Maintenance capability is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    now = now or timezone.now()
    parameters = {"ownerId": owner_id, "limit": limit, "evaluatedAt": now.isoformat()}
    with transaction.atomic():
        operation = VaultMaintenanceOperation.objects.create(
            operator_id=principal.operator_id,
            capability=VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE,
            mode=VaultMaintenanceOperation.Mode.DRY_RUN,
            parameter_digest=digest_parameters(parameters), application_version=_version(),
            schema_version="vault-purge-assessment-v1", state=VaultMaintenanceOperation.State.RUNNING,
            started_at=now,
        )
        queryset = VaultRecord.objects.filter(lifecycle=VaultRecord.Lifecycle.DELETED).order_by("owner_id", "id")
        if owner_id is not None:
            queryset = queryset.filter(owner_id=owner_id)
        records = list(queryset[:limit])
        verified_checkpoint = VaultBackupSet.objects.filter(state=VaultBackupSet.State.VERIFIED).exists()
        eligible = 0
        blocked = 0
        for record in records:
            held = VaultMaintenanceHold.objects.filter(owner_id=record.owner_id, released_at__isnull=True).filter(
                models.Q(scope=VaultMaintenanceHold.Scope.OWNER) |
                models.Q(scope=VaultMaintenanceHold.Scope.RECORD, record=record)
            ).exists()
            conflict = VaultMaintenanceJournal.objects.filter(
                models.Q(owner_id=record.owner_id) | models.Q(record=record),
                state__in=(VaultMaintenanceJournal.State.PENDING, VaultMaintenanceJournal.State.RUNNING,
                           VaultMaintenanceJournal.State.PAUSED),
            ).exists()
            if purge_time_is_eligible(record, now=now) and not held and not conflict and verified_checkpoint:
                eligible += 1
            else:
                blocked += 1
        operation.eligible_count = eligible
        operation.blocked_count = blocked
        operation.state = VaultMaintenanceOperation.State.COMPLETED
        operation.completed_at = timezone.now()
        operation.save(update_fields=("eligible_count", "blocked_count", "state", "completed_at"))
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_PURGE_ASSESSED, actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.VAULT_MAINTENANCE_OPERATION,
            target_id=str(operation.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS,
            request_id=str(operation.pk),
        )
    return operation


# Import kept local to make the read-only evaluator's query construction explicit.
from django.db import models  # noqa: E402
