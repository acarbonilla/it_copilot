import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.maintenance import MaintenancePrincipal
from vault.models import (
    VaultBackupSet,
    VaultMaintenanceHold,
    VaultMaintenanceGuard,
    VaultMaintenanceOperation,
    VaultRecord,
)
from vault.purge import (
    BackupQualificationUnavailable,
    ControlledPurgeDenied,
    PurgeCandidate,
    assess_purge_candidates,
    canonicalize_candidates,
    execute_purge,
    prepare_purge_execution,
    purge_parameter_digest,
)


class ControlledPurgeTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        VaultMaintenanceGuard.objects.get_or_create(pk=1)
        self.owner = User.objects.create_user("purge-owner@example.test", "password")
        self.other_owner = User.objects.create_user("purge-other@example.test", "password")
        self.record = self._deleted_record(self.owner, "First")
        self.second = self._deleted_record(self.other_owner, "Second")
        expiry = self.now + timedelta(hours=1)
        self.executor = MaintenancePrincipal("purge-executor", frozenset({"credential.purge"}), expiry)
        self.confirmer = MaintenancePrincipal("purge-confirmer", frozenset({"credential.purge"}), expiry)
        self.backup = self._generic_verified_backup()

    def _deleted_record(self, owner, label):
        return VaultRecord.objects.create(
            owner=owner, credential_type=VaultRecord.CredentialType.LOGIN, label=label,
            service_label="Service", origin="https://example.test", key_version=1,
            nonce=b"n" * 12, ciphertext=b"opaque-ciphertext", tag=b"t" * 16,
            lifecycle=VaultRecord.Lifecycle.DELETED,
            deleted_at=self.now - timedelta(days=31), restore_expires_at=self.now - timedelta(days=1),
        )

    def _generic_verified_backup(self):
        operation = VaultMaintenanceOperation.objects.create(
            operator_id="backup-operator", capability=VaultMaintenanceOperation.Capability.BACKUP_CREATE,
            mode=VaultMaintenanceOperation.Mode.CONTROL, parameter_digest="a" * 64,
            application_version="test", schema_version="test", state=VaultMaintenanceOperation.State.COMPLETED,
            started_at=self.now, completed_at=self.now,
        )
        return VaultBackupSet.objects.create(
            operation=operation, database_snapshot_id=uuid.uuid4(), manifest_id=uuid.uuid4(),
            protected_bundle_id=uuid.uuid4(), snapshot_digest="b" * 64, bundle_digest="c" * 64,
            application_version="test", schema_version="test", key_inventory_digest="d" * 64,
            retention_state="RETAINED", hold_summary="none", manifest_auth_key_id="test-key",
            state=VaultBackupSet.State.VERIFIED, verification_evidence_digest="e" * 64,
            verified_at=self.now,
        )

    def _candidate(self, record=None):
        record = record or self.record
        return PurgeCandidate(record.pk, record.owner_id, record.revision)

    def _prepared(self, candidates=None):
        candidates = candidates or [self._candidate()]
        dry_run = assess_purge_candidates(
            principal=self.executor, candidates=candidates, backup_checkpoint_id=self.backup.pk, now=self.now)
        operation, confirmation = prepare_purge_execution(
            principal=self.executor, confirming_principal=self.confirmer, dry_run=dry_run,
            candidates=candidates, backup_checkpoint_id=self.backup.pk, now=self.now)
        return candidates, dry_run, operation, confirmation

    def test_candidates_are_bounded_unique_and_deterministically_bound(self):
        first = self._candidate(self.record)
        second = self._candidate(self.second)
        self.assertEqual(canonicalize_candidates([second, first]), canonicalize_candidates([first, second]))
        with self.assertRaises(ControlledPurgeDenied):
            canonicalize_candidates([first, first])
        with self.assertRaises(ControlledPurgeDenied):
            canonicalize_candidates([])
        with self.assertRaises(ControlledPurgeDenied):
            canonicalize_candidates([first] * 101)
        dry_run_id = uuid.uuid4()
        original = purge_parameter_digest(
            candidates=[first], dry_run_id=dry_run_id, backup_checkpoint_id=self.backup.pk)
        changed = purge_parameter_digest(
            candidates=[PurgeCandidate(first.credential_id, first.owner_id, first.expected_revision + 1)],
            dry_run_id=dry_run_id, backup_checkpoint_id=self.backup.pk)
        self.assertNotEqual(original, changed)

    def test_assessment_is_read_only_and_changed_set_cannot_prepare_execution(self):
        candidate = self._candidate()
        dry_run = assess_purge_candidates(
            principal=self.executor, candidates=[candidate], backup_checkpoint_id=self.backup.pk, now=self.now)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)
        self.assertEqual(dry_run.eligible_count, 1)
        self.assertEqual(dry_run.blocked_count, 0)
        altered = PurgeCandidate(candidate.credential_id, candidate.owner_id, candidate.expected_revision + 1)
        with self.assertRaises(ControlledPurgeDenied):
            prepare_purge_execution(
                principal=self.executor, confirming_principal=self.confirmer, dry_run=dry_run,
                candidates=[altered], backup_checkpoint_id=self.backup.pk, now=self.now)

    def test_confirmation_requires_independent_capable_principal_and_is_bound(self):
        candidate = self._candidate()
        dry_run = assess_purge_candidates(
            principal=self.executor, candidates=[candidate], backup_checkpoint_id=self.backup.pk, now=self.now)
        with self.assertRaises(ControlledPurgeDenied):
            prepare_purge_execution(
                principal=self.executor, confirming_principal=self.executor, dry_run=dry_run,
                candidates=[candidate], backup_checkpoint_id=self.backup.pk, now=self.now)
        operation, confirmation = prepare_purge_execution(
            principal=self.executor, confirming_principal=self.confirmer, dry_run=dry_run,
            candidates=[candidate], backup_checkpoint_id=self.backup.pk, now=self.now)
        self.assertEqual(confirmation.operation_id, operation.pk)
        self.assertEqual(confirmation.parameter_digest, operation.parameter_digest)
        self.assertEqual(confirmation.issued_by_operator_id, self.confirmer.operator_id)
        self.assertIsNone(confirmation.consumed_at)

    def test_generic_verified_backup_never_qualifies_operational_execution(self):
        candidates, _dry_run, operation, confirmation = self._prepared()
        with self.assertRaises(BackupQualificationUnavailable):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db(); operation.refresh_from_db(); confirmation.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)
        self.assertIsNotNone(self.record.ciphertext)
        self.assertEqual(operation.state, VaultMaintenanceOperation.State.PENDING)
        self.assertIsNone(confirmation.consumed_at)
        self.assertFalse(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_PURGE_EXECUTED).exists())

    def test_stale_revision_and_expired_confirmation_fail_before_backup_gate(self):
        candidates, _dry_run, operation, _confirmation = self._prepared()
        self.record.revision += 1
        self.record.save(update_fields=("revision",))
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)

        candidate = self._candidate()
        candidates, _dry_run, operation, _confirmation = self._prepared([candidate])
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(
                principal=self.executor, operation_id=operation.pk, candidates=candidates,
                now=self.now + timedelta(minutes=11))

    def test_active_hold_rejects_entire_batch_without_partial_transition(self):
        candidates = [self._candidate(self.record), self._candidate(self.second)]
        _candidates, _dry_run, operation, _confirmation = self._prepared(candidates)
        hold_operation = VaultMaintenanceOperation.objects.create(
            operator_id="hold-operator", capability=VaultMaintenanceOperation.Capability.HOLD_CREATE,
            mode=VaultMaintenanceOperation.Mode.CONTROL, parameter_digest="f" * 64,
            application_version="test", schema_version="test", state=VaultMaintenanceOperation.State.COMPLETED,
            started_at=self.now, completed_at=self.now,
        )
        VaultMaintenanceHold.objects.create(
            scope=VaultMaintenanceHold.Scope.RECORD, owner=self.second.owner, record=self.second,
            reason=VaultMaintenanceHold.Reason.LEGAL, created_by_operator_id="hold-operator",
            created_operation=hold_operation,
        )
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db(); self.second.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)
        self.assertEqual(self.second.lifecycle, VaultRecord.Lifecycle.DELETED)

    def test_expired_or_missing_capability_principal_is_denied(self):
        expired = MaintenancePrincipal(
            "expired", frozenset({"credential.purge"}), self.now - timedelta(seconds=1))
        missing = MaintenancePrincipal(
            "underprivileged", frozenset({"recovery.verify"}), self.now + timedelta(hours=1))
        for principal in (expired, missing, None):
            with self.subTest(principal=principal):
                with self.assertRaises(ControlledPurgeDenied):
                    assess_purge_candidates(
                        principal=principal, candidates=[self._candidate()],
                        backup_checkpoint_id=self.backup.pk, now=self.now)
        self.assertEqual(VaultMaintenanceOperation.objects.filter(
            capability=VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE).count(), 0)

    def test_retention_boundary_is_revalidated_at_execution(self):
        record = VaultRecord.objects.create(
            owner=self.owner, credential_type=VaultRecord.CredentialType.LOGIN, label="Boundary",
            service_label="Service", origin="https://example.test", key_version=1,
            nonce=b"n" * 12, ciphertext=b"opaque", tag=b"t" * 16,
            lifecycle=VaultRecord.Lifecycle.DELETED, deleted_at=self.now - timedelta(days=1),
            restore_expires_at=self.now + timedelta(seconds=1),
        )
        candidate = self._candidate(record)
        dry_run = assess_purge_candidates(
            principal=self.executor, candidates=[candidate], backup_checkpoint_id=self.backup.pk,
            now=self.now + timedelta(seconds=1))
        operation, _confirmation = prepare_purge_execution(
            principal=self.executor, confirming_principal=self.confirmer, dry_run=dry_run,
            candidates=[candidate], backup_checkpoint_id=self.backup.pk, now=self.now)
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(
                principal=self.executor, operation_id=operation.pk, candidates=[candidate], now=self.now)
        record.refresh_from_db()
        self.assertEqual(record.lifecycle, VaultRecord.Lifecycle.DELETED)

    def test_candidate_substitution_and_consumed_confirmation_are_denied(self):
        candidates, _dry_run, operation, confirmation = self._prepared()
        substituted = [PurgeCandidate(self.second.pk, self.second.owner_id, self.second.revision)]
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(
                principal=self.executor, operation_id=operation.pk, candidates=substituted, now=self.now)
        confirmation.consumed_at = self.now
        confirmation.save(update_fields=("consumed_at",))
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)

    def test_conflicting_unfinished_journal_denies_execution(self):
        candidates, _dry_run, operation, _confirmation = self._prepared()
        conflict_operation = VaultMaintenanceOperation.objects.create(
            operator_id="other-operator", capability=VaultMaintenanceOperation.Capability.ROTATE_DEK,
            mode=VaultMaintenanceOperation.Mode.CONTROL, parameter_digest="1" * 64,
            application_version="test", schema_version="test", state=VaultMaintenanceOperation.State.RUNNING,
            started_at=self.now,
        )
        from vault.models import VaultMaintenanceJournal
        VaultMaintenanceJournal.objects.create(
            operation=conflict_operation, operation_type=VaultMaintenanceJournal.OperationType.DEK_ROTATION,
            owner=self.owner, state=VaultMaintenanceJournal.State.RUNNING,
        )
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)

    def test_completed_operation_cannot_be_replayed(self):
        candidates, _dry_run, operation, _confirmation = self._prepared()
        operation.state = VaultMaintenanceOperation.State.COMPLETED
        operation.completed_at = self.now
        operation.save(update_fields=("state", "completed_at"))
        with self.assertRaises(ControlledPurgeDenied):
            execute_purge(principal=self.executor, operation_id=operation.pk, candidates=candidates, now=self.now)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)


class ControlledPurgeMySQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative purge concurrency evidence")
        self.now = timezone.now()
        from vault.models import VaultMaintenanceGuard
        VaultMaintenanceGuard.objects.get_or_create(pk=1)
        self.owner = User.objects.create_user("purge-race@example.test", "password")
        self.record = VaultRecord.objects.create(
            owner=self.owner, credential_type=VaultRecord.CredentialType.LOGIN, label="Race",
            service_label="Service", origin="https://example.test", key_version=1,
            nonce=b"n" * 12, ciphertext=b"opaque", tag=b"t" * 16,
            lifecycle=VaultRecord.Lifecycle.DELETED, deleted_at=self.now - timedelta(days=31),
            restore_expires_at=self.now - timedelta(days=1),
        )
        backup_operation = VaultMaintenanceOperation.objects.create(
            operator_id="backup-operator", capability=VaultMaintenanceOperation.Capability.BACKUP_CREATE,
            mode=VaultMaintenanceOperation.Mode.CONTROL, parameter_digest="a" * 64,
            application_version="test", schema_version="test", state=VaultMaintenanceOperation.State.COMPLETED,
            started_at=self.now, completed_at=self.now,
        )
        self.backup = VaultBackupSet.objects.create(
            operation=backup_operation, database_snapshot_id=uuid.uuid4(), manifest_id=uuid.uuid4(),
            protected_bundle_id=uuid.uuid4(), snapshot_digest="b" * 64, bundle_digest="c" * 64,
            application_version="test", schema_version="test", key_inventory_digest="d" * 64,
            retention_state="RETAINED", hold_summary="none", manifest_auth_key_id="test-key",
            state=VaultBackupSet.State.VERIFIED, verification_evidence_digest="e" * 64,
            verified_at=self.now,
        )
        expiry = self.now + timedelta(hours=1)
        self.principal = MaintenancePrincipal("race-executor", frozenset({"credential.purge"}), expiry)
        confirmer = MaintenancePrincipal("race-confirmer", frozenset({"credential.purge"}), expiry)
        self.candidates = [PurgeCandidate(self.record.pk, self.owner.pk, self.record.revision)]
        dry_run = assess_purge_candidates(
            principal=self.principal, candidates=self.candidates,
            backup_checkpoint_id=self.backup.pk, now=self.now)
        self.operation, _confirmation = prepare_purge_execution(
            principal=self.principal, confirming_principal=confirmer, dry_run=dry_run,
            candidates=self.candidates, backup_checkpoint_id=self.backup.pk, now=self.now)

    def test_concurrent_duplicate_attempts_both_fail_closed_without_transition(self):
        operation_id = self.operation.pk

        def attempt():
            close_old_connections()
            try:
                execute_purge(
                    principal=self.principal, operation_id=operation_id,
                    candidates=self.candidates, now=self.now)
            except ControlledPurgeDenied as exc:
                return type(exc).__name__
            finally:
                close_old_connections()
            return "unexpected-success"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: attempt(), range(2)))
        self.assertEqual(results.count("unexpected-success"), 0)
        self.record.refresh_from_db(); self.operation.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)
        self.assertEqual(self.operation.state, VaultMaintenanceOperation.State.PENDING)
        self.assertFalse(SecurityAuditEvent.objects.filter(
            action=SecurityAuditEvent.Action.VAULT_PURGE_EXECUTED).exists())
