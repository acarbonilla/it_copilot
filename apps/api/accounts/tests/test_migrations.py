from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.models import CreateModel
from django.test import SimpleTestCase


class CustomUserMigrationGraphTests(SimpleTestCase):
    def test_custom_user_is_configured_and_created_in_initial_migration(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        migration = loader.disk_migrations[("accounts", "0001_initial")]

        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertTrue(migration.initial)
        self.assertTrue(
            any(isinstance(operation, CreateModel) and operation.name == "User" for operation in migration.operations)
        )

    def test_default_auth_user_create_operation_is_swappable(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        migration = loader.disk_migrations[("auth", "0001_initial")]
        user_operation = next(
            operation
            for operation in migration.operations
            if isinstance(operation, CreateModel) and operation.name == "User"
        )

        self.assertEqual(user_operation.options["swappable"], "AUTH_USER_MODEL")
