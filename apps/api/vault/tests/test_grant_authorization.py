import base64
import os
import threading
import uuid
from queue import Queue
from unittest import mock

from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.authorization import SensitiveAuthorization
from vault.grants import issue_grant, proof_digest
from vault.models import SensitiveOperationGrant, VaultRecord
from vault.services import VaultSensitiveAuthorizationRequired, create_credential


TEST_KEK = base64.b64encode(b"ic022-test-kek-material-32-bytes"[:32]).decode("ascii")


class SensitiveGrantApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        self.user = User.objects.create_user("ops@example.test", "correct-password")
        self.client = Client(); self.client.force_login(self.user)

    def grant(self, client=None):
        client = client or self.client
        response = client.post("/api/v1/vault/reauthenticate", {"password": "correct-password"}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        return response.json()["grant"]

    def create(self, *, proof=None, client=None):
        client = client or self.client
        return client.post("/api/v1/vault/credentials", {
            "credentialType": "LOGIN", "label": "Example",
            "secretFields": {"username": "owner@example.test", "password": "opaque-password"},
        }, content_type="application/json", HTTP_X_VAULT_GRANT=proof or self.grant(client))

    def test_all_five_sensitive_operations_consume_one_grant_each(self):
        created = self.create()
        self.assertEqual(created.status_code, 201)
        credential_id = created.json()["credential"]["id"]

        updated = self.client.patch(f"/api/v1/vault/credentials/{credential_id}", {
            "expectedRevision": 1, "metadata": {"label": "Updated"}
        }, content_type="application/json", HTTP_X_VAULT_GRANT=self.grant())
        self.assertEqual(updated.status_code, 200)

        revealed = self.client.post(f"/api/v1/vault/credentials/{credential_id}/reveal",
            content_type="application/json", HTTP_X_VAULT_GRANT=self.grant())
        self.assertEqual(revealed.status_code, 200)
        self.assertEqual(revealed.json()["credential"]["revealed"]["password"], "opaque-password")
        self.assertEqual(revealed["Cache-Control"], "no-store, private")

        deleted = self.client.delete(f"/api/v1/vault/credentials/{credential_id}",
            {"expectedRevision": 2}, content_type="application/json", HTTP_X_VAULT_GRANT=self.grant())
        self.assertEqual(deleted.status_code, 204)

        restored = self.client.post(f"/api/v1/vault/credentials/{credential_id}/restore",
            {"expectedRevision": 3}, content_type="application/json", HTTP_X_VAULT_GRANT=self.grant())
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(SensitiveOperationGrant.objects.filter(consumed_at__isnull=False).count(), 5)
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_GRANT_USED).count(), 5)

    def test_replay_and_malformed_or_oversized_proofs_are_generic_denials(self):
        proof = self.grant()
        self.assertEqual(self.create(proof=proof).status_code, 201)
        for invalid in (proof, "short", "x" * 44, "!" * 43):
            response = self.client.post("/api/v1/vault/credentials", {
                "credentialType": "LOGIN", "label": "No", "secretFields": {"password": "opaque"}
            }, content_type="application/json", HTTP_X_VAULT_GRANT=invalid)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "invalid_grant")
        self.assertEqual(VaultRecord.objects.count(), 1)

    def test_expired_revoked_and_wrong_session_grants_deny_without_transition(self):
        expired = self.grant()
        expired_row = SensitiveOperationGrant.objects.get(proof_digest=proof_digest(expired))
        SensitiveOperationGrant.objects.filter(pk=expired_row.pk).update(expires_at=timezone.now())
        self.assertEqual(self.create(proof=expired).status_code, 403)
        expired_row.refresh_from_db(); self.assertIsNone(expired_row.consumed_at)

        revoked = self.grant()
        revoked_row = SensitiveOperationGrant.objects.get(proof_digest=proof_digest(revoked))
        SensitiveOperationGrant.objects.filter(pk=revoked_row.pk).update(
            revoked_at=timezone.now(), revocation_reason=SensitiveOperationGrant.RevocationReason.EXPLICIT)
        self.assertEqual(self.create(proof=revoked).status_code, 403)
        revoked_row.refresh_from_db(); self.assertIsNone(revoked_row.consumed_at)

        exact_session_proof = self.grant()
        other_session = Client(); other_session.force_login(self.user)
        self.assertEqual(self.create(proof=exact_session_proof, client=other_session).status_code, 403)
        self.assertIsNone(SensitiveOperationGrant.objects.get(
            proof_digest=proof_digest(exact_session_proof)).consumed_at)

    def test_valid_grant_business_rejection_and_revision_conflict_consume(self):
        invalid_proof = self.grant()
        invalid = self.client.post("/api/v1/vault/credentials", {
            "credentialType": "LOGIN", "label": "Invalid", "secretFields": {}
        }, content_type="application/json", HTTP_X_VAULT_GRANT=invalid_proof)
        self.assertEqual(invalid.status_code, 400)
        self.assertIsNotNone(SensitiveOperationGrant.objects.get(proof_digest=proof_digest(invalid_proof)).consumed_at)

        record_id = self.create().json()["credential"]["id"]
        conflict_proof = self.grant()
        conflict = self.client.patch(f"/api/v1/vault/credentials/{record_id}", {
            "expectedRevision": 99, "metadata": {"label": "Conflict"}
        }, content_type="application/json", HTTP_X_VAULT_GRANT=conflict_proof)
        self.assertEqual(conflict.status_code, 409)
        self.assertIsNotNone(SensitiveOperationGrant.objects.get(proof_digest=proof_digest(conflict_proof)).consumed_at)
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_GRANT_DENIED).count(), 2)

    def test_cross_owner_admin_and_missing_targets_share_unavailable_and_consume(self):
        credential_id = self.create().json()["credential"]["id"]
        other = User.objects.create_user("admin@example.test", "correct-password", is_app_admin=True,
            is_staff=True, is_superuser=True, it_role=User.ITRole.IT_DOC_ADMIN)
        other_client = Client(); other_client.force_login(other)
        for target in (credential_id, str(uuid.uuid4())):
            proof = self.grant(other_client)
            response = other_client.post(f"/api/v1/vault/credentials/{target}/reveal",
                content_type="application/json", HTTP_X_VAULT_GRANT=proof)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "credential_unavailable")
            self.assertIsNotNone(SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof)).consumed_at)

    def test_critical_audit_failure_rolls_back_record_and_grant_consumption(self):
        proof = self.grant()
        with mock.patch("vault.services.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            response = self.create(proof=proof)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(VaultRecord.objects.exists())
        self.assertIsNone(SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof)).consumed_at)

    def test_grant_use_audit_failure_rolls_back_record_and_consumption(self):
        proof = self.grant()
        with mock.patch("vault.grants.record_critical_event", side_effect=RuntimeError("grant audit unavailable")):
            response = self.create(proof=proof)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(VaultRecord.objects.exists())
        self.assertIsNone(SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof)).consumed_at)


