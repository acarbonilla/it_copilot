import threading
from queue import Queue
from unittest import mock

from django.contrib.sessions.models import Session
from django.db import DatabaseError, close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from security_audit.models import SecurityAuditEvent
from vault.grants import FAILURE_LIMIT, GRANT_TTL, GrantDenied, ReauthenticationDenied, issue_grant, proof_digest, session_digest
from vault.models import SensitiveOperationGrant, SessionReauthenticationThrottle, UserReauthenticationThrottle


class GrantFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("grant@example.test", "correct-password")
        self.client = Client(); self.client.force_login(self.user)
        self.session_key = self.client.session.session_key

    def test_random_proof_is_stored_only_as_domain_separated_digest(self):
        issued = issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        grant = SensitiveOperationGrant.objects.get()
        self.assertEqual(len(issued.proof), 43)
        self.assertNotEqual(grant.proof_digest, issued.proof)
        self.assertNotEqual(grant.session_digest, self.session_key)
        self.assertNotEqual(proof_digest(issued.proof), session_digest(issued.proof))
        self.assertEqual(grant.scope, SensitiveOperationGrant.Scope.VAULT_SENSITIVE)
        self.assertEqual(grant.expires_at, grant.issued_at + GRANT_TTL)
        self.assertIsNone(grant.consumed_at); self.assertIsNone(grant.revoked_at)

    def test_grants_bind_to_exact_active_database_session(self):
        first = issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        other = Client(); other.force_login(self.user)
        second = issue_grant(actor=self.user, session_key=other.session.session_key, password="correct-password")
        self.assertNotEqual(
            SensitiveOperationGrant.objects.get(proof_digest=proof_digest(first.proof)).session_digest,
            SensitiveOperationGrant.objects.get(proof_digest=proof_digest(second.proof)).session_digest,
        )
        Session.objects.filter(session_key=self.session_key).delete()
        with self.assertRaises(ReauthenticationDenied):
            issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")

    def test_fifth_failure_throttles_and_success_resets_both_counters(self):
        for index in range(FAILURE_LIMIT):
            with self.assertRaises(ReauthenticationDenied) as caught:
                issue_grant(actor=self.user, session_key=self.session_key, password="wrong")
            self.assertEqual(caught.exception.throttled, index == FAILURE_LIMIT - 1)
        user_throttle = UserReauthenticationThrottle.objects.get(user=self.user)
        session_throttle = SessionReauthenticationThrottle.objects.get(user=self.user)
        self.assertEqual(user_throttle.failure_count, FAILURE_LIMIT)
        self.assertEqual(session_throttle.failure_count, FAILURE_LIMIT)
        user_throttle.failure_window_started_at = timezone.now() - __import__("datetime").timedelta(minutes=16)
        session_throttle.failure_window_started_at = user_throttle.failure_window_started_at
        user_throttle.save(); session_throttle.save()
        issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        self.assertEqual(UserReauthenticationThrottle.objects.get(user=self.user).failure_count, 0)
        self.assertEqual(SessionReauthenticationThrottle.objects.get(user=self.user).failure_count, 0)

    def test_three_live_grants_and_ten_issuance_state_are_enforced(self):
        for _ in range(3):
            issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        with self.assertRaises(ReauthenticationDenied):
            issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        SensitiveOperationGrant.objects.update(consumed_at=timezone.now())
        throttle = UserReauthenticationThrottle.objects.get(user=self.user)
        throttle.issuance_count = 9; throttle.save(update_fields=("issuance_count",))
        issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        SensitiveOperationGrant.objects.update(consumed_at=timezone.now())
        with self.assertRaises(ReauthenticationDenied):
            issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")

    @mock.patch("vault.grants.record_critical_event", side_effect=DatabaseError("audit unavailable"))
    def test_critical_audit_failure_rolls_back_issuance(self, _audit):
        with self.assertRaises(DatabaseError):
            issue_grant(actor=self.user, session_key=self.session_key, password="correct-password")
        self.assertFalse(SensitiveOperationGrant.objects.exists())
        self.assertFalse(UserReauthenticationThrottle.objects.exists())


class ReauthenticationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reauth@example.test", "correct-password")
        self.client = Client(enforce_csrf_checks=True); self.client.force_login(self.user)

    def csrf(self):
        return self.client.get("/api/v1/auth/csrf").json()["csrfToken"]

    def post(self, payload, token=True):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf()} if token else {}
        return self.client.post("/api/v1/vault/reauthenticate", payload, content_type="application/json", **headers)

    def test_success_contract_no_store_and_no_session_rotation(self):
        before = self.client.session.session_key
        response = self.post({"password": "correct-password"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.session.session_key, before)
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("correct-password", response.content.decode())
        self.assertTrue(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.VAULT_GRANT_ISSUED).exists())

    def test_csrf_and_authentication_are_required(self):
        self.assertEqual(self.post({"password": "correct-password"}, token=False).status_code, 403)
        anonymous = Client(enforce_csrf_checks=True)
        self.assertEqual(anonymous.post("/api/v1/vault/reauthenticate", {"password": "x"}, content_type="application/json").status_code, 403)

    def test_wrong_blank_and_malformed_passwords_share_safe_body(self):
        for payload in ({"password": "wrong"}, {"password": ""}, {}, []):
            response = self.post(payload)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json(), {"error": {"code": "reauthentication_failed", "message": "Reauthentication failed"}})


@override_settings(VAULT_GRANT_PEPPER="mysql-test-vault-grant-pepper-with-at-least-32-bytes")
class GrantMySQLConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative grant concurrency evidence")
        self.user = User.objects.create_user("grant-race@example.test", "correct-password")
        client = Client(); client.force_login(self.user); self.session_key = client.session.session_key

    def run_workers(self, count, password):
        start = threading.Barrier(count + 1); results = Queue()
        def worker():
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.user.pk); start.wait(timeout=10)
                issue_grant(actor=actor, session_key=self.session_key, password=password); results.put("issued")
            except ReauthenticationDenied as exc:
                results.put("throttled" if exc.throttled else "denied")
            except Exception as exc:
                results.put(type(exc).__name__)
            finally: close_old_connections()
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(count)]
        for thread in threads: thread.start()
        start.wait(timeout=10)
        for thread in threads: thread.join(timeout=40); self.assertFalse(thread.is_alive())
        return [results.get(timeout=2) for _ in threads]

    def test_concurrent_failures_stop_at_threshold(self):
        outcomes = self.run_workers(5, "wrong")
        self.assertEqual(outcomes.count("denied"), 4, outcomes); self.assertEqual(outcomes.count("throttled"), 1, outcomes)

    def test_concurrent_issuance_enforces_both_caps(self):
        outcomes = self.run_workers(4, "correct-password")
        self.assertEqual(outcomes.count("issued"), 3, outcomes); self.assertEqual(outcomes.count("denied"), 1, outcomes)
        SensitiveOperationGrant.objects.update(consumed_at=timezone.now())
        throttle = UserReauthenticationThrottle.objects.get(user=self.user)
        throttle.issuance_count = 9; throttle.save(update_fields=("issuance_count",))
        outcomes = self.run_workers(2, "correct-password")
        self.assertEqual(outcomes.count("issued"), 1, outcomes); self.assertEqual(outcomes.count("denied"), 1, outcomes)
