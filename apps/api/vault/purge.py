import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event

from .lifecycle import purge_time_is_eligible
from .maintenance import MaintenancePrincipal, digest_parameters
from .models import (
    VaultBackupSet,
    VaultMaintenanceConfirmation,
    VaultMaintenanceGuard,
    VaultMaintenanceHold,
    VaultMaintenanceJournal,
    VaultMaintenanceOperation,
    VaultOwnerKey,
    VaultPurgeJournalScope,
    VaultRecord,
)
from .qualification import QualificationDenied, qualify_verified_backup


PURGE_SCHEMA_VERSION = "vault-controlled-purge-v1"
MAX_PURGE_BATCH = 100


class ControlledPurgeDenied(Exception):
    """Fixed failure boundary; callers must not expose internal eligibility details."""


class BackupQualificationUnavailable(ControlledPurgeDenied):
    """T02C-3 has not supplied genuine operation-matched recovery evidence."""


class OperationalPurgeDisabled(ControlledPurgeDenied):
    """Independent TTDM boundary: evidence never enables operational execution in T02C-3."""


@dataclass(frozen=True, order=True)
class PurgeCandidate:
    credential_id: uuid.UUID
    owner_id: int
    expected_revision: int


def canonicalize_candidates(candidates):
    if not isinstance(candidates, (list, tuple)) or not 1 <= len(candidates) <= MAX_PURGE_BATCH:
        raise ControlledPurgeDenied("Controlled purge denied")
    canonical = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, PurgeCandidate):
            raise ControlledPurgeDenied("Controlled purge denied")
        try:
            record_id = uuid.UUID(str(candidate.credential_id))
        except (ValueError, TypeError, AttributeError):
            raise ControlledPurgeDenied("Controlled purge denied") from None
        if (isinstance(candidate.owner_id, bool) or not isinstance(candidate.owner_id, int) or candidate.owner_id <= 0 or
                isinstance(candidate.expected_revision, bool) or not isinstance(candidate.expected_revision, int) or
                candidate.expected_revision <= 0 or record_id in seen):
            raise ControlledPurgeDenied("Controlled purge denied")
        seen.add(record_id)
        canonical.append(PurgeCandidate(record_id, candidate.owner_id, candidate.expected_revision))
    return tuple(sorted(canonical, key=lambda item: (item.owner_id, item.credential_id.hex)))


def purge_parameter_digest(*, candidates, dry_run_id, backup_checkpoint_id):
    canonical = canonicalize_candidates(candidates)
    try:
        dry_run_id = uuid.UUID(str(dry_run_id))
        backup_checkpoint_id = uuid.UUID(str(backup_checkpoint_id))
    except (ValueError, TypeError, AttributeError):
        raise ControlledPurgeDenied("Controlled purge denied") from None
    return digest_parameters({
        "applicationVersion": getattr(settings, "APPLICATION_COMMIT", "unknown")[:64],
        "backupCheckpointId": str(backup_checkpoint_id),
        "batchLimit": MAX_PURGE_BATCH,
        "candidates": [{
            "credentialId": str(item.credential_id),
            "expectedRevision": item.expected_revision,
            "ownerId": item.owner_id,
        } for item in canonical],
        "dryRunId": str(dry_run_id),
        "operationType": "credential.purge",
        "schemaVersion": PURGE_SCHEMA_VERSION,
    })


def _trusted_now():
    """Production authority clock. Tests patch this function; callers cannot supply time."""
    return timezone.now()


def _require_principal(principal, *, at=None):
    if not isinstance(principal, MaintenancePrincipal) or "credential.purge" not in principal.capabilities:
        raise ControlledPurgeDenied("Controlled purge denied")
    if principal.expires_at <= (at or _trusted_now()):
        raise ControlledPurgeDenied("Controlled purge denied")


