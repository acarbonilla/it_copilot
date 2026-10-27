from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.models import CreateModel
from django.test import SimpleTestCase


class SessionMigrationGraphTests(SimpleTestCase):
    def test_database_session_backend_and_initial_migration(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        migration = loader.disk_migrations[("sessions", "0001_initial")]

        self.assertTrue(any(isinstance(operation, CreateModel) and operation.name == "Session" for operation in migration.operations))
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        self.assertIn("django.contrib.sessions", settings.INSTALLED_APPS)