@override_settings(VAULT_GRANT_PEPPER="mysql-test-vault-grant-pepper-with-at-least-32-bytes")
class GrantConsumptionMySQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative grant consumption evidence")
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        self.user = User.objects.create_user("consume-race@example.test", "correct-password")
        client = Client(); client.force_login(self.user); self.session_key = client.session.session_key

    def test_simultaneous_grant_consumption_allows_one_commit(self):
        issued = issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        start = threading.Barrier(3); results = Queue()

        def worker(index):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.user.pk); start.wait(timeout=10)
                create_credential(actor=actor, authorization=SensitiveAuthorization(issued.proof, self.session_key),
                    credential_type="LOGIN", label=f"Race {index}", secret_fields={"password": "opaque"})
                results.put("created")
            except VaultSensitiveAuthorizationRequired:
                results.put("denied")
            except Exception as exc:
                results.put(type(exc).__name__)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(index,), daemon=True) for index in range(2)]
        for thread in threads: thread.start()
        start.wait(timeout=10)
        for thread in threads: thread.join(timeout=40); self.assertFalse(thread.is_alive())
        outcomes = sorted(results.get(timeout=2) for _ in threads)
        self.assertEqual(outcomes, ["created", "denied"])
        self.assertEqual(VaultRecord.objects.count(), 1)
        self.assertIsNotNone(SensitiveOperationGrant.objects.get().consumed_at)
