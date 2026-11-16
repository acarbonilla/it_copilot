import base64
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from vault.crypto import EncryptionContext, EncryptionEnvelope, WrappedKeyEnvelope, decrypt, encrypt, unwrap_dek, wrap_dek
from vault.maintenance import MaintenancePrincipal
from vault.models import VaultMaintenanceGuard, VaultOwnerKey, VaultRecord
from vault.rotation import (
    OperationalRotationDisabled, RotationDenied, _execute_disposable_dek_rotation,
    _execute_disposable_kek_rotation, assess_dek_rotation, assess_kek_rotation,
    assess_key_retirement, execute_dek_rotation, execute_kek_rotation, prepare_rotation,
)


class KeyRotationTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.clock = mock.patch("vault.rotation._now", return_value=self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        VaultMaintenanceGuard.objects.get_or_create(pk=1)
        self.owner = User.objects.create_user("rotation-owner@example.test", "password")
        self.executor = MaintenancePrincipal("rotation-executor", frozenset({
            "key.rotate.kek", "key.rotate.dek", "key.retire.online"}), self.now + timedelta(hours=1))
        self.confirmer = MaintenancePrincipal("rotation-confirmer", frozenset({
            "key.rotate.kek", "key.rotate.dek"}), self.now + timedelta(hours=1))
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.keks = {1: b"a" * 32, 2: b"b" * 32}
        self.provider = Path(self.directory.name) / "provider.json"
        self.provider.write_text(json.dumps({
            "schemaVersion": 1, "activeGeneration": 2,
            "generations": [{"generation": generation,
                             "keyBase64": base64.b64encode(key).decode("ascii")}
                            for generation, key in self.keks.items()],
        }), encoding="utf-8")
        self.settings = override_settings(VAULT_KEK_PROVIDER_FILE=str(self.provider)); self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.protected = mock.patch("vault.keys._protected_file", return_value=self.provider)
        self.protected.start(); self.addCleanup(self.protected.stop)

    def _key(self, *, version=1, generation=1, dek=None, active=True):
        dek = dek or bytes([version]) * 32
        wrapped = wrap_dek(kek=self.keks[generation], dek=dek, owner_id=self.owner.pk, key_version=version)
        row = VaultOwnerKey.objects.create(
            owner=self.owner, key_version=version, kek_generation=generation,
            envelope_version=wrapped.envelope_version, nonce=wrapped.nonce,
            wrapped_dek=wrapped.wrapped_dek, tag=wrapped.tag,
            active_slot=True if active else None,
            retired_at=None if active else self.now)
        return row, dek

    def _record(self, key_row, dek, *, lifecycle=VaultRecord.Lifecycle.ACTIVE, label="credential"):
        record = VaultRecord(owner=self.owner, credential_type=VaultRecord.CredentialType.GENERIC_SECRET,
                             label=label, service_label="", origin="", lifecycle=lifecycle,
                             key_version=key_row.key_version, nonce=b"0" * 12, ciphertext=b"x", tag=b"0" * 16)
        if lifecycle == VaultRecord.Lifecycle.DELETED:
            record.deleted_at = self.now; record.restore_expires_at = self.now + timedelta(days=1)
        context = EncryptionContext(self.owner.pk, str(record.pk), record.credential_type)
        envelope = encrypt(dek=dek, plaintext=b'{"secret":"value"}', context=context,
                           key_version=key_row.key_version)
        record.nonce, record.ciphertext, record.tag = envelope.nonce, envelope.ciphertext, envelope.tag
        record.save()
        return record

    def test_kek_rewrap_preserves_dek_record_version_and_ciphertext(self):
        key_row, dek = self._key(); record = self._record(key_row, dek)
        old_nonce, old_wrapped, old_ciphertext = bytes(key_row.nonce), bytes(key_row.wrapped_dek), bytes(record.ciphertext)
        dry = assess_kek_rotation(principal=self.executor, owner_id=self.owner.pk,
                                  source_generation=1, target_generation=2)
        operation, _ = prepare_rotation(principal=self.executor, confirming_principal=self.confirmer, dry_run=dry,
                                        owner_id=self.owner.pk, source_generation=1, target_generation=2)
        self.assertEqual(operation.journal.owner_id, self.owner.pk)
        _execute_disposable_kek_rotation(principal=self.executor, operation_id=operation.pk,
                                         source_generation=1, target_generation=2)
        key_row.refresh_from_db(); record.refresh_from_db()
        self.assertEqual(key_row.kek_generation, 2)
        self.assertNotEqual(bytes(key_row.nonce), old_nonce); self.assertNotEqual(bytes(key_row.wrapped_dek), old_wrapped)
        recovered = unwrap_dek(kek=self.keks[2], envelope=WrappedKeyEnvelope(
            key_row.envelope_version, key_row.key_version, bytes(key_row.nonce),
            bytes(key_row.wrapped_dek), bytes(key_row.tag)), owner_id=self.owner.pk)
        self.assertEqual(recovered, dek); self.assertEqual(record.key_version, 1)
        self.assertEqual(bytes(record.ciphertext), old_ciphertext)
        journal = operation.journal; journal.refresh_from_db()
        self.assertEqual((journal.owner_id, journal.old_key_version, journal.new_key_version),
                         (self.owner.pk, 1, 2))

    def test_dek_rotation_reencrypts_active_and_deleted_atomically(self):
        key_row, old_dek = self._key(); active = self._record(key_row, old_dek)
        deleted = self._record(key_row, old_dek, lifecycle=VaultRecord.Lifecycle.DELETED, label="deleted")
        old = {active.pk: (active.revision, bytes(active.nonce)), deleted.pk: (deleted.revision, bytes(deleted.nonce))}
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        operation, _ = prepare_rotation(principal=self.executor, confirming_principal=self.confirmer, dry_run=dry,
                                        owner_id=self.owner.pk)
        self.assertEqual(operation.journal.owner_id, self.owner.pk)
        _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk, owner_id=self.owner.pk)
        key_row.refresh_from_db(); active.refresh_from_db(); deleted.refresh_from_db()
        new_key = VaultOwnerKey.objects.get(owner=self.owner, active_slot=True)
        new_dek = unwrap_dek(kek=self.keks[2], envelope=WrappedKeyEnvelope(
            new_key.envelope_version, new_key.key_version, bytes(new_key.nonce),
            bytes(new_key.wrapped_dek), bytes(new_key.tag)), owner_id=self.owner.pk)
        self.assertEqual(new_key.key_version, 2); self.assertIsNone(key_row.active_slot)
        for record in (active, deleted):
            self.assertEqual(record.key_version, 2); self.assertEqual(record.revision, old[record.pk][0] + 1)
            self.assertNotEqual(bytes(record.nonce), old[record.pk][1])
            plaintext = decrypt(dek=new_dek, envelope=EncryptionEnvelope(
                record.envelope_version, record.schema_version, record.key_version, bytes(record.nonce),
                bytes(record.ciphertext), bytes(record.tag)), context=EncryptionContext(
                    self.owner.pk, str(record.pk), record.credential_type))
            self.assertEqual(plaintext, b'{"secret":"value"}')
        journal = operation.journal; journal.refresh_from_db()
        self.assertEqual((journal.owner_id, journal.old_key_version, journal.new_key_version),
                         (self.owner.pk, 1, 2))

    def test_failure_rolls_back_without_mixed_key_state(self):
        key_row, dek = self._key(); record = self._record(key_row, dek)
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        operation, _ = prepare_rotation(principal=self.executor, confirming_principal=self.confirmer, dry_run=dry,
                                        owner_id=self.owner.pk)
        with mock.patch("vault.rotation.encrypt", side_effect=RuntimeError("disposable failure")):
            with self.assertRaises(RuntimeError):
                _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                                 owner_id=self.owner.pk)
        key_row.refresh_from_db(); record.refresh_from_db(); operation.refresh_from_db()
        self.assertTrue(key_row.active_slot); self.assertEqual(record.key_version, 1)
        self.assertEqual(operation.state, operation.State.PENDING)

    def test_authorization_confirmation_and_public_paths_fail_closed(self):
        key_row, dek = self._key(); self._record(key_row, dek)
        wrong = MaintenancePrincipal("wrong", frozenset(), self.now + timedelta(hours=1))
        with self.assertRaises(RotationDenied): assess_dek_rotation(principal=wrong, owner_id=self.owner.pk)
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        with self.assertRaises(RotationDenied):
            prepare_rotation(principal=self.executor, confirming_principal=self.executor, dry_run=dry,
                             owner_id=self.owner.pk)
        with self.assertRaises(OperationalRotationDisabled): execute_kek_rotation()
        with self.assertRaises(OperationalRotationDisabled): execute_dek_rotation()

    def test_confirmation_digest_expiry_replay_and_post_lock_expiry_are_denied(self):
        key_row, dek = self._key(); self._record(key_row, dek)
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        operation, confirmation = prepare_rotation(
            principal=self.executor, confirming_principal=self.confirmer, dry_run=dry, owner_id=self.owner.pk)
        confirmation.parameter_digest = "0" * 64; confirmation.save(update_fields=("parameter_digest",))
        with self.assertRaises(RotationDenied):
            _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                             owner_id=self.owner.pk)

        confirmation.parameter_digest = operation.parameter_digest
        confirmation.issued_by_operator_id = "legacy-unattributed"
        confirmation.save(update_fields=("parameter_digest", "issued_by_operator_id"))
        with self.assertRaises(RotationDenied):
            _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                             owner_id=self.owner.pk)

        confirmation.issued_by_operator_id = self.confirmer.operator_id
        confirmation.expires_at = confirmation.created_at + timedelta(seconds=1)
        confirmation.save(update_fields=("issued_by_operator_id", "expires_at"))
        with mock.patch("vault.rotation._now", return_value=confirmation.expires_at + timedelta(seconds=1)):
            with self.assertRaises(RotationDenied):
                _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                                 owner_id=self.owner.pk)

        confirmation.expires_at = self.now + timedelta(minutes=10)
        confirmation.consumed_at = self.now
        confirmation.save(update_fields=("expires_at", "consumed_at"))
        with self.assertRaises(RotationDenied):
            _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                             owner_id=self.owner.pk)

        confirmation.consumed_at = None; confirmation.save(update_fields=("consumed_at",))
        with mock.patch("vault.rotation._now", side_effect=[self.now, self.now + timedelta(hours=2)]):
            with self.assertRaises(RotationDenied):
                _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                                 owner_id=self.owner.pk)

    def test_missing_historical_kek_and_retirement_dependencies_deny(self):
        key_row, dek = self._key(); self._record(key_row, dek)
        assessment = assess_key_retirement(principal=self.executor, owner_id=self.owner.pk, key_version=1)
        self.assertFalse(assessment.eligible)
        self.assertIn("ACTIVE_KEY", assessment.reason_codes)
        self.assertIn("RECORD_REFERENCE", assessment.reason_codes)
        self.assertIn("RECOVERY_EVIDENCE_UNAVAILABLE", assessment.reason_codes)
        document = json.loads(self.provider.read_text(encoding="utf-8"))
        document["generations"] = [document["generations"][1]]
        self.provider.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(Exception): assess_kek_rotation(
            principal=self.executor, owner_id=self.owner.pk, source_generation=1, target_generation=2)

    def test_pending_owner_scope_blocks_overlap_and_retirement_but_not_unrelated_owner(self):
        key_row, dek = self._key(); self._record(key_row, dek)
        first_dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        second_dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        operation, _ = prepare_rotation(principal=self.executor, confirming_principal=self.confirmer,
                                        dry_run=first_dry, owner_id=self.owner.pk)
        journal = operation.journal; journal.refresh_from_db()
        self.assertEqual(journal.owner_id, self.owner.pk)
        self.assertEqual(journal.state, journal.State.PENDING)
        with self.assertRaises(RotationDenied):
            prepare_rotation(principal=self.executor, confirming_principal=self.confirmer,
                             dry_run=second_dry, owner_id=self.owner.pk)
        assessment = assess_key_retirement(principal=self.executor, owner_id=self.owner.pk, key_version=1)
        self.assertIn("UNFINISHED_JOURNAL", assessment.reason_codes)

        other = User.objects.create_user("rotation-unrelated@example.test", "password")
        other_dek = b"u" * 32
        wrapped = wrap_dek(kek=self.keks[1], dek=other_dek, owner_id=other.pk, key_version=1)
        other_key = VaultOwnerKey.objects.create(owner=other, key_version=1, kek_generation=1,
            envelope_version=wrapped.envelope_version, nonce=wrapped.nonce,
            wrapped_dek=wrapped.wrapped_dek, tag=wrapped.tag)
        record = VaultRecord(owner=other, credential_type=VaultRecord.CredentialType.GENERIC_SECRET,
            label="unrelated", service_label="", origin="", key_version=1,
            nonce=b"0" * 12, ciphertext=b"x", tag=b"0" * 16)
        envelope = encrypt(dek=other_dek, plaintext=b'{"secret":"other"}', context=EncryptionContext(
            other.pk, str(record.pk), record.credential_type), key_version=other_key.key_version)
        record.nonce, record.ciphertext, record.tag = envelope.nonce, envelope.ciphertext, envelope.tag; record.save()
        unrelated = assess_dek_rotation(principal=self.executor, owner_id=other.pk)
        self.assertEqual((unrelated.eligible_count, unrelated.blocked_count), (1, 0))

    def test_fresh_post_lock_time_rejects_expired_confirmation_without_mutation(self):
        key_row, dek = self._key(); record = self._record(key_row, dek)
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        operation, confirmation = prepare_rotation(
            principal=self.executor, confirming_principal=self.confirmer, dry_run=dry, owner_id=self.owner.pk)
        confirmation.expires_at = self.now + timedelta(minutes=5); confirmation.save(update_fields=("expires_at",))
        with mock.patch("vault.rotation._now", side_effect=[self.now, self.now + timedelta(minutes=6)]):
            with self.assertRaises(RotationDenied):
                _execute_disposable_dek_rotation(principal=self.executor, operation_id=operation.pk,
                                                 owner_id=self.owner.pk)
        key_row.refresh_from_db(); record.refresh_from_db(); operation.refresh_from_db()
        self.assertTrue(key_row.active_slot); self.assertEqual(record.key_version, 1)
        self.assertEqual(operation.state, operation.State.PENDING)

    def test_fresh_post_lock_time_rejects_expired_executor_without_mutation(self):
        key_row, dek = self._key(); record = self._record(key_row, dek)
        short = MaintenancePrincipal(self.executor.operator_id, self.executor.capabilities,
                                     self.now + timedelta(minutes=5))
        dry = assess_dek_rotation(principal=short, owner_id=self.owner.pk)
        operation, _ = prepare_rotation(
            principal=short, confirming_principal=self.confirmer, dry_run=dry, owner_id=self.owner.pk)
        with mock.patch("vault.rotation._now", side_effect=[self.now, self.now + timedelta(minutes=6)]):
            with self.assertRaises(RotationDenied):
                _execute_disposable_dek_rotation(principal=short, operation_id=operation.pk,
                                                 owner_id=self.owner.pk)
        key_row.refresh_from_db(); record.refresh_from_db(); operation.refresh_from_db()
        self.assertTrue(key_row.active_slot); self.assertEqual(record.key_version, 1)
        self.assertEqual(operation.state, operation.State.PENDING)


class NativeMySQLKeyRotationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for key-rotation lock evidence")
        if not str(connection.settings_dict["NAME"]).startswith("test_"):
            self.fail("Refusing rotation concurrency verification outside a disposable test database")
        self.now = timezone.now()
        self.clock = mock.patch("vault.rotation._now", return_value=self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        VaultMaintenanceGuard.objects.get_or_create(pk=1)
        self.owner = User.objects.create_user("rotation-race@example.test", "password")
        self.executor = MaintenancePrincipal("rotation-executor", frozenset({"key.rotate.dek"}),
                                             self.now + timedelta(hours=1))
        confirmer = MaintenancePrincipal("rotation-confirmer", frozenset({"key.rotate.dek"}),
                                         self.now + timedelta(hours=1))
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.kek = b"n" * 32; provider = Path(self.directory.name) / "provider.json"
        provider.write_text(json.dumps({"schemaVersion": 1, "activeGeneration": 1, "generations": [{
            "generation": 1, "keyBase64": base64.b64encode(self.kek).decode("ascii")}]}), encoding="utf-8")
        self.settings = override_settings(VAULT_KEK_PROVIDER_FILE=str(provider)); self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.protected = mock.patch("vault.keys._protected_file", return_value=provider)
        self.protected.start(); self.addCleanup(self.protected.stop)
        dek = b"d" * 32; wrapped = wrap_dek(kek=self.kek, dek=dek, owner_id=self.owner.pk, key_version=1)
        key_row = VaultOwnerKey.objects.create(owner=self.owner, key_version=1, kek_generation=1,
            envelope_version=wrapped.envelope_version, nonce=wrapped.nonce,
            wrapped_dek=wrapped.wrapped_dek, tag=wrapped.tag)
        record = VaultRecord(owner=self.owner, credential_type=VaultRecord.CredentialType.GENERIC_SECRET,
            label="race", service_label="", origin="", key_version=1,
            nonce=b"0" * 12, ciphertext=b"x", tag=b"0" * 16)
        envelope = encrypt(dek=dek, plaintext=b'{"secret":"race"}', context=EncryptionContext(
            self.owner.pk, str(record.pk), record.credential_type), key_version=1)
        record.nonce, record.ciphertext, record.tag = envelope.nonce, envelope.ciphertext, envelope.tag; record.save()
        dry = assess_dek_rotation(principal=self.executor, owner_id=self.owner.pk)
        self.operation, _ = prepare_rotation(principal=self.executor, confirming_principal=confirmer, dry_run=dry,
                                             owner_id=self.owner.pk)

    def test_parallel_duplicate_dek_rotation_serializes_one_completion(self):
        operation_id, owner_id, principal = self.operation.pk, self.owner.pk, self.executor
        def attempt():
            close_old_connections()
            try:
                _execute_disposable_dek_rotation(principal=principal, operation_id=operation_id, owner_id=owner_id)
                return "completed"
            except RotationDenied:
                return "denied"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(outcomes, ["completed", "denied"])
        self.assertEqual(VaultOwnerKey.objects.filter(owner=self.owner, active_slot=True).count(), 1)
