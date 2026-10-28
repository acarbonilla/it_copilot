from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.db import DatabaseError, close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase

from accounts.models import AccountDeletionReview, AdminLifecycleGuard, User
from accounts.lifecycle import LastActiveAdmin, deactivate_user
from security_audit.models import SecurityAuditEvent


class UserLifecycleApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@example.test", "long-admin-password", is_app_admin=True)
        self.second_admin = User.objects.create_user("admin2@example.test", "long-admin-password", is_app_admin=True)
        self.target = User.objects.create_user("target@example.test", "long-target-password", it_role=User.ITRole.IT_MEMBER)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.csrf = self.client.get("/api/v1/auth/csrf").json()["csrfToken"]

    def post(self, path, data=None):
        return self.client.post(path, data or {}, content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def patch_user(self, data):
        return self.client.patch(f"/api/v1/users/{self.target.pk}", data, content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def test_authorization_matrix_requires_active_app_admin(self):
        cases = (
            (None, 401),
            (User.objects.create_user("member@example.test", "long-password", it_role=User.ITRole.IT_DOC_ADMIN), 403),
            (User.objects.create_superuser("super@example.test", "long-password"), 403),
            (User.objects.create_user("inactive@example.test", "long-password", is_app_admin=True, is_active=False), 401),
        )
        for user, status in cases:
            with self.subTest(user=user, status=status):
                client = Client()
                if user:
                    client.force_login(user)
                self.assertEqual(client.get("/api/v1/users").status_code, status)

    def test_list_is_bounded_and_serializes_only_safe_fields(self):
        response = self.client.get("/api/v1/users?page_size=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["users"]), 2)
        self.assertEqual(set(response.json()["users"][0]), {"id", "email", "is_active", "is_app_admin", "it_role", "lifecycle_status"})
        self.assertEqual(self.client.get("/api/v1/users?page_size=101").status_code, 400)

    def test_patch_allowlist_validation_and_audit(self):
        self.assertEqual(self.patch_user({"email": "changed@example.test"}).status_code, 400)
        response = self.patch_user({"it_role": "IT_EDITOR", "is_app_admin": True})
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.it_role, User.ITRole.IT_EDITOR)
        self.assertTrue(self.target.is_app_admin)
        self.assertTrue(SecurityAuditEvent.objects.filter(action="account.role_changed", target_id=str(self.target.pk)).exists())

    def test_deactivation_revokes_all_sessions_and_reactivation_requires_login(self):
        one, two = Client(), Client()
        one.force_login(self.target)
        two.force_login(self.target)
        keys = {one.session.session_key, two.session.session_key}
        response = self.post(f"/api/v1/users/{self.target.pk}/deactivate")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Session.objects.filter(session_key__in=keys).exists())
        self.assertEqual(one.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(self.post(f"/api/v1/users/{self.target.pk}/reactivate").status_code, 200)
        self.assertEqual(one.get("/api/v1/auth/me").status_code, 401)

    def test_pending_invitation_cannot_be_reactivated(self):
        pending = User.objects.create_user("pending@example.test", None, is_active=False, lifecycle_state=User.LifecycleState.PENDING_INVITATION)
        self.assertEqual(self.post(f"/api/v1/users/{pending.pk}/reactivate").status_code, 400)

    def test_last_active_admin_cannot_be_deactivated_or_downgraded(self):
        self.second_admin.is_app_admin = False
        self.second_admin.save(update_fields=("is_app_admin",))
        self.assertEqual(self.post(f"/api/v1/users/{self.admin.pk}/deactivate").status_code, 409)
        response = self.client.patch(f"/api/v1/users/{self.admin.pk}", {"is_app_admin": False}, content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(response.status_code, 409)

    def test_deletion_review_is_non_destructive(self):
        sessions_before = Session.objects.count()
        response = self.post(f"/api/v1/users/{self.target.pk}/deletion-reviews", {"reason_code": "NO_LONGER_NEEDED"})
        self.assertEqual(response.status_code, 202)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())
        self.assertEqual(Session.objects.count(), sessions_before)
        self.assertEqual(AccountDeletionReview.objects.filter(target=self.target).count(), 1)

    def test_csrf_is_required_for_every_mutation(self):
        self.assertEqual(self.client.post(f"/api/v1/users/{self.target.pk}/deactivate").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/users/{self.target.pk}", {}, content_type="application/json").status_code, 403)

    def test_audit_failure_rolls_back_lifecycle_mutation_and_sessions(self):
        target_client = Client()
        target_client.force_login(self.target)
        key = target_client.session.session_key
        with patch("accounts.lifecycle.record_critical_event", side_effect=DatabaseError("injected")):
            response = self.post(f"/api/v1/users/{self.target.pk}/deactivate")
        self.assertEqual(response.status_code, 500)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertTrue(Session.objects.filter(session_key=key).exists())


@skipUnless(connection.vendor == "mysql", "Requires native MySQL row-lock semantics")
class LastAdminConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_deactivations_cannot_remove_both_admins(self):
        AdminLifecycleGuard.objects.get_or_create(pk=1)
        first = User.objects.create_user("first@example.test", "long-password", is_app_admin=True)
        second = User.objects.create_user("second@example.test", "long-password", is_app_admin=True)
        barrier = Barrier(2)

        def deactivate(actor_id, target_id):
            close_old_connections()
            barrier.wait()
            try:
                deactivate_user(actor=User.objects.get(pk=actor_id), target_id=target_id)
                return "success"
            except LastActiveAdmin:
                return "protected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda ids: deactivate(*ids), ((first.pk, second.pk), (second.pk, first.pk))))
        self.assertCountEqual(results, ["success", "protected"])
        self.assertEqual(User.objects.filter(is_active=True, is_app_admin=True, lifecycle_state=User.LifecycleState.ACTIVE).count(), 1)