def _active_hold_exists(record):
    return VaultMaintenanceHold.objects.filter(owner_id=record.owner_id, released_at__isnull=True).filter(
        Q(scope=VaultMaintenanceHold.Scope.OWNER) |
        Q(scope=VaultMaintenanceHold.Scope.RECORD, record_id=record.pk)
    ).exists()


def _conflicting_journal_exists(record, operation=None):
    query = VaultMaintenanceJournal.objects.filter(
        Q(owner_id=record.owner_id) | Q(record_id=record.pk) |
        Q(purge_scopes__owner_id=record.owner_id) | Q(purge_scopes__record_id=record.pk) |
        Q(operation_type=VaultMaintenanceJournal.OperationType.PURGE, owner__isnull=True, record__isnull=True,
          purge_scopes__isnull=True),
        state__in=(VaultMaintenanceJournal.State.PENDING, VaultMaintenanceJournal.State.RUNNING,
                   VaultMaintenanceJournal.State.PAUSED),
    )
    if operation is not None:
        query = query.exclude(operation=operation)
    return query.distinct().exists()


def assess_purge_candidates(*, principal, candidates, backup_checkpoint_id):
    """Create a candidate-bound read-only assessment. It never qualifies backup or mutates a credential."""
    now = _trusted_now()
    _require_principal(principal, at=now)
    canonical = canonicalize_candidates(candidates)
    operation_id = uuid.uuid4()
    parameter_digest = purge_parameter_digest(
        candidates=canonical, dry_run_id=operation_id, backup_checkpoint_id=backup_checkpoint_id)
    with transaction.atomic():
        operation = VaultMaintenanceOperation.objects.create(
            id=operation_id, operator_id=principal.operator_id,
            capability=VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE,
            mode=VaultMaintenanceOperation.Mode.DRY_RUN,
            parameter_digest=parameter_digest, backup_checkpoint_id=backup_checkpoint_id,
            application_version=getattr(settings, "APPLICATION_COMMIT", "unknown")[:64],
            schema_version=PURGE_SCHEMA_VERSION,
            state=VaultMaintenanceOperation.State.RUNNING, started_at=now,
        )
        records = {record.pk: record for record in VaultRecord.objects.filter(
            pk__in=[item.credential_id for item in canonical])}
        eligible = 0
        for candidate in canonical:
            record = records.get(candidate.credential_id)
            if (record is not None and record.owner_id == candidate.owner_id and
                    record.revision == candidate.expected_revision and purge_time_is_eligible(record, now=now) and
                    not _active_hold_exists(record) and not _conflicting_journal_exists(record)):
                eligible += 1
        operation.eligible_count = eligible
        operation.blocked_count = len(canonical) - eligible
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


