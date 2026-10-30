from django.test import TestCase

from accounts.models import User
from documents.models import Document
from documents.policies import DocumentCapability, authorize_document, visible_documents


class DocumentPolicyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.editor = User.objects.create_user("editor@example.test", None, it_role=User.ITRole.IT_EDITOR)
        self.doc_admin = User.objects.create_user("docadmin@example.test", None, it_role=User.ITRole.IT_DOC_ADMIN)
        self.app_admin = User.objects.create_user("appadmin@example.test", None, is_app_admin=True)
        self.combined = User.objects.create_user(
            "combined@example.test", None, is_app_admin=True, it_role=User.ITRole.IT_EDITOR
        )
        self.document = Document.objects.create(owner=self.owner, title="Private runbook")

    def test_owner_capabilities_and_cross_owner_denial(self):
        owner_actions = (
            DocumentCapability.VIEW_METADATA,
            DocumentCapability.EDIT_METADATA,
            DocumentCapability.VIEW_CONTENT,
            DocumentCapability.DOWNLOAD,
            DocumentCapability.PROCESS,
            DocumentCapability.ARCHIVE,
            DocumentCapability.DELETE,
        )
        for capability in owner_actions:
            with self.subTest(capability=capability):
                self.assertTrue(authorize_document(self.owner, capability, document=self.document).allowed)
                self.assertFalse(authorize_document(self.editor, capability, document=self.document).allowed)

    def test_it_doc_admin_has_cross_owner_content_access(self):
        for capability in DocumentCapability:
            if capability not in {DocumentCapability.CREATE, DocumentCapability.OPERATIONAL_METADATA}:
                with self.subTest(capability=capability):
                    self.assertTrue(authorize_document(self.doc_admin, capability, document=self.document).allowed)

    def test_app_admin_has_operational_metadata_but_no_document_content(self):
        self.assertTrue(authorize_document(self.app_admin, DocumentCapability.OPERATIONAL_METADATA).allowed)
        for capability in (
            DocumentCapability.VIEW_METADATA,
            DocumentCapability.EDIT_METADATA,
            DocumentCapability.VIEW_CONTENT,
            DocumentCapability.DOWNLOAD,
            DocumentCapability.PROCESS,
            DocumentCapability.ARCHIVE,
            DocumentCapability.RESTORE,
            DocumentCapability.DELETE,
        ):
            with self.subTest(capability=capability):
                self.assertFalse(authorize_document(self.app_admin, capability, document=self.document).allowed)

    def test_combined_app_admin_uses_only_it_role_document_rights(self):
        owned = Document.objects.create(owner=self.combined, title="Owned")
        self.assertTrue(authorize_document(self.combined, DocumentCapability.DOWNLOAD, document=owned).allowed)
        self.assertFalse(authorize_document(self.combined, DocumentCapability.DOWNLOAD, document=self.document).allowed)
        self.assertTrue(authorize_document(self.combined, DocumentCapability.OPERATIONAL_METADATA).allowed)

    def test_inactive_deactivated_and_deleted_documents_are_denied(self):
        self.owner.is_active = False
        self.owner.lifecycle_state = User.LifecycleState.DEACTIVATED
        self.owner.save(update_fields=("is_active", "lifecycle_state"))
        self.assertFalse(authorize_document(self.owner, DocumentCapability.VIEW_CONTENT, document=self.document).allowed)
        self.document.visibility = Document.Visibility.DELETED
        self.document.deleted_at = self.document.updated_at
        self.document.save(update_fields=("visibility", "deleted_at"))
        self.assertFalse(authorize_document(self.doc_admin, DocumentCapability.VIEW_CONTENT, document=self.document).allowed)

    def test_visible_queryset_is_owner_scoped_admin_wide_and_deleted_excluded(self):
        other = Document.objects.create(owner=self.editor, title="Other")
        deleted = Document.objects.create(owner=self.owner, title="Deleted")
        deleted.visibility = Document.Visibility.DELETED
        deleted.deleted_at = deleted.updated_at
        deleted.save(update_fields=("visibility", "deleted_at"))
        self.assertEqual(set(visible_documents(self.owner).values_list("pk", flat=True)), {self.document.pk})
        self.assertEqual(set(visible_documents(self.doc_admin).values_list("pk", flat=True)), {self.document.pk, other.pk})
        self.assertFalse(visible_documents(self.app_admin).exists())
