import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from documents.models import Document, DocumentVersion, ProcessingJob
from documents.storage import PrivateArtifactStore
from documents.services import archive_document, delete_document
from documents.uploads import create_document_upload


class DocumentApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner-api@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.other = User.objects.create_user("other-api@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.doc_admin = User.objects.create_user("doc-admin-api@example.test", None, it_role=User.ITRole.IT_DOC_ADMIN)
        self.app_admin = User.objects.create_user("app-admin-api@example.test", None, is_app_admin=True)
        self.document = Document.objects.create(owner=self.owner, title="Private title", description="Private description")
        self.other_document = Document.objects.create(owner=self.other, title="Other title")
        self.client = APIClient()

    def test_list_is_owner_scoped_doc_admin_wide_and_app_admin_operational_only(self):
        self.client.force_login(self.owner)
        response = self.client.get("/api/v1/documents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["documents"]], [str(self.document.pk)])

        self.client.force_login(self.doc_admin)
        response = self.client.get("/api/v1/documents?ordering=title&page_size=100")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pagination"]["count"], 2)

        self.client.force_login(self.app_admin)
        item = self.client.get("/api/v1/documents").json()["documents"][0]
        self.assertNotIn("title", item)
        self.assertNotIn("description", item)
        self.assertFalse(any(item["capabilities"].values()))
        self.assertEqual(self.client.get(f"/api/v1/documents/{self.document.pk}/download").status_code, 404)

    def test_cross_owner_direct_access_is_generic_and_inactive_is_denied(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/v1/documents/{self.document.pk}")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (404, "not_found"))
        self.owner.is_active = False
        self.owner.save(update_fields=("is_active",))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/v1/documents").status_code, 401)

    def test_metadata_and_lifecycle_require_revision_and_csrf(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.patch(f"/api/v1/documents/{self.document.pk}",
                                     {"title": "Changed", "expected_revision": 1}, format="json")
        self.assertEqual((response.status_code, response.json()["error"]["code"]), (403, "csrf_failed"))
        self.client.force_login(self.owner)
        response = self.client.patch(f"/api/v1/documents/{self.document.pk}",
                                     {"title": "Changed", "expected_revision": 1}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["document"]["metadata_revision"], 2)
        self.assertEqual(self.client.post(f"/api/v1/documents/{self.document.pk}/archive",
                                         {"expected_revision": 1}, format="json").status_code, 409)
        self.assertEqual(self.client.post(f"/api/v1/documents/{self.document.pk}/archive",
                                         {"expected_revision": 2}, format="json").status_code, 200)

    def test_retry_creates_one_job_for_failed_candidate(self):
        version = DocumentVersion.objects.create(document=self.document, sequence=1,
            processing_state=DocumentVersion.ProcessingState.FAILED, created_by_user_id=self.owner.pk)
        self.document.candidate_version = version
        self.document.save(update_fields=("candidate_version", "updated_at"))
        self.client.force_login(self.owner)
        url = f"/api/v1/documents/{self.document.pk}/retry"
        response = self.client.post(url, {"expected_revision": 1, "version_id": str(version.pk)}, format="json")
        self.assertEqual(response.status_code, 202, response.content)
        self.assertEqual(ProcessingJob.objects.filter(document_version=version).count(), 1)
        self.assertEqual(self.client.post(url, {"expected_revision": 1, "version_id": str(version.pk)}, format="json").status_code, 409)

    def test_retry_audit_failure_rolls_back_job_and_version(self):
        version = DocumentVersion.objects.create(document=self.document, sequence=1,
            processing_state=DocumentVersion.ProcessingState.FAILED, created_by_user_id=self.owner.pk)
        self.document.candidate_version = version
        self.document.save(update_fields=("candidate_version", "updated_at"))
        self.client.force_login(self.owner)
        with patch("documents.services.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            response = self.client.post(f"/api/v1/documents/{self.document.pk}/retry",
                {"expected_revision": 1, "version_id": str(version.pk)}, format="json")
        self.assertEqual(response.status_code, 500)
        version.refresh_from_db()
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.FAILED)
        self.assertFalse(ProcessingJob.objects.filter(document_version=version).exists())

    def test_private_download_is_attachment_integrity_checked_and_not_cached(self):
        with tempfile.TemporaryDirectory() as root, override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(root) / "private"):
            store = PrivateArtifactStore()
            uploaded = create_document_upload(actor=self.owner, title="Download",
                description="", uploaded_file=SimpleUploadedFile("safe.txt", b"safe text", content_type="text/plain"),
                store=store)
            self.client.force_login(self.owner)
            store_patch = patch("documents.views.PrivateArtifactStore", return_value=store)
            store_patch.start()
            self.addCleanup(store_patch.stop)
            response = self.client.get(f"/api/v1/documents/{uploaded.document.pk}/download")
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment", response["Content-Disposition"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            artifact_path = store.resolve(uploaded.version.original_artifact.storage_key)
            replacement = artifact_path.with_suffix(".replacement")
            replacement.write_bytes(b"unverified replacement")
            replacement_succeeded = False
            try:
                os.replace(replacement, artifact_path)
                replacement_succeeded = True
            except PermissionError:
                replacement.unlink(missing_ok=True)
            archive_document(actor=self.owner, document_id=uploaded.document.pk, expected_revision=1)
            delete_document(actor=self.owner, document_id=uploaded.document.pk, expected_revision=2)
            self.assertEqual(b"".join(response.streaming_content), b"safe text")
            self.assertIsNone(store._root_lock)
            if replacement_succeeded:
                self.assertEqual(artifact_path.read_bytes(), b"unverified replacement")
            uploaded.document.refresh_from_db()
            self.assertEqual(uploaded.document.visibility, Document.Visibility.DELETED)

    def test_deleted_document_download_is_denied_before_storage_is_opened(self):
        self.client.force_login(self.owner)
        delete_document(actor=self.owner, document_id=self.document.pk, expected_revision=1)
        with patch("documents.views.PrivateArtifactStore") as store_class:
            response = self.client.get(f"/api/v1/documents/{self.document.pk}/download")
        self.assertEqual(response.status_code, 404)
        store_class.assert_not_called()

    def test_download_integrity_error_closes_file_and_store_resources(self):
        with tempfile.TemporaryDirectory() as root, override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(root) / "private"):
            store = PrivateArtifactStore()
            uploaded = create_document_upload(actor=self.owner, title="Download", description="",
                uploaded_file=SimpleUploadedFile("safe.txt", b"safe text", content_type="text/plain"), store=store)
            uploaded.version.original_artifact.sha256_digest = "0" * 64
            uploaded.version.original_artifact.save(update_fields=("sha256_digest",))
            self.client.force_login(self.owner)
            with patch("documents.views.PrivateArtifactStore", return_value=store):
                response = self.client.get(f"/api/v1/documents/{uploaded.document.pk}/download")
            self.assertEqual(response.status_code, 404)
            self.assertIsNone(store._root_lock)
