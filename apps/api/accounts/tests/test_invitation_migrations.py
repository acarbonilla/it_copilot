from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from accounts.models import AccountInvitation, User
from security_audit.models import SecurityAuditEvent


class InvitationMigrationTests(TestCase):
    def test_forward_migrations_and_dependencies_exist(self):
        loader = MigrationLoader(connection)
        accounts_migration = loader.disk_migrations[("accounts", "0002_account_invitation")]
        audit_migration = loader.disk_migrations[("security_audit", "0002_ic006_event_vocabulary")]
        self.assertIn(("accounts", "0001_initial"), accounts_migration.dependencies)
        self.assertIn(("security_audit", "0001_initial"), audit_migration.dependencies)

    def test_invitation_table_and_user_lifecycle_column_exist(self):
        self.assertIn(AccountInvitation._meta.db_table, connection.introspection.table_names())
        with connection.cursor() as cursor:
            invitation_columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, AccountInvitation._meta.db_table)
            }
            user_columns = {
                column.name for column in connection.introspection.get_table_description(cursor, User._meta.db_table)
            }
        self.assertEqual(
            invitation_columns,
            {"id", "user_id", "token_digest", "created_at", "expires_at", "consumed_at", "revoked_at", "invited_by_user_id"},
        )
        self.assertIn("lifecycle_state", user_columns)

    def test_ic006_audit_vocabulary_is_available(self):
        self.assertEqual(SecurityAuditEvent.Action.ACCOUNT_ACTIVATION_SUCCEEDED, "account.activation_succeeded")
        self.assertEqual(SecurityAuditEvent.Action.ACCOUNT_ACTIVATION_DENIED, "account.activation_denied")
        self.assertEqual(SecurityAuditEvent.TargetType.ACCOUNT_INVITATION, "account_invitation")
