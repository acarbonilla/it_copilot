import hashlib
import json
import tempfile
import uuid
import os
import shutil
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from vault.backup_contracts import (
    BUNDLE_ALGORITHM, BackupContractError, authenticate_manifest, authenticate_manifest_v2,
    bundle_aad_v2, decrypt_key_bundle, encrypt_key_bundle,
)
from vault.maintenance import MaintenancePrincipal
from vault.models import (
    VaultBackupSet, VaultMaintenanceJournal, VaultMaintenanceOperation, VaultRecord, VaultRecoveryEvidence,
)
from vault.purge import (
    ControlledPurgeDenied, OperationalPurgeDisabled, PurgeCandidate, assess_purge_candidates,
    execute_purge, prepare_purge_execution,
)
from vault.qualification import candidate_set_digest, owner_set_digest, qualify_verified_backup
from vault.recovery import RecoveryVerificationError, require_disposable_database
from vault.recovery import restore_disposable_snapshot
from vault.snapshot import create_mysql_snapshot


class BackupCryptographyTests(TestCase):
    def test_manifest_v2_authentication_and_tamper_rejection(self):
        key = b"m" * 32
        now = timezone.now()
        unsigned = {
            "manifestSchemaVersion": 2, "manifestId": str(uuid.uuid4()), "backupSetId": str(uuid.uuid4()),
            "databaseSnapshotId": str(uuid.uuid4()), "snapshotMechanism": "mysqldump-single-transaction",
            "toolVersion": "8.0.37", "serverVersion": "8.0.37", "snapshotSize": 10,
            "databaseSnapshotDigest": "a" * 64, "applicationVersion": "commit", "schemaVersion": "schema",
            "migrationFingerprint": "b" * 64, "preparedOperationId": str(uuid.uuid4()),
            "dryRunId": str(uuid.uuid4()), "purgeParameterDigest": "c" * 64,
            "candidateSetDigest": "d" * 64, "ownerSetDigest": "e" * 64, "candidateCount": 1,
            "ownerCount": 1, "snapshotEpoch": str(uuid.uuid4()), "snapshotStartedAt": now.isoformat(),
            "snapshotCompletedAt": now.isoformat(), "protectedBundleId": str(uuid.uuid4()),
            "bundleAlgorithm": BUNDLE_ALGORITHM, "protectedBundleDigest": "f" * 64,
            "protectedBundleSize": 20, "keyInventoryDigest": "1" * 64,
            "authenticationKeyId": "manifest-key-1", "verificationPolicyVersion": "vault-recovery-v1",
            "evidenceExpiresAt": (now + timedelta(hours=1)).isoformat(), "invalidationGeneration": 0,
            "journalCheckpointId": str(uuid.uuid4()),
        }
        manifest = authenticate_manifest_v2(unsigned, key=key)
        self.assertEqual(authenticate_manifest(manifest, key=key), unsigned)
        manifest["candidateCount"] = 2
        with self.assertRaises(BackupContractError):
            authenticate_manifest(manifest, key=key)

    def test_bundle_gcm_rejects_wrong_key_and_aad(self):
        ids = [uuid.uuid4() for _ in range(4)]
        aad = bundle_aad_v2(backup_set_id=ids[0], bundle_id=ids[1], manifest_id=ids[2], snapshot_id=ids[3],
                            snapshot_digest="a" * 64, application_version="commit", schema_version="schema",
                            key_inventory_digest="b" * 64)
        payload = {"bundleContractVersion": 2, "keys": [{"version": 1, "algorithm": "AES-256-GCM",
                                                           "key": "disposable-test-material"}]}
        blob = encrypt_key_bundle(payload, protection_key=b"k" * 32, aad=aad)
        self.assertEqual(decrypt_key_bundle(blob, protection_key=b"k" * 32, aad=aad), payload)
        for key, changed_aad in ((b"x" * 32, aad), (b"k" * 32, aad + b"x")):
            with self.assertRaises(BackupContractError):
                decrypt_key_bundle(blob, protection_key=key, aad=changed_aad)

    def test_recovery_target_must_be_disposable(self):
        require_disposable_database("test_vault_recovery_" + "a" * 32)
        for unsafe in ("it_support_copilot", "test_vault_recovery_bad", ""):
            with self.assertRaises(RecoveryVerificationError):
                require_disposable_database(unsafe)


class PurgeRemediationAndQualificationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.clock = mock.patch("vault.purge._trusted_now", return_value=self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.owner = User.objects.create_user("backup-owner@example.test", "password")
        self.record = VaultRecord.objects.create(
            owner=self.owner, credential_type=VaultRecord.CredentialType.LOGIN, label="Disposable",
            service_label="Service", origin="https://example.test", key_version=1, nonce=b"n" * 12,
            ciphertext=b"opaque", tag=b"t" * 16, lifecycle=VaultRecord.Lifecycle.DELETED,
            deleted_at=self.now - timedelta(days=31), restore_expires_at=self.now - timedelta(days=1),
        )
        expiry = self.now + timedelta(hours=1)
        self.executor = MaintenancePrincipal("purge-executor", frozenset({"credential.purge"}), expiry)
        self.confirmer = MaintenancePrincipal("purge-confirmer", frozenset({"credential.purge"}), expiry)
        backup_operation = VaultMaintenanceOperation.objects.create(
            operator_id="backup-creator", capability=VaultMaintenanceOperation.Capability.BACKUP_CREATE,
            mode=VaultMaintenanceOperation.Mode.CONTROL, parameter_digest="a" * 64,
            application_version="unknown", schema_version="vault-controlled-purge-v1",
            state=VaultMaintenanceOperation.State.COMPLETED, started_at=self.now, completed_at=self.now)
        self.backup = VaultBackupSet.objects.create(
            operation=backup_operation, database_snapshot_id=uuid.uuid4(), manifest_id=uuid.uuid4(),
            protected_bundle_id=uuid.uuid4(), snapshot_digest="0" * 64, bundle_digest="0" * 64,
            application_version="unknown", schema_version="vault-controlled-purge-v1",
            key_inventory_digest="1" * 64, retention_state="RETAINED", hold_summary="none",
            manifest_auth_key_id="manifest-key-1", state=VaultBackupSet.State.PREPARING)
        self.candidates = [PurgeCandidate(self.record.pk, self.owner.pk, self.record.revision)]

    def _prepare(self):
        dry = assess_purge_candidates(principal=self.executor, candidates=self.candidates,
                                      backup_checkpoint_id=self.backup.pk)
        return (dry, *prepare_purge_execution(principal=self.executor, confirming_principal=self.confirmer,
                    dry_run=dry, candidates=self.candidates, backup_checkpoint_id=self.backup.pk))

    def test_caller_time_spoof_is_rejected_by_interface(self):
        with self.assertRaises(TypeError):
            assess_purge_candidates(principal=self.executor, candidates=self.candidates,
                                    backup_checkpoint_id=self.backup.pk, now=self.now + timedelta(days=1))

    def test_legacy_or_same_executor_confirmation_is_rejected(self):
        _dry, operation, confirmation = self._prepare()
        for issuer in ("legacy-unattributed", operation.operator_id, ""):
            confirmation.issued_by_operator_id = issuer
            confirmation.save(update_fields=("issued_by_operator_id",))
            with self.assertRaises(ControlledPurgeDenied):
                execute_purge(principal=self.executor, operation_id=operation.pk, candidates=self.candidates)

    def test_pending_batch_scope_blocks_overlapping_assessment(self):
        _dry, operation, _confirmation = self._prepare()
        self.assertEqual(operation.journal.purge_scopes.count(), 1)
        overlap = assess_purge_candidates(principal=self.executor, candidates=self.candidates,
                                          backup_checkpoint_id=self.backup.pk)
        self.assertEqual(overlap.eligible_count, 0)
        self.assertEqual(overlap.blocked_count, 1)

    def test_genuine_bound_evidence_qualifies_verifier_but_operational_purge_stays_disabled(self):
        dry, operation, _confirmation = self._prepare()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / f"{self.backup.database_snapshot_id}.sql"; snapshot.write_bytes(b"snapshot")
            bundle = root / f"{self.backup.protected_bundle_id}.bin"; bundle.write_bytes(b"bundle")
            self.backup.snapshot_digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            self.backup.bundle_digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
            self.backup.state = VaultBackupSet.State.VERIFIED
            self.backup.verified_at = self.now
            self.backup.verification_evidence_digest = "9" * 64
            self.backup.save(update_fields=("snapshot_digest", "bundle_digest", "state", "verified_at",
                                            "verification_evidence_digest"))
            candidate_digest = candidate_set_digest(self.candidates); owner_digest = owner_set_digest(self.candidates)
            VaultRecoveryEvidence.objects.create(
                backup_set=self.backup, prepared_operation_id=operation.pk, dry_run_id=dry.pk,
                parameter_digest=operation.parameter_digest, candidate_set_digest=candidate_digest,
                owner_set_digest=owner_digest, evidence_digest="9" * 64, backup_operator_id="backup-creator",
                verifier_operator_id="recovery-verifier", verification_policy_version="vault-recovery-v1",
                verified_at=self.now, expires_at=self.now + timedelta(hours=1), cleanup_complete=True)
            unsigned = {
                "manifestSchemaVersion": 2, "manifestId": str(self.backup.manifest_id),
                "backupSetId": str(self.backup.pk), "databaseSnapshotId": str(self.backup.database_snapshot_id),
                "snapshotMechanism": "mysqldump-single-transaction", "toolVersion": "8.0.37",
                "serverVersion": "8.0.37", "snapshotSize": snapshot.stat().st_size,
                "databaseSnapshotDigest": self.backup.snapshot_digest, "applicationVersion": operation.application_version,
                "schemaVersion": self.backup.schema_version, "migrationFingerprint": "2" * 64,
                "preparedOperationId": str(operation.pk), "dryRunId": str(dry.pk),
                "purgeParameterDigest": operation.parameter_digest, "candidateSetDigest": candidate_digest,
                "ownerSetDigest": owner_digest, "candidateCount": 1, "ownerCount": 1,
                "snapshotEpoch": str(uuid.uuid4()), "snapshotStartedAt": self.now.isoformat(),
                "snapshotCompletedAt": self.now.isoformat(), "protectedBundleId": str(self.backup.protected_bundle_id),
                "bundleAlgorithm": BUNDLE_ALGORITHM, "protectedBundleDigest": self.backup.bundle_digest,
                "protectedBundleSize": bundle.stat().st_size, "keyInventoryDigest": self.backup.key_inventory_digest,
                "authenticationKeyId": "manifest-key-1", "verificationPolicyVersion": "vault-recovery-v1",
                "evidenceExpiresAt": (self.now + timedelta(hours=1)).isoformat(), "invalidationGeneration": 0,
                "journalCheckpointId": str(operation.journal.pk),
            }
            manifest = root / f"{self.backup.manifest_id}.json"
            manifest.write_text(json.dumps(authenticate_manifest_v2(unsigned, key=b"m" * 32)), encoding="utf-8")
            with mock.patch("vault.qualification.validate_protected_root", return_value=root), \
                 mock.patch("vault.qualification.validate_artifact", side_effect=lambda path, **_: Path(path)), \
                 mock.patch("vault.qualification._key", return_value=b"m" * 32), \
                 override_settings(VAULT_BACKUP_MANIFEST_ROOT=str(root), VAULT_BACKUP_SNAPSHOT_ROOT=str(root),
                                   VAULT_BACKUP_BUNDLE_ROOT=str(root), VAULT_MANIFEST_AUTH_KEY_FILE=str(root / "key")):
                result = qualify_verified_backup(operation=operation, backup_set=self.backup,
                                                 candidates=self.candidates, trusted_now=self.now)
                self.assertEqual(result.prepared_operation_id, str(operation.pk))
                with self.assertRaises(OperationalPurgeDisabled):
                    execute_purge(principal=self.executor, operation_id=operation.pk, candidates=self.candidates)
            self.record.refresh_from_db()
            self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)


