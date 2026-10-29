import io
import hashlib
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase, override_settings

from accounts.models import User
from documents.extraction_isolation import ExtractionResult
from documents.models import DocumentVersion, ExtractedTextArtifact, ProcessingJob
from documents.processor import process_one
from documents.storage import PrivateArtifactStore
from documents.uploads import create_document_upload


class DocumentProcessorTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private"
        self.settings = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=self.root)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.store = PrivateArtifactStore(self.root)
        self.addCleanup(self.store.close)
        self.owner = User.objects.create_user("worker-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)

    def upload(self, content=b"private secret\r\ntext"):
        return create_document_upload(
            actor=self.owner,
            title="Private",
            description="",
            uploaded_file=SimpleUploadedFile("sensitive-name.txt", content, content_type="text/plain"),
            store=self.store,
        )

    def test_worker_extracts_and_publishes_private_text(self):
        uploaded = self.upload()
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store), "succeeded")
        uploaded.document.refresh_from_db()
        uploaded.version.refresh_from_db()
        uploaded.job.refresh_from_db()
        artifact = ExtractedTextArtifact.objects.get(document_version=uploaded.version)
        self.assertEqual(uploaded.document.current_version_id, uploaded.version.pk)
        self.assertIsNone(uploaded.document.candidate_version_id)
        self.assertEqual(uploaded.version.processing_state, DocumentVersion.ProcessingState.READY)
        self.assertEqual(uploaded.job.state, ProcessingJob.State.SUCCEEDED)
        self.assertEqual(self.store.resolve(artifact.storage_key).read_text(encoding="utf-8"), "private secret\ntext")

    def test_missing_original_fails_without_result(self):
        uploaded = self.upload()
        self.store.delete(uploaded.version.original_artifact.storage_key)
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store), "failed")
        uploaded.job.refresh_from_db()
        uploaded.version.refresh_from_db()
        self.assertEqual(uploaded.job.state, ProcessingJob.State.FAILED)
        self.assertEqual(uploaded.job.last_error_code, "artifact_invalid")
        self.assertEqual(uploaded.version.processing_state, DocumentVersion.ProcessingState.FAILED)
        self.assertFalse(ExtractedTextArtifact.objects.exists())

    def test_corrupted_original_fails_integrity_check(self):
        uploaded = self.upload()
        self.store.resolve(uploaded.version.original_artifact.storage_key).write_bytes(b"tampered")
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store), "failed")
        uploaded.job.refresh_from_db()
        self.assertEqual(uploaded.job.last_error_code, "artifact_invalid")
        self.assertFalse(ExtractedTextArtifact.objects.exists())

    def test_publication_failure_removes_staged_output(self):
        self.upload()

        def runner(**kwargs):
            data = b"result"
            kwargs["output_path"].write_bytes(data)
            return ExtractionResult(6, 6, "f6a214f7a2c223c4f1c8e1f0a3e34c4d6f203f995a63f6f54f4f4c2325552e38", None, "test")

        # Digest mismatch fails closed and the unreferenced staging file is removed.
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store, extraction_runner=runner), "failed")
        self.assertEqual(list((self.root / "extracted").rglob("*.txt")), [])
        self.assertFalse(ExtractedTextArtifact.objects.exists())

    def test_database_publication_failure_removes_staged_output(self):
        self.upload()

        def runner(**kwargs):
            data = b"result"
            kwargs["output_path"].write_bytes(data)
            return ExtractionResult(6, 6, hashlib.sha256(data).hexdigest(), None, "test")

        with patch("documents.processor.publish_claim", side_effect=DatabaseError("database failure")):
            self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store, extraction_runner=runner), "retry")
        self.assertEqual(list((self.root / "extracted").rglob("*.txt")), [])
        self.assertFalse(ExtractedTextArtifact.objects.exists())

    def test_command_log_contains_no_filename_or_content(self):
        self.upload(b"SYNTHETIC_WORKER_SECRET")
        self.store.close()
        output = io.StringIO()
        with patch("documents.management.commands.process_documents.process_one", return_value="succeeded"):
            call_command("process_documents", "--once", stdout=output)
        logged = output.getvalue()
        self.assertIn("outcome=succeeded", logged)
        self.assertNotIn("sensitive-name", logged)
        self.assertNotIn("SYNTHETIC_WORKER_SECRET", logged)
        self.assertNotIn(str(self.root), logged)
