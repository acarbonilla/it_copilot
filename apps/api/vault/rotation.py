import os
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User

from .crypto import EncryptionContext, EncryptionEnvelope, WrappedKeyEnvelope, decrypt, encrypt, unwrap_dek, wrap_dek
from .keys import active_kek_generation, load_kek
from .maintenance import MaintenancePrincipal, digest_parameters
from .models import (
    DEK_BYTES, VaultBackupSet, VaultMaintenanceConfirmation, VaultMaintenanceGuard, VaultMaintenanceHold,
    VaultMaintenanceJournal, VaultMaintenanceOperation, VaultOwnerKey, VaultRecord,
)


MAX_ROTATION_RECORDS = 100
ROTATION_SCHEMA = "vault-key-rotation-v1"
UNFINISHED = (VaultMaintenanceJournal.State.PENDING, VaultMaintenanceJournal.State.RUNNING,
              VaultMaintenanceJournal.State.PAUSED)


class RotationDenied(Exception):
    pass


class OperationalRotationDisabled(RotationDenied):
    pass


@dataclass(frozen=True)
class RetirementAssessment:
    eligible: bool
    reason_codes: tuple[str, ...]


def _now():
    return timezone.now()


def _require(principal, capability, *, at):
    if (not isinstance(principal, MaintenancePrincipal) or capability not in principal.capabilities or
            principal.expires_at <= at):
        raise RotationDenied("Key rotation denied")


def _is_disposable_database():
    name = str(connection.settings_dict.get("NAME", ""))
    if connection.vendor == "sqlite":
        return name == ":memory:" or name.startswith("file:memorydb_")
    configured = os.environ.get("MYSQL_DATABASE", "")
    return bool(configured) and name == f"test_{configured}"


def _require_disposable_database():
    if not _is_disposable_database():
        raise OperationalRotationDisabled("Operational key rotation is not authorized")


def _wrapped(row):
    return WrappedKeyEnvelope(row.envelope_version, row.key_version, bytes(row.nonce),
                              bytes(row.wrapped_dek), bytes(row.tag))


def _record_envelope(row):
    return EncryptionEnvelope(row.envelope_version, row.schema_version, row.key_version, bytes(row.nonce),
                              bytes(row.ciphertext), bytes(row.tag))


def _context(row):
    return EncryptionContext(row.owner_id, str(row.pk), row.credential_type, row.schema_version)


def _blocked_owner(owner_id, *, exclude_operation_id=None):
    journals = VaultMaintenanceJournal.objects.filter(owner_id=owner_id, state__in=UNFINISHED)
    scoped = VaultMaintenanceJournal.objects.filter(purge_scopes__owner_id=owner_id, state__in=UNFINISHED)
    if exclude_operation_id is not None:
        journals = journals.exclude(operation_id=exclude_operation_id)
        scoped = scoped.exclude(operation_id=exclude_operation_id)
    return (VaultMaintenanceHold.objects.filter(owner_id=owner_id, released_at__isnull=True).exists() or
            journals.exists() or scoped.exists())


def _backup_in_progress():
    return VaultBackupSet.objects.filter(state__in=(VaultBackupSet.State.PREPARING,
                                                     VaultBackupSet.State.FILES_COMPLETE)).exists()


def _new_operation(*, principal, capability, mode, parameter_digest, state, parent=None, eligible=0, blocked=0,
                   now=None):
    now = now or _now()
    return VaultMaintenanceOperation.objects.create(
        operator_id=principal.operator_id, capability=capability, mode=mode,
        parameter_digest=parameter_digest, parent_dry_run=parent,
        application_version=getattr(settings, "APPLICATION_COMMIT", "unknown")[:64],
        schema_version=ROTATION_SCHEMA, state=state, eligible_count=eligible, blocked_count=blocked,
        started_at=now if state == VaultMaintenanceOperation.State.RUNNING else None,
        completed_at=now if state == VaultMaintenanceOperation.State.COMPLETED else None,
    )


