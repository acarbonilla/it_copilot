from unittest.mock import patch

from django.db import DatabaseError
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

    def test_health_rejects_unsupported_method_with_structured_error(self):
        response = self.client.post("/api/v1/health")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json(), {"error": {"code": "method_not_allowed", "message": 'Method "POST" not allowed.'}})

    def test_unknown_api_path_returns_structured_error(self):
        response = self.client.get("/api/v1/unknown")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": {"code": "not_found", "message": "Not found"}})


class MigrationGuardrailTests(SimpleTestCase):
    def test_auth_apps_are_not_installed_before_custom_user_model(self):
        from django.conf import settings

        self.assertNotIn("django.contrib.auth", settings.INSTALLED_APPS)
        self.assertNotIn("django.contrib.admin", settings.INSTALLED_APPS)
        self.assertNotIn("django.contrib.sessions", settings.INSTALLED_APPS)

    def test_only_one_url_pattern_is_registered(self):
        from config.urls import urlpatterns

        self.assertEqual(len(urlpatterns), 1)
        self.assertEqual(str(urlpatterns[0].pattern), "api/v1/health")
