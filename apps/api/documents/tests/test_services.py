from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.test import TestCase, TransactionTestCase

from accounts.models import User
from documents.models import Document
from documents.services import (
    DocumentConflictError,
    archive_document,
    create_document,
    delete_document,
    restore_document,
    update_document_metadata,
)
from security_audit.models import SecurityAuditEvent


class DocumentServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.other = User.objects.create_user("other@example.test", None, it_role=User.ITRole.IT_EDITOR)
        self.doc_admin = User.objects.create_user("docadmin@example.test", None, it_role=User.ITRole.IT_DOC_ADMIN)
        self.app_admin = User.objects.create_user("appadmin@example.test", None, is_app_admin=True)

    def test_create_update_archive_restore_delete_and_atomic_audit(self):
        document = create_document(actor=self.owner, title="  Runbook  ", description="  Private  ")
        self.assertEqual((document.title, document.description, document.metadata_revision), ("Runbook", "Private", 1))
        self.assertTrue(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.DOCUMENT_CREATED).exists())

        document = update_document_metadata(
            actor=self.owner, document_id=document.pk, expected_revision=1, title="Revised"
        )
        self.assertEqual((document.title, document.metadata_revision), ("Revised", 2))
        result = archive_document(actor=self.owner, document_id=document.pk, expected_revision=2)
        self.assertEqual((result.previous_visibility, result.document.visibility), (Document.Visibility.ACTIVE, Document.Visibility.ARCHIVED))
        result = restore_document(actor=self.owner, document_id=document.pk, expected_revision=3)
        self.assertEqual(result.document.visibility, Document.Visibility.ACTIVE)
        result = delete_document(actor=self.owner, document_id=document.pk, expected_revision=4)
        self.assertEqual(result.document.visibility, Document.Visibility.DELETED)
        self.assertIsNotNone(result.document.deleted_at)
        self.assertEqual(
            list(SecurityAuditEvent.objects.filter(target_id=str(document.pk)).values_list("action", flat=True)),
            [
                SecurityAuditEvent.Action.DOCUMENT_DELETED,
                SecurityAuditEvent.Action.DOCUMENT_RESTORED,
                SecurityAuditEvent.Action.DOCUMENT_ARCHIVED,
                SecurityAuditEvent.Action.DOCUMENT_METADATA_UPDATED,
                SecurityAuditEvent.Action.DOCUMENT_CREATED,
            ],
        )

    def test_stale_revision_and_invalid_transition_do_not_mutate_or_audit(self):
        document = create_document(actor=self.owner, title="Runbook")
        initial_events = SecurityAuditEvent.objects.count()
        with self.assertRaises(DocumentConflictError):
            update_document_metadata(actor=self.owner, document_id=document.pk, expected_revision=99, title="Lost")
        with self.assertRaises(DocumentConflictError):
            restore_document(actor=self.owner, document_id=document.pk, expected_revision=1)
        document.refresh_from_db()
        self.assertEqual((document.title, document.metadata_revision, document.visibility), ("Runbook", 1, Document.Visibility.ACTIVE))
        self.assertEqual(SecurityAuditEvent.objects.count(), initial_events)

    def test_doc_admin_can_manage_cross_owner_document(self):
        document = create_document(actor=self.owner, title="Runbook")
        updated = update_document_metadata(
            actor=self.doc_admin, document_id=document.pk, expected_revision=1, description="Managed"
        )
        self.assertEqual(updated.description, "Managed")
        self.assertEqual(updated.owner_id, self.owner.pk)

    def test_create_audit_failure_rolls_back_document(self):
        with patch("documents.services.record_critical_event", side_effect=DatabaseError("audit unavailable")):
            with self.assertRaises(DatabaseError):
                create_document(actor=self.owner, title="Never committed")
        self.assertFalse(Document.objects.exists())

    def test_lifecycle_audit_failure_rolls_back_transition(self):
        document = create_document(actor=self.owner, title="Runbook")
        with patch("documents.services.record_critical_event", side_effect=DatabaseError("audit unavailable")):
            with self.assertRaises(DatabaseError):
                archive_document(actor=self.owner, document_id=document.pk, expected_revision=1)
        document.refresh_from_db()
        self.assertEqual((document.visibility, document.metadata_revision), (Document.Visibility.ACTIVE, 1))


class DocumentDenialAuditTests(TransactionTestCase):
    def test_cross_owner_and_app_admin_are_denied_with_controlled_audit(self):
        owner = User.objects.create_user("owner-denial@example.test", None, it_role=User.ITRole.IT_MEMBER)
        other = User.objects.create_user("other-denial@example.test", None, it_role=User.ITRole.IT_EDITOR)
        app_admin = User.objects.create_user("appadmin-denial@example.test", None, is_app_admin=True)
        document = create_document(actor=owner, title="Runbook")
        for actor in (other, app_admin):
            with self.subTest(actor=actor.email):
                with self.assertRaises(PermissionDenied):
                    update_document_metadata(actor=actor, document_id=document.pk, expected_revision=1, title="Forbidden")
        denied = SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED)
        self.assertEqual(denied.count(), 2)
        self.assertEqual(set(denied.values_list("target_id", flat=True)), {str(document.pk)})