def assess_kek_rotation(*, principal, source_generation, target_generation):
    now = _now(); _require(principal, "key.rotate.kek", at=now)
    if (isinstance(source_generation, bool) or not isinstance(source_generation, int) or source_generation <= 0 or
            isinstance(target_generation, bool) or not isinstance(target_generation, int) or target_generation <= 0 or
            source_generation == target_generation or target_generation != active_kek_generation()):
        raise RotationDenied("Key rotation denied")
    load_kek(source_generation); load_kek(target_generation)
    rows = list(VaultOwnerKey.objects.filter(kek_generation=source_generation).order_by("owner_id", "key_version")[:MAX_ROTATION_RECORDS + 1])
    if len(rows) > MAX_ROTATION_RECORDS:
        raise RotationDenied("Key rotation batch limit exceeded")
    candidates = [{"ownerId": row.owner_id, "keyVersion": row.key_version, "rowId": row.pk} for row in rows]
    digest = digest_parameters({"kind": "KEK", "sourceGeneration": source_generation,
                                "targetGeneration": target_generation, "candidates": candidates})
    blocked = len(rows) if _backup_in_progress() else sum(_blocked_owner(row.owner_id) for row in rows)
    return _new_operation(principal=principal, capability=VaultMaintenanceOperation.Capability.ROTATE_KEK,
                          mode=VaultMaintenanceOperation.Mode.DRY_RUN, parameter_digest=digest,
                          state=VaultMaintenanceOperation.State.COMPLETED,
                          eligible=len(rows) - blocked, blocked=blocked, now=now)


def assess_dek_rotation(*, principal, owner_id):
    now = _now(); _require(principal, "key.rotate.dek", at=now)
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id <= 0:
        raise RotationDenied("Key rotation denied")
    records = list(VaultRecord.objects.filter(owner_id=owner_id).exclude(lifecycle=VaultRecord.Lifecycle.PURGED)
                   .order_by("id")[:MAX_ROTATION_RECORDS + 1])
    if len(records) > MAX_ROTATION_RECORDS:
        raise RotationDenied("Key rotation batch limit exceeded")
    candidates = [{"recordId": str(row.pk), "revision": row.revision, "keyVersion": row.key_version,
                   "lifecycle": row.lifecycle} for row in records]
    digest = digest_parameters({"kind": "DEK", "ownerId": owner_id, "candidates": candidates})
    blocked = len(records) if _backup_in_progress() or _blocked_owner(owner_id) else 0
    return _new_operation(principal=principal, capability=VaultMaintenanceOperation.Capability.ROTATE_DEK,
                          mode=VaultMaintenanceOperation.Mode.DRY_RUN, parameter_digest=digest,
                          state=VaultMaintenanceOperation.State.COMPLETED,
                          eligible=len(records) - blocked, blocked=blocked, now=now)


def prepare_rotation(*, principal, confirming_principal, dry_run, ttl=timedelta(minutes=10)):
    now = _now(); _require(principal, dry_run.capability, at=now); _require(confirming_principal, dry_run.capability, at=now)
    if (principal.operator_id == confirming_principal.operator_id or dry_run.mode != VaultMaintenanceOperation.Mode.DRY_RUN or
            dry_run.state != VaultMaintenanceOperation.State.COMPLETED or dry_run.blocked_count or dry_run.eligible_count <= 0 or
            not timedelta(seconds=1) <= ttl <= timedelta(hours=1)):
        raise RotationDenied("Key rotation denied")
    with transaction.atomic():
        locked = VaultMaintenanceOperation.objects.select_for_update().get(pk=dry_run.pk)
        if locked.executions.exists():
            raise RotationDenied("Key rotation denied")
        operation = _new_operation(principal=principal, capability=locked.capability,
                                   mode=VaultMaintenanceOperation.Mode.EXECUTE,
                                   parameter_digest=locked.parameter_digest,
                                   state=VaultMaintenanceOperation.State.PENDING, parent=locked, now=now)
        confirmation = VaultMaintenanceConfirmation.objects.create(
            operation=operation, parameter_digest=operation.parameter_digest,
            artifact_digest=digest_parameters({"operationId": str(operation.pk),
                                               "issuer": confirming_principal.operator_id,
                                               "nonce": str(uuid.uuid4())}),
            issued_by_operator_id=confirming_principal.operator_id, expires_at=now + ttl)
        VaultMaintenanceJournal.objects.create(
            operation=operation,
            operation_type=(VaultMaintenanceJournal.OperationType.KEK_ROTATION
                            if locked.capability == VaultMaintenanceOperation.Capability.ROTATE_KEK
                            else VaultMaintenanceJournal.OperationType.DEK_ROTATION),
            state=VaultMaintenanceJournal.State.PENDING)
    return operation, confirmation


def execute_kek_rotation(**kwargs):
    raise OperationalRotationDisabled("Operational key rotation is not authorized")


