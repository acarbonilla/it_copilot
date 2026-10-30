from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase

from security_audit.models import SecurityAuditEvent


class DocumentMigrationContractTests(SimpleTestCase):
    databases = {"default"}

    def test_initial_schema_and_audit_vocabulary_migrations_exist(self):
        loader = MigrationLoader(connection)
        self.assertIn(("documents", "0001_initial"), loader.disk_migrations)
        self.assertIn(("documents", "0003_originalartifact"), loader.disk_migrations)
        self.assertIn(("documents", "0004_processing_metadata"), loader.disk_migrations)
        self.assertIn(("security_audit", "0007_remove_securityauditevent_audit_action_known_and_more"), loader.disk_migrations)
        audit = loader.disk_migrations[("security_audit", "0005_remove_securityauditevent_audit_action_known_and_more")]
        self.assertIn(("security_audit", "0004_f02_sec_001_invitation_events"), audit.dependencies)

    def test_document_audit_vocabulary_is_controlled(self):
        self.assertEqual(
            {
                SecurityAuditEvent.Action.DOCUMENT_CREATED,
                SecurityAuditEvent.Action.DOCUMENT_METADATA_UPDATED,
                SecurityAuditEvent.Action.DOCUMENT_ARCHIVED,
                SecurityAuditEvent.Action.DOCUMENT_RESTORED,
                SecurityAuditEvent.Action.DOCUMENT_DELETED,
                SecurityAuditEvent.Action.DOCUMENT_UPLOAD_CREATED,
                SecurityAuditEvent.Action.DOCUMENT_RETRY_REQUESTED,
            },
            {
                "document.created",
                "document.metadata_updated",
                "document.archived",
                "document.restored",
                "document.deleted",
                "document.upload_created",
                "document.retry_requested",
            },
        )
