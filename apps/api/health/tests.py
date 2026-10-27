import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, OperationalError
from django.test import SimpleTestCase
from rest_framework.test import APIClient


class HealthApiTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("health.views.connections")
    def test_health_returns_200_when_database_is_available(self, connections):
        cursor = connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        cursor.execute.assert_called_once_with("SELECT 1")

    @patch("health.views.connections")
    def test_health_returns_safe_503_when_database_is_unavailable(self, connections):
        connections.__getitem__.return_value.cursor.side_effect = DatabaseError("password=secret")
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": {"code": "database_unavailable", "message": "Service temporarily unavailable"}})
        self.assertNotIn("secret", response.content.decode())

    @patch("health.views.connections")
    def test_health_returns_safe_503_when_database_read_times_out(self, connections):
        connections.__getitem__.return_value.cursor.side_effect = OperationalError("read timed out: password=secret")
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": {"code": "database_unavailable", "message": "Service temporarily unavailable"}})
        self.assertNotIn("timed out", response.content.decode())
        self.assertNotIn("secret", response.content.decode())

    @patch("health.views.connections")
    def test_html_accept_header_returns_json_without_template_rendering(self, connections):
        response = self.client.get("/api/v1/health", HTTP_ACCEPT="text/html")
        self.assertEqual(response.status_code, 406)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"error": {"code": "not_acceptable", "message": "Could not satisfy the request Accept header."}})

    def test_health_rejects_unsupported_method_with_structured_error(self):
        response = self.client.post("/api/v1/health")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json(), {"error": {"code": "method_not_allowed", "message": 'Method "POST" not allowed.'}})

    def test_unknown_api_path_returns_structured_error(self):
        response = self.client.get("/api/v1/unknown")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": {"code": "not_found", "message": "Not found"}})


class MigrationGuardrailTests(SimpleTestCase):
    def test_auth_uses_configured_custom_user_model(self):
        from django.conf import settings

        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertIn("django.contrib.auth", settings.INSTALLED_APPS)
        self.assertIn("django.contrib.sessions", settings.INSTALLED_APPS)
        self.assertIn("accounts", settings.INSTALLED_APPS)
        self.assertNotIn("django.contrib.admin", settings.INSTALLED_APPS)

    def test_health_and_approved_auth_url_patterns_are_registered(self):
        from config.urls import urlpatterns

        self.assertEqual(
            {str(pattern.pattern) for pattern in urlpatterns},
            {
                "api/v1/health",
                "api/v1/auth/csrf",
                "api/v1/auth/login",
                "api/v1/auth/logout",
                "api/v1/auth/me",
            },
        )

    def test_mysql_network_timeouts_are_finite(self):
        from config.settings import local

        options = local.DATABASES["default"]["OPTIONS"]
        for timeout in ("connect_timeout", "read_timeout", "write_timeout"):
            self.assertIsInstance(options[timeout], int)
            self.assertGreater(options[timeout], 0)

    def test_non_positive_mysql_timeout_is_rejected(self):
        from config.settings.local import positive_timeout

        with patch.dict(os.environ, {"MYSQL_READ_TIMEOUT": "0"}):
            with self.assertRaisesMessage(ImproperlyConfigured, "MYSQL_READ_TIMEOUT must be a positive integer"):
                positive_timeout("MYSQL_READ_TIMEOUT")