def execute_dek_rotation(**kwargs):
    raise OperationalRotationDisabled("Operational key rotation is not authorized")


def _lock_and_validate(*, principal, operation_id, capability):
    now = _now(); _require(principal, capability, at=now)
    VaultMaintenanceGuard.objects.select_for_update().get(pk=1)
    operation = VaultMaintenanceOperation.objects.select_for_update().select_related("parent_dry_run").get(pk=operation_id)
    confirmation = VaultMaintenanceConfirmation.objects.select_for_update().get(operation=operation)
    journal = VaultMaintenanceJournal.objects.select_for_update().get(operation=operation)
    if (operation.capability != capability or operation.operator_id != principal.operator_id or
            operation.state != VaultMaintenanceOperation.State.PENDING or journal.state != VaultMaintenanceJournal.State.PENDING or
            confirmation.parameter_digest != operation.parameter_digest or confirmation.consumed_at is not None or
            confirmation.expires_at <= now or not confirmation.issued_by_operator_id or
            confirmation.issued_by_operator_id == "legacy-unattributed" or
            confirmation.issued_by_operator_id == principal.operator_id):
        raise RotationDenied("Key rotation denied")
    _require(principal, capability, at=_now())
    return operation, confirmation, journal


def _complete(operation, confirmation, journal, now):
    confirmation.consumed_at = now; confirmation.save(update_fields=("consumed_at",))
    journal.state = VaultMaintenanceJournal.State.COMPLETED; journal.completed_at = now
    journal.checkpoint_digest = digest_parameters({"operationId": str(operation.pk), "completedAt": now.isoformat()})
    journal.save(update_fields=("state", "completed_at", "checkpoint_digest", "updated_at"))
    operation.state = VaultMaintenanceOperation.State.COMPLETED; operation.started_at = now; operation.completed_at = now
    operation.save(update_fields=("state", "started_at", "completed_at"))


def _execute_disposable_kek_rotation(*, principal, operation_id, source_generation, target_generation):
    _require_disposable_database()
    with transaction.atomic():
        operation, confirmation, journal = _lock_and_validate(
            principal=principal, operation_id=operation_id,
            capability=VaultMaintenanceOperation.Capability.ROTATE_KEK)
        owner_ids = list(VaultOwnerKey.objects.filter(kek_generation=source_generation)
                         .order_by("owner_id").values_list("owner_id", flat=True).distinct())
        list(User.objects.select_for_update().filter(pk__in=owner_ids).order_by("pk"))
        rows = list(VaultOwnerKey.objects.select_for_update().filter(kek_generation=source_generation)
                    .order_by("owner_id", "key_version"))
        candidates = [{"ownerId": row.owner_id, "keyVersion": row.key_version, "rowId": row.pk} for row in rows]
        expected = digest_parameters({"kind": "KEK", "sourceGeneration": source_generation,
                                      "targetGeneration": target_generation, "candidates": candidates})
        if (not rows or len(rows) > MAX_ROTATION_RECORDS or operation.parameter_digest != expected or
                target_generation != active_kek_generation() or _backup_in_progress() or
                any(_blocked_owner(row.owner_id, exclude_operation_id=operation.pk) for row in rows)):
            raise RotationDenied("Key rotation denied")
        source, target = load_kek(source_generation), load_kek(target_generation)
        for row in rows:
            dek = unwrap_dek(kek=source, envelope=_wrapped(row), owner_id=row.owner_id)
            wrapped = wrap_dek(kek=target, dek=dek, owner_id=row.owner_id, key_version=row.key_version)
            if unwrap_dek(kek=target, envelope=wrapped, owner_id=row.owner_id) != dek:
                raise RotationDenied("Key rotation verification failed")
            row.kek_generation, row.nonce, row.wrapped_dek, row.tag = (
                target_generation, wrapped.nonce, wrapped.wrapped_dek, wrapped.tag)
            row.save(update_fields=("kek_generation", "nonce", "wrapped_dek", "tag"))
        journal.old_key_version = source_generation; journal.new_key_version = target_generation
        _complete(operation, confirmation, journal, _now())
    return operation


