import base64
import os
import threading
from queue import Queue
from unittest import mock

from django.contrib.sessions.models import Session
from django.conf import settings
from django.db import close_old_connections, connection, transaction
from django.test import Client, TransactionTestCase, override_settings

from accounts.lifecycle import deactivate_user
from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.authorization import SensitiveAuthorization
from vault.grants import issue_grant, proof_digest, revoke_session_grants
from vault.models import SensitiveOperationGrant, VaultRecord
from vault.services import VaultSensitiveAuthorizationRequired, VaultUnavailableError, create_credential


TEST_KEK = base64.b64encode(b"ic022-test-kek-material-32-bytes"[:32]).decode("ascii")


class GrantRevocationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        self.user = User.objects.create_user("revoke@example.test", "correct-password")
        self.client = Client(); self.client.force_login(self.user)

    def grant(self, client=None):
        client = client or self.client
        response = client.post("/api/v1/vault/reauthenticate", {"password": "correct-password"}, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        return response.json()["grant"]

    def test_explicit_revoke_is_csrf_protected_idempotent_and_audited(self):
        proof = self.grant()
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post("/api/v1/vault/grants/revoke").status_code, 403)
        token = csrf_client.get("/api/v1/auth/csrf").json()["csrfToken"]
        # This client has a different exact session, so its idempotent revoke does not affect the first proof.
        self.assertEqual(csrf_client.post("/api/v1/vault/grants/revoke", HTTP_X_CSRFTOKEN=token).status_code, 204)
        grant = SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof)); self.assertIsNone(grant.revoked_at)

        self.assertEqual(self.client.post("/api/v1/vault/grants/revoke").status_code, 204)
        self.assertEqual(self.client.post("/api/v1/vault/grants/revoke").status_code, 204)
        grant.refresh_from_db(); self.assertIsNotNone(grant.revoked_at)
        self.assertEqual(grant.revocation_reason, SensitiveOperationGrant.RevocationReason.EXPLICIT)
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_GRANT_REVOKED).count(), 3)

    def test_revocation_audit_failure_rolls_back_revocation(self):
        proof = self.grant()
        with mock.patch("vault.grants.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            response = self.client.post("/api/v1/vault/grants/revoke")
        self.assertEqual(response.status_code, 503)
        grant = SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof))
        self.assertIsNone(grant.revoked_at)

    def test_logout_revokes_grants_and_invalidates_exact_session(self):
        proof = self.grant(); session_key = self.client.session.session_key
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 204)
        grant = SensitiveOperationGrant.objects.get(proof_digest=proof_digest(proof))
        self.assertIsNotNone(grant.revoked_at)
        self.assertEqual(grant.revocation_reason, SensitiveOperationGrant.RevocationReason.LOGOUT)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())

    def test_deactivation_revokes_all_sessions_and_grants(self):
        first = self.grant()
        other_client = Client(); other_client.force_login(self.user); second = self.grant(other_client)
        session_keys = [self.client.session.session_key, other_client.session.session_key]
        admin = User.objects.create_user("admin-revoke@example.test", "correct-password", is_app_admin=True)
        deactivate_user(actor=admin, target_id=self.user.pk)
        grants = SensitiveOperationGrant.objects.filter(proof_digest__in=[proof_digest(first), proof_digest(second)])
        self.assertEqual(grants.filter(revocation_reason=SensitiveOperationGrant.RevocationReason.ACCOUNT_DEACTIVATED).count(), 2)
        self.assertFalse(Session.objects.filter(session_key__in=session_keys).exists())

    def test_deleted_expired_or_corrupt_session_cannot_authorize(self):
        proof = self.grant(); session_key = self.client.session.session_key
        authorization = SensitiveAuthorization(proof, session_key)
        Session.objects.filter(session_key=session_key).delete()
        with self.assertRaises(VaultSensitiveAuthorizationRequired):
            create_credential(actor=self.user, authorization=authorization, credential_type="LOGIN",
                label="No", secret_fields={"password": "opaque"})
        self.assertFalse(VaultRecord.objects.exists())

        client = Client(); client.force_login(self.user); proof = self.grant(client); session_key = client.session.session_key
        Session.objects.filter(session_key=session_key).update(expire_date=__import__("django.utils.timezone", fromlist=["now"]).now())
        with self.assertRaises(VaultSensitiveAuthorizationRequired):
            create_credential(actor=self.user, authorization=SensitiveAuthorization(proof, session_key),
                credential_type="LOGIN", label="No", secret_fields={"password": "opaque"})

        client = Client(); client.force_login(self.user); proof = self.grant(client); session_key = client.session.session_key
        Session.objects.filter(session_key=session_key).update(session_data="corrupt")
        with self.assertRaises(VaultSensitiveAuthorizationRequired):
            create_credential(actor=self.user, authorization=SensitiveAuthorization(proof, session_key),
                credential_type="LOGIN", label="No", secret_fields={"password": "opaque"})


