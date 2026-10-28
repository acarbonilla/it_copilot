import json
import tempfile
from pathlib import Path

from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import AccountInvitation, User
from security_audit.models import SecurityAuditEvent


FRONTEND_ORIGIN = "http://localhost:3000"


class InvitationApiTests(TransactionTestCase):
    def setUp(self):
        self.mailbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.mailbox.cleanup)
        self.settings_override = override_settings(
            DEBUG=True,
            INVITATION_DELIVERY_MODE="file",
            INVITATION_MAILBOX_ROOT=Path(self.mailbox.name),
            INVITATION_ACTIVATION_BASE_URL="http://localhost:3000/activate",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.admin = User.objects.create_user("admin@example.test", "correct-admin-password", is_app_admin=True)

    def csrf(self, client):
        return client.get("/api/v1/auth/csrf", HTTP_ORIGIN=FRONTEND_ORIGIN).json()["csrfToken"]

    def authenticated_client(self, user):
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        return client, self.csrf(client)

    def invite(self, client, token, **overrides):
        payload = {"email": "invitee@example.test", "it_role": User.ITRole.IT_MEMBER, "is_app_admin": False}
        payload.update(overrides)
        return client.post(
            "/api/v1/users/invitations",
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )

    def delivered_token(self, invitation_id):
        artifact = Path(self.mailbox.name) / f"{invitation_id}.json"
        return json.loads(artifact.read_text(encoding="utf-8"))["activation_url"].rsplit("/", 1)[-1]

    def activate(self, client, csrf_token, token, password="unique-long-passphrase-4829"):
        return client.post(
            "/api/v1/auth/activate",
            {"token": token, "password": password},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )

    def test_invite_authorization_and_csrf_matrix(self):
        anonymous = Client(enforce_csrf_checks=True)
        anonymous_token = self.csrf(anonymous)
        self.assertEqual(self.invite(anonymous, anonymous_token).status_code, 401)

        subjects = (
            User.objects.create_user("member@example.test", "password", it_role=User.ITRole.IT_MEMBER),
            User.objects.create_user("it-admin@example.test", "password", it_role=User.ITRole.IT_DOC_ADMIN),
            User.objects.create_user("inactive-admin@example.test", "password", is_app_admin=True, is_active=False),
        )
        unknown_role_admin = User.objects.create_user("unknown-admin@example.test", "password", is_app_admin=True)
        User.objects.filter(pk=unknown_role_admin.pk).update(it_role="UNKNOWN")
        unknown_role_admin.refresh_from_db()
        subjects += (unknown_role_admin,)
        for subject in subjects:
            client, token = self.authenticated_client(subject)
            response = self.invite(client, token, email=f"target-{subject.pk}@example.test")
            with self.subTest(subject=subject.email):
                self.assertEqual(response.status_code, 401 if not subject.is_active else 403)

        admin_client, _ = self.authenticated_client(self.admin)
        missing_csrf = admin_client.post(
            "/api/v1/users/invitations",
            {"email": "missing-csrf@example.test", "it_role": User.ITRole.IT_MEMBER, "is_app_admin": False},
            content_type="application/json",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"]["code"], "csrf_failed")

    def test_admin_invite_response_is_bounded_and_contains_no_secret(self):
        client, token = self.authenticated_client(self.admin)
        with self.assertNoLogs("accounts.invitations"):
            response = self.invite(client, token)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body["invitation"]), {"id", "status", "expires_at"})
        secret = self.delivered_token(body["invitation"]["id"])
        self.assertNotIn(secret, response.content.decode())
        self.assertNotIn("activation_url", response.content.decode())

    def test_activation_requires_csrf_and_does_not_create_session(self):
        admin_client, token = self.authenticated_client(self.admin)
        invitation_response = self.invite(admin_client, token)
        invitation_id = invitation_response.json()["invitation"]["id"]
        secret = self.delivered_token(invitation_id)
        client = Client(enforce_csrf_checks=True)
        missing = client.post(
            "/api/v1/auth/activate",
            {"token": secret, "password": "unique-long-passphrase-4829"},
            content_type="application/json",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        self.assertEqual(missing.status_code, 403)
        response = self.activate(client, self.csrf(client), secret)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "activated"})
        self.assertNotIn("sessionid", response.cookies)
        self.assertNotIn("user", response.json())

    def test_invalid_expired_revoked_reused_and_unknown_tokens_share_response(self):
        client, csrf_token = self.authenticated_client(self.admin)
        responses = []
        for email, state in (("expired@example.test", "expired"), ("revoked@example.test", "revoked"), ("reused@example.test", "reused")):
            invitation_response = self.invite(client, csrf_token, email=email)
            invitation_id = invitation_response.json()["invitation"]["id"]
            secret = self.delivered_token(invitation_id)
            if state == "expired":
                AccountInvitation.objects.filter(pk=invitation_id).update(expires_at=timezone.now())
            elif state == "revoked":
                AccountInvitation.objects.filter(pk=invitation_id).update(revoked_at=timezone.now())
            else:
                self.assertEqual(self.activate(client, csrf_token, secret).status_code, 200)
            responses.append(self.activate(client, csrf_token, secret))
        responses.extend((
            self.activate(client, csrf_token, "x" * 43),
            self.activate(client, csrf_token, "malformed token"),
        ))
        expected = {"error": {"code": "invalid_activation", "message": "Activation request is invalid"}}
        for response in responses:
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), expected)

    def test_weak_password_has_bounded_error_and_does_not_consume(self):
        client, csrf_token = self.authenticated_client(self.admin)
        invitation_response = self.invite(client, csrf_token)
        invitation_id = invitation_response.json()["invitation"]["id"]
        response = self.activate(client, csrf_token, self.delivered_token(invitation_id), password="password12345")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "password_policy_failed")
        self.assertNotIn("common", response.content.decode().lower())
        self.assertIsNone(AccountInvitation.objects.get(pk=invitation_id).consumed_at)

    def test_no_public_account_creation_route_exists(self):
        client = Client()
        for path in ("/api/v1/users", "/api/v1/auth/register", "/api/v1/auth/signup"):
            with self.subTest(path=path):
                self.assertEqual(client.post(path, {}, content_type="application/json").status_code, 404)

    def test_invalid_activation_records_sanitized_denial_without_token(self):
        client = Client(enforce_csrf_checks=True)
        token = self.csrf(client)
        secret = "x" * 43
        with self.assertLogs("django.request", level="WARNING") as captured:
            response = self.activate(client, token, secret)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(secret, " ".join(captured.output))
        self.assertTrue(
            SecurityAuditEvent.objects.filter(
                action=SecurityAuditEvent.Action.ACCOUNT_ACTIVATION_DENIED,
                target_type=SecurityAuditEvent.TargetType.ACCOUNT_INVITATION,
                outcome=SecurityAuditEvent.Outcome.DENIED,
            ).exists()
        )
