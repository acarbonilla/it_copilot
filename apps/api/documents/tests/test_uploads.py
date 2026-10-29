import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase, override_settings
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from accounts.models import User
from documents.models import Document, DocumentVersion, OriginalArtifact, ProcessingJob
from documents.storage import ArtifactStorageError, PrivateArtifactStore
from documents.uploads import InvalidUpload, UploadFailed, create_document_upload
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event as persist_critical_event


class DocumentUploadServiceTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "private"
        self.store = PrivateArtifactStore(self.root)
        self.owner = User.objects.create_user("owner-upload@example.test", None, it_role=User.ITRole.IT_MEMBER)

    def upload(self, *, name="runbook.txt", content=b"private runbook", content_type="text/plain"):
        return create_document_upload(
            actor=self.owner,
            title="Runbook",
            description="Private",
            uploaded_file=SimpleUploadedFile(name, content, content_type=content_type),
            store=self.store,
        )

    def pdf_bytes(self, *, pages=1, encrypted=False):
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=72, height=72)
        if encrypted:
            writer.encrypt("secret")
        with tempfile.SpooledTemporaryFile() as output:
            writer.write(output)
            output.seek(0)
            return output.read()

    def active_pdf_bytes(self):
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
            {
                NameObject("/S"): NameObject("/JavaScript"),
                NameObject("/JS"): TextStringObject("app.alert('unsafe')"),
            }
        )
        with tempfile.SpooledTemporaryFile() as output:
            writer.write(output)
            output.seek(0)
            return output.read()

    def files(self):
        return [path for path in self.root.rglob("*") if path.is_file()]

    def test_txt_upload_atomically_creates_private_artifact_version_job_and_audit(self):
        result = self.upload(name="..\\sensitive-name.txt")
        artifact = OriginalArtifact.objects.get(document_version=result.version)
        result.document.refresh_from_db()
        self.assertEqual(result.document.owner, self.owner)
        self.assertEqual(result.document.candidate_version, result.version)
        self.assertIsNone(result.document.current_version)
        self.assertEqual(result.version.processing_state, DocumentVersion.ProcessingState.QUEUED)
        self.assertEqual(result.job.state, ProcessingJob.State.PENDING)
        self.assertEqual(artifact.original_filename, "sensitive-name.txt")
        self.assertEqual(artifact.detected_media_type, "text/plain")
        self.assertNotIn("sensitive", artifact.storage_key)
        self.assertEqual(self.store.resolve(artifact.storage_key).read_bytes(), b"private runbook")
        self.assertEqual(
            set(SecurityAuditEvent.objects.filter(target_id=str(result.document.pk)).values_list("action", flat=True)),
            {SecurityAuditEvent.Action.DOCUMENT_CREATED, SecurityAuditEvent.Action.DOCUMENT_UPLOAD_CREATED},
        )

    def test_markdown_pdf_and_duplicate_content_are_accepted_as_distinct_documents(self):
        markdown = self.upload(name="guide.md", content=b"# Guide\n", content_type="text/markdown")
        pdf = self.upload(name="guide.pdf", content=self.pdf_bytes(), content_type="application/pdf")
        duplicate = self.upload()
        self.assertEqual(Document.objects.count(), 3)
        self.assertNotEqual(markdown.document.pk, duplicate.document.pk)
        self.assertEqual(OriginalArtifact.objects.get(document_version=pdf.version).detected_media_type, "application/pdf")

    @override_settings(DOCUMENT_MAX_PDF_PAGES=2)
    def test_rejects_malformed_encrypted_over_page_limit_and_unsupported_content(self):
        cases = (
            ("bad.pdf", b"%PDF-not-valid", "application/pdf"),
            ("encrypted.pdf", self.pdf_bytes(encrypted=True), "application/pdf"),
            ("many.pdf", self.pdf_bytes(pages=3), "application/pdf"),
            ("active.pdf", self.active_pdf_bytes(), "application/pdf"),
            ("binary.txt", b"\xff\xfe", "text/plain"),
            ("nul.md", b"safe\x00unsafe", "text/markdown"),
            ("archive.zip", b"PK\x03\x04", "application/zip"),
            ("wrong.txt", b"plain", "application/pdf"),
        )
        for name, content, content_type in cases:
            with self.subTest(name=name), self.assertRaises(InvalidUpload):
                self.upload(name=name, content=content, content_type=content_type)
        self.assertFalse(Document.objects.exists())
        self.assertEqual(self.files(), [])

    @override_settings(DOCUMENT_MAX_FILE_BYTES=4)
    def test_rejects_oversize_file_without_database_or_artifact(self):
        with self.assertRaises(InvalidUpload):
            self.upload(content=b"12345")
        self.assertFalse(Document.objects.exists())
        self.assertEqual(self.files(), [])

    def test_artifact_database_audit_and_enqueue_failures_compensate(self):
        failure_points = (
            patch.object(self.store, "write_upload", side_effect=ArtifactStorageError("disk failure")),
            patch("documents.uploads.OriginalArtifact.objects.create", side_effect=DatabaseError("database failure")),
            patch("documents.uploads.ProcessingJob.objects.create", side_effect=DatabaseError("enqueue failure")),
            patch("documents.uploads.record_critical_event", side_effect=DatabaseError("audit failure")),
        )
        for failure in failure_points:
            with self.subTest(failure=failure.attribute if hasattr(failure, "attribute") else repr(failure)):
                with failure, self.assertRaises((UploadFailed, DatabaseError)):
                    self.upload()
                self.assertFalse(Document.objects.exists())
                self.assertFalse(DocumentVersion.objects.exists())
                self.assertFalse(OriginalArtifact.objects.exists())
                self.assertFalse(ProcessingJob.objects.exists())
                self.assertEqual(self.files(), [])

    def test_second_critical_audit_failure_rolls_back_first_audit_and_every_artifact(self):
        calls = 0

        def fail_second_audit(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise DatabaseError("second audit unavailable")
            return persist_critical_event(**kwargs)

        with patch("documents.uploads.record_critical_event", side_effect=fail_second_audit), self.assertRaises(DatabaseError):
            self.upload()
        self.assertFalse(Document.objects.exists())
        self.assertFalse(SecurityAuditEvent.objects.exists())
        self.assertEqual(self.files(), [])

    def test_cleanup_failure_quarantines_uncommitted_artifact(self):
        with (
            patch("documents.uploads.record_critical_event", side_effect=DatabaseError("audit failure")),
            patch.object(self.store, "delete", side_effect=OSError("delete failure")),
            self.assertRaises(DatabaseError),
        ):
            self.upload()
        self.assertFalse(Document.objects.exists())
        quarantined = self.files()
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0].parent.name, "quarantine")

    def test_deactivation_or_role_loss_before_upload_is_denied(self):
        stale = self.owner
        for changes in (
            {"is_active": False, "lifecycle_state": User.LifecycleState.DEACTIVATED},
            {"is_active": True, "lifecycle_state": User.LifecycleState.ACTIVE, "it_role": User.ITRole.NONE},
        ):
            User.objects.filter(pk=stale.pk).update(**changes)
            with self.assertRaises(PermissionDenied):
                self.upload()
            self.assertFalse(Document.objects.exists())