def prepare_purge_execution(*, principal, confirming_principal, dry_run, candidates,
                            backup_checkpoint_id, confirmation_ttl=timedelta(minutes=10)):
    """Prepare immutable execution metadata and an independently authorized one-use confirmation."""
    now = _trusted_now()
    _require_principal(principal, at=now)
    _require_principal(confirming_principal, at=now)
    if principal.operator_id == confirming_principal.operator_id:
        raise ControlledPurgeDenied("Controlled purge denied")
    if not isinstance(confirmation_ttl, timedelta) or not timedelta(seconds=1) <= confirmation_ttl <= timedelta(hours=1):
        raise ControlledPurgeDenied("Controlled purge denied")
    canonical = canonicalize_candidates(candidates)
    with transaction.atomic():
        locked_dry_run = VaultMaintenanceOperation.objects.select_for_update().get(pk=dry_run.pk)
        expected_digest = purge_parameter_digest(
            candidates=canonical, dry_run_id=locked_dry_run.pk, backup_checkpoint_id=backup_checkpoint_id)
        if (locked_dry_run.mode != VaultMaintenanceOperation.Mode.DRY_RUN or
                locked_dry_run.capability != VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE or
                locked_dry_run.state != VaultMaintenanceOperation.State.COMPLETED or
                locked_dry_run.parameter_digest != expected_digest or
                locked_dry_run.backup_checkpoint_id != uuid.UUID(str(backup_checkpoint_id)) or
                locked_dry_run.eligible_count != len(canonical) or locked_dry_run.blocked_count != 0):
            raise ControlledPurgeDenied("Controlled purge denied")
        operation = VaultMaintenanceOperation.objects.create(
            operator_id=principal.operator_id,
            capability=VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE,
            mode=VaultMaintenanceOperation.Mode.EXECUTE, parent_dry_run=locked_dry_run,
            backup_checkpoint_id=backup_checkpoint_id, parameter_digest=expected_digest,
            application_version=getattr(settings, "APPLICATION_COMMIT", "unknown")[:64],
            schema_version=PURGE_SCHEMA_VERSION,
            state=VaultMaintenanceOperation.State.PENDING,
        )
        confirmation = VaultMaintenanceConfirmation.objects.create(
            operation=operation, parameter_digest=expected_digest,
            artifact_digest=hashlib.sha256(
                b"vault-purge-confirmation-v1\x00" + secrets.token_bytes(32)).hexdigest(),
            expires_at=now + confirmation_ttl,
            issued_by_operator_id=confirming_principal.operator_id,
        )
        journal = VaultMaintenanceJournal.objects.create(
            operation=operation, operation_type=VaultMaintenanceJournal.OperationType.PURGE,
            state=VaultMaintenanceJournal.State.PENDING,
        )
        VaultPurgeJournalScope.objects.bulk_create([
            VaultPurgeJournalScope(journal=journal, owner_id=item.owner_id, record_id=item.credential_id,
                                   expected_revision=item.expected_revision)
            for item in canonical
        ])
    return operation, confirmation


def qualify_purge_backup(*, operation, backup_set, candidates):
    """Validate genuine evidence, then enforce the independent operational enablement HOLD."""
    try:
        qualify_verified_backup(operation=operation, backup_set=backup_set, candidates=candidates,
                                trusted_now=_trusted_now())
    except QualificationDenied:
        raise BackupQualificationUnavailable("Qualified purge backup evidence is unavailable") from None
    raise OperationalPurgeDisabled("Operational purge is not authorized")


def _validate_locked_execution(*, operation, confirmation, dry_run, records, candidates, now):
    expected_digest = purge_parameter_digest(
        candidates=candidates, dry_run_id=dry_run.pk, backup_checkpoint_id=operation.backup_checkpoint_id)
    if (operation.mode != VaultMaintenanceOperation.Mode.EXECUTE or
            operation.capability != VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE or
            operation.state != VaultMaintenanceOperation.State.PENDING or
            operation.parameter_digest != expected_digest or operation.parent_dry_run_id != dry_run.pk or
            operation.application_version != getattr(settings, "APPLICATION_COMMIT", "unknown")[:64] or
            operation.schema_version != PURGE_SCHEMA_VERSION or
            dry_run.mode != VaultMaintenanceOperation.Mode.DRY_RUN or
            dry_run.state != VaultMaintenanceOperation.State.COMPLETED or
            dry_run.parameter_digest != expected_digest or
            dry_run.eligible_count != len(candidates) or dry_run.blocked_count != 0 or
            confirmation.operation_id != operation.pk or confirmation.parameter_digest != expected_digest or
            not confirmation.issued_by_operator_id or confirmation.issued_by_operator_id == "legacy-unattributed" or
            confirmation.issued_by_operator_id == operation.operator_id or
            confirmation.consumed_at is not None or confirmation.expires_at <= now or
            len(records) != len(candidates)):
        raise ControlledPurgeDenied("Controlled purge denied")
    by_id = {record.pk: record for record in records}
    for candidate in candidates:
        record = by_id.get(candidate.credential_id)
        if (record is None or record.owner_id != candidate.owner_id or
                record.revision != candidate.expected_revision or
                not purge_time_is_eligible(record, now=now) or _active_hold_exists(record) or
                _conflicting_journal_exists(record, operation=operation)):
            raise ControlledPurgeDenied("Controlled purge denied")