def _execute_disposable_dek_rotation(*, principal, operation_id, owner_id):
    _require_disposable_database()
    with transaction.atomic():
        operation, confirmation, journal = _lock_and_validate(
            principal=principal, operation_id=operation_id,
            capability=VaultMaintenanceOperation.Capability.ROTATE_DEK)
        owner = User.objects.select_for_update().get(pk=owner_id)
        key_rows = list(VaultOwnerKey.objects.select_for_update().filter(owner=owner).order_by("key_version"))
        records = list(VaultRecord.objects.select_for_update().filter(owner=owner)
                       .exclude(lifecycle=VaultRecord.Lifecycle.PURGED).order_by("id"))
        candidates = [{"recordId": str(row.pk), "revision": row.revision, "keyVersion": row.key_version,
                       "lifecycle": row.lifecycle} for row in records]
        expected = digest_parameters({"kind": "DEK", "ownerId": owner_id, "candidates": candidates})
        active = next((row for row in key_rows if row.active_slot is True), None)
        if (not records or len(records) > MAX_ROTATION_RECORDS or active is None or operation.parameter_digest != expected or
                _backup_in_progress() or _blocked_owner(owner_id, exclude_operation_id=operation.pk)):
            raise RotationDenied("Key rotation denied")
        by_version = {row.key_version: row for row in key_rows}
        plaintexts = []
        for row in records:
            key_row = by_version.get(row.key_version)
            if key_row is None:
                raise RotationDenied("Key rotation denied")
            old_dek = unwrap_dek(kek=load_kek(key_row.kek_generation), envelope=_wrapped(key_row), owner_id=owner_id)
            plaintexts.append((row, decrypt(dek=old_dek, envelope=_record_envelope(row), context=_context(row))))
        new_version = max(by_version) + 1
        new_dek = os.urandom(DEK_BYTES); generation = active_kek_generation()
        wrapped = wrap_dek(kek=load_kek(generation), dek=new_dek, owner_id=owner_id, key_version=new_version)
        now = _now(); active.active_slot = None; active.retired_at = now
        active.save(update_fields=("active_slot", "retired_at"))
        VaultOwnerKey.objects.create(owner=owner, key_version=new_version, kek_generation=generation,
                                     envelope_version=wrapped.envelope_version, nonce=wrapped.nonce,
                                     wrapped_dek=wrapped.wrapped_dek, tag=wrapped.tag)
        for row, plaintext in plaintexts:
            envelope = encrypt(dek=new_dek, plaintext=plaintext, context=_context(row), key_version=new_version)
            if decrypt(dek=new_dek, envelope=envelope, context=_context(row)) != plaintext:
                raise RotationDenied("Key rotation verification failed")
            row.key_version, row.nonce, row.ciphertext, row.tag = (
                new_version, envelope.nonce, envelope.ciphertext, envelope.tag)
            row.revision += 1
            row.save(update_fields=("key_version", "nonce", "ciphertext", "tag", "revision", "updated_at"))
        journal.owner = owner; journal.old_key_version = active.key_version; journal.new_key_version = new_version
        _complete(operation, confirmation, journal, now)
    return operation


def assess_key_retirement(*, principal, owner_id, key_version):
    now = _now(); _require(principal, "key.retire.online", at=now)
    reasons = set()
    row = VaultOwnerKey.objects.filter(owner_id=owner_id, key_version=key_version).first()
    if row is None:
        return RetirementAssessment(False, ("KEY_NOT_FOUND",))
    if row.active_slot is True: reasons.add("ACTIVE_KEY")
    if VaultRecord.objects.filter(owner_id=owner_id, key_version=key_version).exists(): reasons.add("RECORD_REFERENCE")
    if VaultMaintenanceHold.objects.filter(owner_id=owner_id, released_at__isnull=True).exists(): reasons.add("ACTIVE_HOLD")
    if VaultMaintenanceJournal.objects.filter(Q(owner_id=owner_id) | Q(purge_scopes__owner_id=owner_id),
                                               state__in=UNFINISHED).exists(): reasons.add("UNFINISHED_JOURNAL")
    if VaultBackupSet.objects.exclude(state=VaultBackupSet.State.FAILED).exists(): reasons.add("BACKUP_DEPENDENCY_UNKNOWN")
    try: load_kek(row.kek_generation)
    except Exception: reasons.add("HISTORICAL_KEK_MISSING")
    if not VaultBackupSet.objects.filter(state=VaultBackupSet.State.VERIFIED,
                                         recovery_evidence__invalidated_at__isnull=True,
                                         recovery_evidence__expires_at__gt=now,
                                         recovery_evidence__cleanup_complete=True).exists():
        reasons.add("RECOVERY_EVIDENCE_UNAVAILABLE")
    return RetirementAssessment(not reasons, tuple(sorted(reasons)))
