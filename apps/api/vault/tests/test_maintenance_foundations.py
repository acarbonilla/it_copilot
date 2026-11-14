import hashlib
import hmac
import json
import os
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.maintenance import (
    MaintenanceAuthorizationDenied,
    _canonical,
    authenticate_maintenance_operator,
)
from vault.maintenance import MaintenancePrincipal
from vault.maintenance_services import assess_purge, create_hold, release_hold
from vault.backup_contracts import BackupContractError, MANIFEST_AUTH_ALGORITHM, authenticate_manifest
from vault.lifecycle import evaluate_purge_eligibility
from vault.models import (VaultBackupSet, VaultMaintenanceConfirmation, VaultMaintenanceHold,
                          VaultMaintenanceJournal, VaultMaintenanceOperation, VaultRecord)


class MaintenanceAuthorizationTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.auth = root / "operators.json"
        self.key = root / "auth.key"
        self.token = root / "operator.token"
        self.key_bytes = b"maintenance-authentication-key-material-32-bytes"
        self.token_bytes = b"operator-token-material-that-is-long-enough"
        self.key.write_bytes(self.key_bytes)
        self.token.write_bytes(self.token_bytes)
        self.settings = override_settings(
            REPOSITORY_DIR=Path("C:/unrelated-repository"),
            VAULT_MAINTENANCE_OPERATORS_FILE=str(self.auth.resolve()),
            VAULT_MAINTENANCE_AUTH_KEY_FILE=str(self.key.resolve()),
        )
        self.settings.enable(); self.addCleanup(self.settings.disable)

    def write_auth(self, *, enabled=True, capabilities=None, tamper=False):
        token_digest = hmac.new(
            self.key_bytes, b"vault-maintenance-operator-token-v1\x00" + self.token_bytes, hashlib.sha256
        ).hexdigest()
        body = {"schemaVersion": 1, "operators": [{
            "operatorId": "operator-01", "enabled": enabled,
            "capabilities": capabilities or ["credential.purge"],
            "expiresAt": (timezone.now() + timedelta(hours=1)).isoformat(), "tokenDigest": token_digest,
        }]}
        body["mac"] = hmac.new(
            self.key_bytes, b"vault-maintenance-auth-file-v1\x00" + _canonical(body), hashlib.sha256
        ).hexdigest()
        if tamper:
            body["operators"][0]["capabilities"].append("backup.create")
        self.auth.write_text(json.dumps(body), encoding="utf-8")
        return body

    @mock.patch("vault.maintenance._protected_file", side_effect=lambda value, **_: Path(value))
    def test_valid_operator_requires_exact_capability_and_reloads_file(self, _protected):
        self.write_auth()
        principal = authenticate_maintenance_operator(
            operator_id="operator-01", token_file=str(self.token), required_capability="credential.purge")
        self.assertEqual(principal.operator_id, "operator-01")
        self.write_auth(enabled=False)
        with self.assertRaises(MaintenanceAuthorizationDenied):
            authenticate_maintenance_operator(
                operator_id="operator-01", token_file=str(self.token), required_capability="credential.purge")

    @mock.patch("vault.maintenance._protected_file", side_effect=lambda value, **_: Path(value))
    def test_tamper_wrong_token_and_role_fallback_are_rejected(self, _protected):
        self.write_auth(tamper=True)
        with self.assertRaises(MaintenanceAuthorizationDenied):
            authenticate_maintenance_operator(
                operator_id="operator-01", token_file=str(self.token), required_capability="credential.purge")
        self.write_auth(capabilities=["backup.create"])
        with self.assertRaises(MaintenanceAuthorizationDenied):
            authenticate_maintenance_operator(
                operator_id="operator-01", token_file=str(self.token), required_capability="credential.purge")

    def test_unsafe_posix_permissions_are_rejected(self):
        self.write_auth()
        if os.name == "nt":
            self.skipTest("POSIX permission-bit assertion; Windows ACL path is enforced separately")
        os.chmod(self.auth, 0o644)
        with self.assertRaises(MaintenanceAuthorizationDenied):
            authenticate_maintenance_operator(
                operator_id="operator-01", token_file=str(self.token), required_capability="credential.purge")

    def test_execute_options_fail_before_authorization(self):
        for command, extra in (("assess_vault_purge", []), ("assess_vault_rotation", ["--kind", "kek"]),
                               ("assess_vault_recovery", [])):
            with self.subTest(command=command), self.assertRaises(CommandError):
                call_command(command, "--operator-id", "operator-01", "--token-file", str(self.token),
                             "--execute", *extra)


class HoldFoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("hold-owner@example.test", "password", is_app_admin=True,
                                              is_staff=True, is_superuser=True)
        expiry = timezone.now() + timedelta(hours=1)
        self.creator = MaintenancePrincipal("holder-creator", frozenset({"credential.hold.create"}), expiry)
        self.releaser = MaintenancePrincipal("holder-releaser", frozenset({"credential.hold.release"}), expiry)

    def test_hold_create_release_are_capability_bound_and_audited(self):
        hold = create_hold(principal=self.creator, owner=self.owner,
                           scope=VaultMaintenanceHold.Scope.OWNER, reason=VaultMaintenanceHold.Reason.LEGAL)
        self.assertIsNone(hold.released_at)
        released = release_hold(principal=self.releaser, hold=hold)
        self.assertIsNotNone(released.released_at)
        self.assertEqual(SecurityAuditEvent.objects.filter(
            action__in=(SecurityAuditEvent.Action.VAULT_HOLD_CREATED,
                        SecurityAuditEvent.Action.VAULT_HOLD_RELEASED)).count(), 2)
        self.assertEqual(VaultMaintenanceOperation.objects.count(), 2)

    @mock.patch("vault.maintenance_services.record_critical_event", side_effect=RuntimeError("audit detail"))
    def test_critical_audit_failure_rolls_back_hold(self, _audit):
        with self.assertRaises(RuntimeError):
            create_hold(principal=self.creator, owner=self.owner,
                        scope=VaultMaintenanceHold.Scope.OWNER, reason=VaultMaintenanceHold.Reason.LEGAL)
        self.assertEqual(VaultMaintenanceHold.objects.count(), 0)
        self.assertEqual(VaultMaintenanceOperation.objects.count(), 0)


class MaintenancePersistenceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("persistence-owner@example.test", "password")
        now = timezone.now()
        self.record = VaultRecord.objects.create(
            owner=self.owner, credential_type=VaultRecord.CredentialType.LOGIN, label="Deleted",
            service_label="", origin="", lifecycle=VaultRecord.Lifecycle.DELETED,
            key_version=1, nonce=b"n" * 12, ciphertext=b"ciphertext", tag=b"t" * 16,
            deleted_at=now - timedelta(days=31), restore_expires_at=now - timedelta(days=1),
        )
        self.operation = VaultMaintenanceOperation.objects.create(
            operator_id="operator", capability=VaultMaintenanceOperation.Capability.CREDENTIAL_PURGE,
            mode=VaultMaintenanceOperation.Mode.DRY_RUN, parameter_digest="a" * 64,
            application_version="test", schema_version="test", state=VaultMaintenanceOperation.State.COMPLETED,
            completed_at=now,
        )
        self.principal = MaintenancePrincipal(
            "purge-operator", frozenset({"credential.purge"}), now + timedelta(hours=1))

    def backup(self, *, state=VaultBackupSet.State.PREPARING, evidence=None, verified_at=None):
        return VaultBackupSet.objects.create(
            operation=self.operation, database_snapshot_id=uuid.uuid4(), manifest_id=uuid.uuid4(),
            protected_bundle_id=uuid.uuid4(), snapshot_digest="a" * 64, bundle_digest="b" * 64,
            application_version="test", schema_version="test", key_inventory_digest="c" * 64,
            retention_state="RETAINED", hold_summary="none", manifest_auth_key_id="manifest-key-1",
            state=state, verification_evidence_digest=evidence, verified_at=verified_at,
        )

    def test_verified_inventory_requires_evidence_and_time(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.backup(state=VaultBackupSet.State.VERIFIED)

    def test_purge_predicate_fails_closed_on_hold_journal_checkpoint_and_confirmation(self):
        result = evaluate_purge_eligibility(
            record=self.record, expected_revision=self.record.revision,
            operation=None, confirmation=None, capability_authorized=False)
        self.assertFalse(result.eligible)
        self.assertTrue({"verified_checkpoint_missing", "capability_missing", "completed_dry_run_missing",
                         "confirmation_missing"} <= set(result.reasons))

    def test_journal_completed_state_requires_timestamp(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            VaultMaintenanceJournal.objects.create(
                operation=self.operation, operation_type=VaultMaintenanceJournal.OperationType.PURGE,
                owner=self.owner, state=VaultMaintenanceJournal.State.COMPLETED)

    def test_purge_assessment_is_read_only_bounded_and_critically_audited(self):
        operation = assess_purge(principal=self.principal, owner_id=self.owner.pk, limit=100)
        self.record.refresh_from_db()
        self.assertEqual(self.record.lifecycle, VaultRecord.Lifecycle.DELETED)
        self.assertEqual(operation.state, VaultMaintenanceOperation.State.COMPLETED)
        self.assertEqual(operation.blocked_count, 1)
        self.assertEqual(SecurityAuditEvent.objects.filter(
            action=SecurityAuditEvent.Action.VAULT_PURGE_ASSESSED,
            target_id=str(operation.pk)).count(), 1)

    @mock.patch("vault.maintenance_services.record_critical_event", side_effect=RuntimeError("audit detail"))
    def test_purge_assessment_audit_failure_rolls_back_metadata(self, _audit):
        before = VaultMaintenanceOperation.objects.count()
        with self.assertRaises(RuntimeError):
            assess_purge(principal=self.principal, owner_id=self.owner.pk, limit=100)
        self.assertEqual(VaultMaintenanceOperation.objects.count(), before)


class BackupContractTests(TestCase):
    def test_manifest_requires_keyed_authenticity_and_exact_schema(self):
        key = b"manifest-authentication-key-material-32-bytes"
        unsigned = {
            "manifestSchemaVersion": 1, "backupSetId": str(uuid.uuid4()),
            "databaseSnapshotId": str(uuid.uuid4()), "databaseSnapshotDigest": "a" * 64,
            "protectedBundleId": str(uuid.uuid4()), "protectedBundleDigest": "b" * 64,
            "applicationVersion": "commit", "schemaVersion": "schema", "keyInventoryDigest": "c" * 64,
            "journalCheckpointId": None, "retentionState": "RETAINED", "holdSummary": "none",
            "createdAt": timezone.now().isoformat(), "authenticationKeyId": "manifest-key-1",
        }
        from vault.backup_contracts import canonical_manifest_bytes
        mac = hmac.new(key, b"vault-backup-manifest-v1\x00" + canonical_manifest_bytes(unsigned),
                       hashlib.sha256).hexdigest()
        manifest = {**unsigned, "authentication": {"algorithm": MANIFEST_AUTH_ALGORITHM, "mac": mac}}
        self.assertEqual(authenticate_manifest(manifest, key=key), unsigned)
        manifest["holdSummary"] = "tampered"
        with self.assertRaises(BackupContractError):
            authenticate_manifest(manifest, key=key)