def execute_purge(*, principal, operation_id, candidates):
    """Execute only after T02C-3 qualification. In T02C-1 this always fails before mutation."""
    canonical = canonicalize_candidates(candidates)
    with transaction.atomic():
        VaultMaintenanceGuard.objects.select_for_update().get(pk=1)
        list(User.objects.select_for_update().filter(
            pk__in=sorted({item.owner_id for item in canonical})).order_by("pk"))
        operation = VaultMaintenanceOperation.objects.select_for_update().select_related("parent_dry_run").get(
            pk=operation_id)
        now = _trusted_now()
        _require_principal(principal, at=now)
        if operation.operator_id != principal.operator_id:
            raise ControlledPurgeDenied("Controlled purge denied")
        dry_run = VaultMaintenanceOperation.objects.select_for_update().get(pk=operation.parent_dry_run_id)
        journal = VaultMaintenanceJournal.objects.select_for_update().get(operation=operation)
        confirmation = VaultMaintenanceConfirmation.objects.select_for_update().get(operation=operation)
        list(VaultMaintenanceHold.objects.select_for_update().filter(
            owner_id__in=sorted({item.owner_id for item in canonical}), released_at__isnull=True).order_by("owner_id", "id"))
        backup_set = VaultBackupSet.objects.select_for_update().get(pk=operation.backup_checkpoint_id)
        list(VaultOwnerKey.objects.select_for_update().filter(
            owner_id__in=sorted({item.owner_id for item in canonical})).order_by("owner_id", "key_version"))
        records = list(VaultRecord.objects.select_for_update().filter(
            pk__in=[item.credential_id for item in canonical]).order_by("owner_id", "id"))
        if journal.state != VaultMaintenanceJournal.State.PENDING:
            raise ControlledPurgeDenied("Controlled purge denied")
        _validate_locked_execution(
            operation=operation, confirmation=confirmation, dry_run=dry_run,
            records=records, candidates=canonical, now=now)
        # This authoritative seam has no successful implementation until T02C-3. The code below is intentionally
        # unreachable in T02C-1 and must not be enabled with a flag, fixture, generic VERIFIED row, or test double.
        qualify_purge_backup(operation=operation, backup_set=backup_set, candidates=canonical)

        journal.state = VaultMaintenanceJournal.State.RUNNING
        journal.attempt_count += 1
        journal.save(update_fields=("state", "attempt_count", "updated_at"))
        for record in records:
            record.lifecycle = VaultRecord.Lifecycle.PURGED
            record.label = record.service_label = record.origin = None
            record.schema_version = record.envelope_version = record.key_version = None
            record.nonce = record.ciphertext = record.tag = None
            record.purged_at = now
            record.purge_operation_id = operation.pk
            record.revision += 1
            record.save(update_fields=(
                "lifecycle", "label", "service_label", "origin", "schema_version", "envelope_version",
                "key_version", "nonce", "ciphertext", "tag", "purged_at", "purge_operation_id", "revision",
            ))
        confirmation.consumed_at = now
        confirmation.save(update_fields=("consumed_at",))
        journal.state = VaultMaintenanceJournal.State.COMPLETED
        journal.completed_at = now
        journal.save(update_fields=("state", "completed_at", "updated_at"))
        operation.state = VaultMaintenanceOperation.State.COMPLETED
        operation.eligible_count = len(records)
        operation.completed_at = now
        operation.save(update_fields=("state", "eligible_count", "completed_at"))
        record_critical_event(
            action=SecurityAuditEvent.Action.VAULT_PURGE_EXECUTED, actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.VAULT_MAINTENANCE_OPERATION,
            target_id=str(operation.pk), outcome=SecurityAuditEvent.Outcome.SUCCESS,
            request_id=str(operation.pk),
        )
    return operation