class NativeMySQLBackupRecoveryTests(TransactionTestCase):
    reset_sequences = True

    def test_mysqldump_snapshot_restores_only_to_disposable_database(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for disposable backup/recovery evidence")
        current_database = connection.settings_dict["NAME"]
        if not str(current_database).startswith("test_"):
            self.fail("Refusing backup verification outside a Django disposable test database")
        mysqldump = shutil.which("mysqldump") or r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
        mysql = shutil.which("mysql") or r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
        if not Path(mysqldump).is_file() or not Path(mysql).is_file():
            self.skipTest("Version-qualified MySQL client tools are unavailable")
        config = connection.settings_dict
        recovery_database = "test_vault_recovery_" + uuid.uuid4().hex
        principal = MaintenancePrincipal("recovery-verifier", frozenset({"recovery.verify"}),
                                         timezone.now() + timedelta(hours=1))
        with tempfile.TemporaryDirectory() as directory:
            result = create_mysql_snapshot(
                connection=connection, executable=mysqldump, database=current_database, user=config["USER"],
                password=config["PASSWORD"], host=config["HOST"], port=config["PORT"], destination_root=directory,
                timeout=120, max_bytes=64 * 1024 * 1024)
            self.assertTrue(result.path.is_file())
            self.assertEqual(hashlib.sha256(result.path.read_bytes()).hexdigest(), result.digest)
            defaults = Path(directory) / ".restore.cnf"
            defaults.write_text("[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n" %
                                (config["USER"], config["PASSWORD"], config["HOST"], config["PORT"]),
                                encoding="utf-8")
            os.chmod(defaults, 0o600)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE `{recovery_database}` CHARACTER SET utf8mb4")
            try:
                restore_disposable_snapshot(principal=principal, database_name=recovery_database,
                                            mysql_executable=mysql, defaults_file=defaults,
                                            snapshot_path=result.path, timeout=120)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s",
                                   [recovery_database])
                    self.assertGreater(cursor.fetchone()[0], 0)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP DATABASE IF EXISTS `{recovery_database}`")
