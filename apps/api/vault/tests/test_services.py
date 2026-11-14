import base64
import os
import uuid
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.models import VaultOwnerKey, VaultRecord
from vault.services import (
    VaultConflictError,
    VaultSensitiveAuthorizationRequired,
    VaultServiceUnavailable,
    VaultUnavailableError,
    create_credential,
    delete_credential,
    get_credential_metadata,
    metadata_payload,
    restore_credential,
    reveal_credential,
    update_credential,
)
from vault.testing import authorize_sensitive_operation_for_test, patch_sensitive_authorization_for_test

from vault.crypto import VaultCryptoError

TEST_KEK = base64.b64encode(b"external-test-kek-material-32byt"[:32]).decode("ascii")


class VaultServiceTests(TestCase):
    def setUp(self):
        self.auth_patch = patch_sensitive_authorization_for_test()
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.owner = User.objects.create_user("owner@example.test", "password")
        self.other = User.objects.create_user("other@example.test", "password", is_app_admin=True, is_staff=True, is_superuser=True)
        self.authorization = authorize_sensitive_operation_for_test(self.owner)

    def create(self, credential_type=VaultRecord.CredentialType.LOGIN, secret_fields=None, **kwargs):
        defaults = {
            VaultRecord.CredentialType.LOGIN: {"username": "user@example.test", "password": "opaque-password"},
            VaultRecord.CredentialType.API_TOKEN: {"token": "opaque-token", "token_identifier": "build"},
            VaultRecord.CredentialType.SSH_KEY: {"private_key": "opaque-private-key", "passphrase": "opaque-passphrase"},
            VaultRecord.CredentialType.GENERIC_SECRET: {"secret": "opaque-generic-secret"},
        }
        return create_credential(actor=self.owner, authorization=self.authorization, credential_type=credential_type,
                                 label=kwargs.pop("label", "Example"), secret_fields=secret_fields or defaults[credential_type], **kwargs)

    def test_all_types_encrypt_and_metadata_never_serializes_envelopes(self):
        for credential_type in VaultRecord.CredentialType:
            record = self.create(credential_type)
            data = metadata_payload(record)
            self.assertEqual(data["credential_type"], credential_type)
            self.assertTrue({"ciphertext", "nonce", "tag", "key_version"}.isdisjoint(data))
            self.assertNotIn("opaque", str(data))
        self.assertEqual(VaultOwnerKey.objects.count(), 1)
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_CREATED).count(), 4)

    def test_partial_update_preserves_omitted_encrypted_fields(self):
        record = self.create()
        updated = update_credential(actor=self.owner, authorization=self.authorization, record_id=record.pk,
                                    expected_revision=1, secret_fields={"username": "new@example.test"})
        with self.captureOnCommitCallbacks(execute=True):
            deferred = reveal_credential(actor=self.owner, authorization=self.authorization, record_id=record.pk)
        self.assertEqual(deferred.release()["username"], "new@example.test")
        self.assertEqual(deferred.release()["password"], "opaque-password")
        self.assertEqual(updated.revision, 2)

    def test_stale_revision_and_restore_window(self):
        record = self.create()
        with self.assertRaises(VaultConflictError):
            update_credential(actor=self.owner, authorization=self.authorization, record_id=record.pk,
                              expected_revision=99, metadata_changes={"label": "Changed"})
        deleted = delete_credential(actor=self.owner, authorization=self.authorization, record_id=record.pk, expected_revision=1)
        self.assertEqual(deleted.lifecycle, VaultRecord.Lifecycle.DELETED)
        with self.assertRaises(VaultUnavailableError):
            get_credential_metadata(actor=self.owner, record_id=record.pk)
        VaultRecord.objects.filter(pk=record.pk).update(restore_expires_at=timezone.now())
        with self.assertRaises(VaultConflictError):
            restore_credential(actor=self.owner, authorization=self.authorization, record_id=record.pk, expected_revision=2)

    def test_cross_owner_admin_superuser_and_missing_targets_share_unavailable(self):
        record = self.create()
        for actor, target in ((self.other, record.pk), (self.owner, uuid.uuid4())):
            with self.subTest(actor=actor.pk), self.assertRaisesRegex(VaultUnavailableError, "Credential is unavailable"):
                get_credential_metadata(actor=actor, record_id=target)

    def test_every_cross_owner_privilege_combination_remains_denied(self):
        record = self.create()
        combinations = [
            {"it_role": role} for role in User.ITRole
        ] + [
            {"is_app_admin": True}, {"is_staff": True}, {"is_superuser": True},
            {"is_app_admin": True, "is_staff": True, "is_superuser": True, "it_role": User.ITRole.IT_DOC_ADMIN},
        ]
        for index, fields in enumerate(combinations):
            actor = User.objects.create_user(f"privilege-{index}@example.test", "password", **fields)
            with self.subTest(fields=fields), self.assertRaises(VaultUnavailableError):
                get_credential_metadata(actor=actor, record_id=record.pk)

    def test_inactive_owner_and_missing_authorization_fail_closed(self):
        record = self.create()
        self.owner.is_active = False
        self.owner.save(update_fields=("is_active",))
        with self.assertRaises(VaultUnavailableError):
            get_credential_metadata(actor=self.owner, record_id=record.pk)
        with self.assertRaises(VaultSensitiveAuthorizationRequired):
            create_credential(actor=self.other, authorization=None, credential_type="LOGIN", label="x",
                              secret_fields={"password": "opaque"})

    def test_validation_rejects_bad_origin_controls_and_oversize(self):
        invalid = [
            {"origin": "http://example.test"},
            {"origin": "https://example.test:bad"},
            {"label": "bad\nlabel"},
            {"secret_fields": {"password": "x" * 32769}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)

    def test_type_specific_metadata_classification_is_enforced(self):
        self.create(VaultRecord.CredentialType.LOGIN, service_label="Example", origin="https://example.test")
        self.create(VaultRecord.CredentialType.API_TOKEN, service_label="Example")
        for credential_type in (VaultRecord.CredentialType.API_TOKEN, VaultRecord.CredentialType.SSH_KEY,
                                VaultRecord.CredentialType.GENERIC_SECRET):
            with self.subTest(credential_type=credential_type), self.assertRaises(ValidationError):
                self.create(credential_type, origin="https://example.test")

    @mock.patch("vault.services.record_critical_event", side_effect=RuntimeError("audit backend detail"))
    def test_audit_failure_rolls_back_mutation(self, _audit):
        with self.assertRaisesRegex(VaultServiceUnavailable, "Vault operation could not be completed") as caught:
            self.create()
        self.assertNotIn("audit backend detail", str(caught.exception))
        self.assertEqual(VaultRecord.objects.count(), 0)
        self.assertEqual(VaultOwnerKey.objects.count(), 0)

    def test_duplicate_labels_are_allowed(self):
        self.create(label="same")
        self.create(label="same")
        self.assertEqual(VaultRecord.objects.count(), 2)

    @mock.patch("vault.services.MAX_RECORDS_PER_OWNER", 2)
    def test_owner_quantity_limit_counts_active_and_deleted_records(self):
        first = self.create(label="first")
        delete_credential(actor=self.owner, authorization=self.authorization, record_id=first.pk, expected_revision=1)
        self.create(label="second")
        with self.assertRaises(VaultConflictError):
            self.create(label="third")

    def test_database_envelope_length_constraint_rejects_bypass_update(self):
        record = self.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            VaultRecord.objects.filter(pk=record.pk).update(nonce=b"short")


    def test_malformed_credential_ids_return_generic_unavailable(self):
        invalid_ids = [
            "not-a-uuid",
            "",
            "123",
            "00000000-0000-0000-0000-invalid",
            None,
            12345,
            {},
            [],
        ]

        for invalid_id in invalid_ids:
            with self.subTest(record_id=invalid_id):
                with self.assertRaisesRegex(
                    VaultUnavailableError,
                    "^Credential is unavailable$",
                ):
                    get_credential_metadata(
                        actor=self.owner,
                        record_id=invalid_id,
                    )

                with self.assertRaisesRegex(
                    VaultUnavailableError,
                    "^Credential is unavailable$",
                ):
                    reveal_credential(
                        actor=self.owner,
                        authorization=self.authorization,
                        record_id=invalid_id,
                    )


    def test_https_origin_canonicalization(self):
        accepted = {
            "https://example.com": "https://example.com",
            "https://EXAMPLE.COM:443/": "https://example.com",
            "https://example.com:8443": "https://example.com:8443",
            "https://[2001:db8::1]": "https://[2001:db8::1]",
            "https://[2001:0db8::0001]:443/": "https://[2001:db8::1]",
            "https://[2001:db8::1]:8443": "https://[2001:db8::1]:8443",
        }

        for origin, expected in accepted.items():
            with self.subTest(origin=origin):
                record = self.create(
                    label="Canonical origin",
                    origin=origin,
                )
                self.assertEqual(record.origin, expected)

    def test_invalid_https_origins_are_rejected(self):
        invalid = [
            "http://example.com",
            "https://example.com:bad",
            "https://example.com:99999",
            "https://example.com:0",
            "https://example.com:",
            "https://2001:db8::1",
            "https://[invalid-ipv6]",
            "https://[2001:db8::1",
            "https://example.com/path",
            "https://example.com?query=1",
            "https://example.com#fragment",
            "https://user@example.com",
            "https://example..com",
            "https://-example.com",
            "https://example.com-",
            "https://exa_mple.com",
            "https://example.com\\evil",
            "https://example.com:443:8443",
        ]

        for origin in invalid:
            with self.subTest(origin=origin):
                with self.assertRaises(ValidationError):
                    self.create(
                        label="Invalid origin",
                        origin=origin,
                    )


class VaultCommitBarrierTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.auth_patch = patch_sensitive_authorization_for_test()
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.owner = User.objects.create_user("barrier@example.test", "password")
        self.authorization = authorize_sensitive_operation_for_test(self.owner)
        self.record = create_credential(actor=self.owner, authorization=self.authorization, credential_type="LOGIN",
                                        label="Barrier", secret_fields={"password": "opaque-password"})

    def test_plaintext_cannot_release_before_commit(self):
        with transaction.atomic():
            deferred = reveal_credential(actor=self.owner, authorization=self.authorization, record_id=self.record.pk)
            with self.assertRaises(VaultServiceUnavailable):
                deferred.release()
        self.assertEqual(deferred.release(), {"password": "opaque-password"})


    def test_outer_rollback_never_releases_plaintext(self):
        deferred = None

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                deferred = reveal_credential(
                    actor=self.owner,
                    authorization=self.authorization,
                    record_id=self.record.pk,
                )

                self.assertIsNone(deferred._payload)

                raise RuntimeError("rollback marker")

        self.assertIsNotNone(deferred)
        self.assertIsNone(deferred._payload)

        with self.assertRaises(VaultServiceUnavailable):
            deferred.release()

    def test_nested_rollback_never_releases_plaintext(self):
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    deferred = reveal_credential(
                        actor=self.owner,
                        authorization=self.authorization,
                        record_id=self.record.pk,
                    )

                    self.assertIsNone(deferred._payload)

                    raise RuntimeError("nested rollback marker")

        self.assertIsNone(deferred._payload)

        with self.assertRaises(VaultServiceUnavailable):
            deferred.release()

    def test_decryption_occurs_only_after_commit(self):
        with mock.patch(
            "vault.services._decrypt_payload",
            wraps=__import__(
                "vault.services",
                fromlist=["_decrypt_payload"],
            )._decrypt_payload,
        ) as decrypt_mock:
            with transaction.atomic():
                deferred = reveal_credential(
                    actor=self.owner,
                    authorization=self.authorization,
                    record_id=self.record.pk,
                )

                self.assertIsNone(deferred._payload)
                decrypt_mock.assert_not_called()

            decrypt_mock.assert_called_once()
            self.assertEqual(
                deferred.release(),
                {"password": "opaque-password"},
            )


    def test_audit_failure_never_decrypts(self):
        with mock.patch(
            "vault.services._decrypt_payload"
        ) as decrypt_mock:
            with mock.patch(
                "vault.services.record_critical_event",
                side_effect=RuntimeError("audit failure"),
            ):
                with self.assertRaises(VaultServiceUnavailable):
                    reveal_credential(
                        actor=self.owner,
                        authorization=self.authorization,
                        record_id=self.record.pk,
                    )

            decrypt_mock.assert_not_called()

    def test_post_commit_decryption_failure_denies_release(self):
        with mock.patch(
            "vault.services._decrypt_payload",
            side_effect=VaultCryptoError("simulated failure"),
        ):
            deferred = reveal_credential(
                actor=self.owner,
                authorization=self.authorization,
                record_id=self.record.pk,
            )

        self.assertIsNone(deferred._payload)

        with self.assertRaises(VaultServiceUnavailable):
            deferred.release()
