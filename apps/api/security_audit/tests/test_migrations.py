from django.db import connection
from django.test import TestCase

from security_audit.models import SecurityAuditEvent


class AuditMigrationTests(TestCase):
    def test_audit_table_and_expected_columns_exist(self):
        table = SecurityAuditEvent._meta.db_table
        self.assertIn(table, connection.introspection.table_names())
        with connection.cursor() as cursor:
            columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
        self.assertEqual(
            columns,
            {"id", "action", "actor_user_id", "target_type", "target_id", "outcome", "occurred_at", "request_id"},
        )

    def test_actor_snapshot_is_not_a_foreign_key(self):
        field = SecurityAuditEvent._meta.get_field("actor_user_id")
        self.assertFalse(field.is_relation)
