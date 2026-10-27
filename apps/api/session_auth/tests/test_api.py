from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings

from accounts.models import User


FRONTEND_ORIGIN = "http://localhost:3000"


class SessionAuthApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            "user@example.com",
            "correct-password",
            is_app_admin=True,
            it_role=User.ITRole.IT_EDITOR,
        )

    def csrf_token(self, client=None):
        client = client or self.client
        response = client.get("/api/v1/auth/csrf", HTTP_ORIGIN=FRONTEND_ORIGIN)
        self.assertEqual(response.status_code, 200)
        return response.json()["csrfToken"]

    def login(self, client=None, **credentials):
        client = client or self.client
        token = self.csrf_token(client)
        payload = {"email": self.user.email, "password": "correct-password"}
        payload.update(credentials)
        return client.post(
            "/api/v1/auth/login",
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )

    def test_successful_login_returns_minimal_identity_and_creates_session(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"user": {"id": self.user.pk, "email": self.user.email, "is_app_admin": True, "it_role": User.ITRole.IT_EDITOR}},
        )
        self.assertTrue(self.client.session.session_key)
        self.assertTrue(Session.objects.filter(session_key=self.client.session.session_key).exists())
        self.assertNotIn("password", response.content.decode())

    def test_login_rotates_existing_session_identifier(self):
        session = self.client.session
        session["anonymous_marker"] = True
        session.save()
        original_key = session.session_key

        self.assertEqual(self.login().status_code, 200)

        self.assertNotEqual(self.client.session.session_key, original_key)
        self.assertFalse(Session.objects.filter(session_key=original_key).exists())

    def test_invalid_nonexistent_blank_and_inactive_credentials_share_safe_error(self):
        inactive = User.objects.create_user("inactive@example.com", "correct-password", is_active=False)
        attempts = [
            {"email": self.user.email, "password": "wrong"},
            {"email": "missing@example.com", "password": "wrong"},
            {"email": "", "password": "wrong"},
            {"email": "   ", "password": "wrong"},
            {"email": inactive.email, "password": "correct-password"},
        ]
        for credentials in attempts:
            client = Client(enforce_csrf_checks=True)
            response = self.login(client, **credentials)
            with self.subTest(credentials=credentials):
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"error": {"code": "invalid_credentials", "message": "Invalid email or password"}})
                self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_authenticated_me_and_anonymous_rejection(self):
        anonymous = self.client.get("/api/v1/auth/me")
        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(anonymous.json()["error"]["code"], "authentication_required")

        self.assertEqual(self.login().status_code, 200)
        response = self.client.get("/api/v1/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], self.user.email)

    def test_deactivation_denies_next_request_with_existing_cookie(self):
        self.assertEqual(self.login().status_code, 200)
        session_key = self.client.session.session_key
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 401)
        self.assertTrue(Session.objects.filter(session_key=session_key).exists())

    def test_logout_invalidates_server_session_and_cookie_replay(self):
        self.assertEqual(self.login().status_code, 200)
        token = self.csrf_token()
        old_key = self.client.session.session_key

        response = self.client.post(
            "/api/v1/auth/logout",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())

        self.client.cookies[settings.SESSION_COOKIE_NAME] = old_key
        replay = self.client.get("/api/v1/auth/me")
        self.assertEqual(replay.status_code, 401)

    def test_missing_and_invalid_csrf_rejected_on_login(self):
        missing = self.client.post(
            "/api/v1/auth/login",
            {"email": self.user.email, "password": "correct-password"},
            content_type="application/json",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        invalid = self.client.post(
            "/api/v1/auth/login",
            {"email": self.user.email, "password": "correct-password"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN="invalid",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        for response in (missing, invalid):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json(), {"error": {"code": "csrf_failed", "message": "CSRF validation failed"}})
            self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_missing_and_invalid_csrf_rejected_on_logout(self):
        self.assertEqual(self.login().status_code, 200)
        missing = self.client.post("/api/v1/auth/logout", HTTP_ORIGIN=FRONTEND_ORIGIN)
        invalid = self.client.post(
            "/api/v1/auth/logout",
            HTTP_X_CSRFTOKEN="invalid",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
        )
        for response in (missing, invalid):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "csrf_failed")

    def test_disallowed_origin_is_rejected_with_valid_token(self):
        token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": self.user.email, "password": "correct-password"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="http://evil.example",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "csrf_failed")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_unsafe_https_referer_is_rejected_with_valid_token(self):
        token = self.csrf_token()
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": self.user.email, "password": "correct-password"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_REFERER="https://evil.example/login",
            secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "csrf_failed")

    def test_cookie_flags_and_exact_origin_cors(self):
        csrf_response = self.client.get("/api/v1/auth/csrf", HTTP_ORIGIN=FRONTEND_ORIGIN)
        csrf_cookie = csrf_response.cookies[settings.CSRF_COOKIE_NAME]
        self.assertEqual(csrf_cookie["samesite"], "Lax")
        self.assertEqual(csrf_cookie["httponly"], "")
        self.assertEqual(csrf_cookie["secure"], "")
        self.assertEqual(csrf_response.headers["Access-Control-Allow-Origin"], FRONTEND_ORIGIN)
        self.assertEqual(csrf_response.headers["Access-Control-Allow-Credentials"], "true")

        login_response = self.login()
        session_cookie = login_response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(session_cookie["samesite"], "Lax")
        self.assertTrue(session_cookie["httponly"])
        self.assertEqual(session_cookie["secure"], "")

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_https_execution_context_uses_secure_cookies(self):
        csrf_response = self.client.get("/api/v1/auth/csrf", secure=True)
        self.assertTrue(csrf_response.cookies[settings.CSRF_COOKIE_NAME]["secure"])

        token = csrf_response.json()["csrfToken"]
        login_response = self.client.post(
            "/api/v1/auth/login",
            {"email": self.user.email, "password": "correct-password"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://localhost:8000",
            HTTP_HOST="localhost:8000",
            secure=True,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.cookies[settings.SESSION_COOKIE_NAME]["secure"])

    def test_credentialed_cors_preflight_is_exact_origin_only(self):
        allowed = self.client.options(
            "/api/v1/auth/login",
            HTTP_ORIGIN=FRONTEND_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type,x-csrftoken",
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers["Access-Control-Allow-Origin"], FRONTEND_ORIGIN)
        self.assertEqual(allowed.headers["Access-Control-Allow-Credentials"], "true")
        self.assertIn("x-csrftoken", allowed.headers["Access-Control-Allow-Headers"])

        denied = self.client.options(
            "/api/v1/auth/login",
            HTTP_ORIGIN="http://evil.example",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertNotIn("Access-Control-Allow-Origin", denied.headers)