@override_settings(VAULT_GRANT_PEPPER="mysql-test-vault-grant-pepper-with-at-least-32-bytes")
class GrantRevocationMySQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative revocation races")
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start(); self.addCleanup(self.env.stop)
        self.user = User.objects.create_user("revoke-race@example.test", "correct-password")
        client = Client(); client.force_login(self.user); self.session_key = client.session.session_key
        self.issued = issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")

    def use_worker(self, start, results):
        close_old_connections()
        try:
            actor = User.objects.get(pk=self.user.pk); start.wait(timeout=10)
            create_credential(actor=actor, authorization=SensitiveAuthorization(self.issued.proof, self.session_key),
                credential_type="LOGIN", label="Race", secret_fields={"password": "opaque"})
            results.put("used")
        except (VaultSensitiveAuthorizationRequired, VaultUnavailableError):
            results.put("denied")
        except Exception as exc:
            results.put(type(exc).__name__)
        finally: close_old_connections()

    def client_for_session(self):
        client = Client(); client.cookies[settings.SESSION_COOKIE_NAME] = self.session_key
        return client

    def run_race(self, other_worker):
        start = threading.Barrier(3); results = Queue()
        threads = [threading.Thread(target=self.use_worker, args=(start, results), daemon=True),
                   threading.Thread(target=other_worker, args=(start, results), daemon=True)]
        for thread in threads: thread.start()
        start.wait(timeout=10)
        for thread in threads: thread.join(timeout=40); self.assertFalse(thread.is_alive())
        return sorted(results.get(timeout=2) for _ in threads)

    def assert_safe_final_state(self):
        grant = SensitiveOperationGrant.objects.get(pk=SensitiveOperationGrant.objects.only("pk").get().pk)
        self.assertFalse(grant.consumed_at and grant.revoked_at)
        if grant.consumed_at:
            self.assertEqual(VaultRecord.objects.count(), 1)
        else:
            self.assertIsNotNone(grant.revoked_at)
            self.assertEqual(VaultRecord.objects.count(), 0)

    def test_grant_use_versus_explicit_revoke_has_safe_winner(self):
        def revoke_worker(start, results):
            close_old_connections()
            try:
                client = self.client_for_session(); start.wait(timeout=10)
                results.put("revoked" if client.post("/api/v1/vault/grants/revoke").status_code == 204 else "revoke_error")
            finally: close_old_connections()
        outcomes = self.run_race(revoke_worker)
        self.assertIn(outcomes, (["revoked", "used"], ["denied", "revoked"]))
        self.assert_safe_final_state()

    def test_grant_use_versus_logout_has_safe_winner(self):
        def logout_worker(start, results):
            close_old_connections()
            try:
                client = self.client_for_session(); start.wait(timeout=10)
                results.put("logged_out" if client.post("/api/v1/auth/logout").status_code == 204 else "logout_error")
            finally: close_old_connections()
        outcomes = self.run_race(logout_worker)
        self.assertIn(outcomes, (["logged_out", "used"], ["denied", "logged_out"]))
        self.assert_safe_final_state()

    def test_grant_use_versus_deactivation_has_safe_winner(self):
        admin = User.objects.create_user("race-admin@example.test", "correct-password", is_app_admin=True)
        def deactivate_worker(start, results):
            close_old_connections()
            try:
                actor = User.objects.get(pk=admin.pk); start.wait(timeout=10)
                deactivate_user(actor=actor, target_id=self.user.pk); results.put("deactivated")
            except Exception as exc: results.put(type(exc).__name__)
            finally: close_old_connections()
        outcomes = self.run_race(deactivate_worker)
        self.assertIn(outcomes, (["deactivated", "used"], ["deactivated", "denied"]))
        self.assert_safe_final_state()

    def test_forced_revocation_and_use_winner_orders(self):
        # Revocation wins by holding the user lock before the use begins.
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=self.user.pk)
            revoke_session_grants(user=user, session_key=self.session_key,
                reason=SensitiveOperationGrant.RevocationReason.EXPLICIT)
        with self.assertRaises(VaultSensitiveAuthorizationRequired):
            create_credential(actor=self.user, authorization=SensitiveAuthorization(self.issued.proof, self.session_key),
                credential_type="LOGIN", label="No", secret_fields={"password": "opaque"})
        self.assert_safe_final_state()

        # A fresh use wins and commits before a later revocation observes the terminal grant.
        self.user = User.objects.create_user("use-wins@example.test", "correct-password")
        client = Client(); client.force_login(self.user); self.session_key = client.session.session_key
        self.issued = issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        create_credential(actor=self.user, authorization=SensitiveAuthorization(self.issued.proof, self.session_key),
            credential_type="LOGIN", label="Yes", secret_fields={"password": "opaque"})
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=self.user.pk)
            revoke_session_grants(user=user, session_key=self.session_key,
                reason=SensitiveOperationGrant.RevocationReason.EXPLICIT)
        grant = SensitiveOperationGrant.objects.get(user=self.user)
        self.assertIsNotNone(grant.consumed_at); self.assertIsNone(grant.revoked_at)
