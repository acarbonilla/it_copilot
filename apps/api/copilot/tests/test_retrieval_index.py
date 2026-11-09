import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings

from accounts.models import User
from documents.processor import process_one
from documents.models import DocumentRetrievalChange
from documents.retrieval import (
    RetrievalBoundaryError, RetrievalCandidate, authorize_retrieval_candidates,
    list_indexable_versions, open_verified_extracted_text,
)
from documents.storage import PrivateArtifactStore
from documents.uploads import create_document_upload

from copilot.indexing import (
    IndexLeaseLost, claim_next_index_job, consume_retrieval_changes, fail_index_job,
    heartbeat_index_job, process_one_index_job,
)
from copilot.models import RetrievalChunk, RetrievalIndexGeneration, RetrievalIndexJob
from copilot.reconciliation import inventory_index_issues, repair_index_issues
from copilot.retrieval import retrieve_authorized_evidence


class RetrievalIndexTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private"
        settings_override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=self.root)
        settings_override.enable(); self.addCleanup(settings_override.disable)
        self.store = PrivateArtifactStore(self.root); self.addCleanup(self.store.close)
        self.owner = User.objects.create_user("owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.other = User.objects.create_user("other@example.test", None, it_role=User.ITRole.IT_MEMBER)

    def ready_document(self, text=b"reset password with the secure portal"):
        uploaded = create_document_upload(
            actor=self.owner, title="Password reset", description="",
            uploaded_file=SimpleUploadedFile("private.txt", text, content_type="text/plain"),
            store=self.store,
        )
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store), "succeeded")
        uploaded.document.refresh_from_db(); uploaded.version.refresh_from_db()
        return uploaded

    def index(self, uploaded):
        consume_retrieval_changes()
        self.assertEqual(process_one_index_job(store=self.store), "succeeded")
        return RetrievalIndexGeneration.objects.get(document=uploaded.document, status="PUBLISHED")

    def test_f03_boundary_lists_and_opens_without_storage_key(self):
        uploaded = self.ready_document()
        page = list_indexable_versions(limit=1)
        self.assertEqual(page.items[0].version_id, uploaded.version.pk)
        verified = open_verified_extracted_text(
            version_id=uploaded.version.pk,
            expected_digest=uploaded.version.extracted_text_artifact.sha256_digest,
            store=self.store,
        )
        self.assertIn("reset password", verified.stream.read())
        self.assertFalse(hasattr(verified, "storage_key"))

    def test_corrupt_text_fails_closed(self):
        uploaded = self.ready_document()
        artifact = uploaded.version.extracted_text_artifact
        self.store.resolve(artifact.storage_key).write_text("tampered", encoding="utf-8")
        with self.assertRaises(RetrievalBoundaryError):
            open_verified_extracted_text(version_id=uploaded.version.pk, expected_digest=artifact.sha256_digest, store=self.store)

    def test_authorization_matrix_and_candidate_limit(self):
        uploaded = self.ready_document()
        digest = uploaded.version.extracted_text_artifact.sha256_digest
        candidate = RetrievalCandidate(uploaded.document.pk, uploaded.version.pk, digest)
        self.assertEqual(authorize_retrieval_candidates(actor=self.other, candidates=(candidate,), store=self.store), ())
        admin = User.objects.create_user("docadmin@example.test", None, it_role=User.ITRole.IT_DOC_ADMIN)
        self.assertEqual(len(authorize_retrieval_candidates(actor=admin, candidates=(candidate,), store=self.store)), 1)
        app_admin = User.objects.create_user("appadmin@example.test", None, is_app_admin=True)
        self.assertEqual(authorize_retrieval_candidates(actor=app_admin, candidates=(candidate,), store=self.store), ())
        self.owner.it_role = User.ITRole.NONE; self.owner.save()
        self.assertEqual(authorize_retrieval_candidates(actor=self.owner, candidates=(candidate,), store=self.store), ())
        with self.assertRaises(ValueError):
            authorize_retrieval_candidates(actor=self.owner, candidates=(candidate,) * 41, store=self.store)

    def test_outbox_index_and_bounded_authorized_retrieval(self):
        uploaded = self.ready_document(); self.index(uploaded)
        result = retrieve_authorized_evidence(actor=self.owner, question="reset password", store=self.store)
        self.assertFalse(result.insufficient_evidence)
        self.assertLessEqual(len(result.evidence), 8)
        self.assertTrue(all(item.document_id == uploaded.document.pk for item in result.evidence))
        self.assertTrue(retrieve_authorized_evidence(actor=self.other, question="reset password", store=self.store).insufficient_evidence)

    def test_deactivation_and_archive_are_immediate(self):
        uploaded = self.ready_document(); self.index(uploaded)
        self.owner.lifecycle_state = User.LifecycleState.DEACTIVATED; self.owner.save()
        self.assertTrue(retrieve_authorized_evidence(actor=self.owner, question="reset", store=self.store).insufficient_evidence)
        self.owner.lifecycle_state = User.LifecycleState.ACTIVE; self.owner.save()
        uploaded.document.visibility = uploaded.document.Visibility.ARCHIVED; uploaded.document.save()
        self.assertTrue(retrieve_authorized_evidence(actor=self.owner, question="reset", store=self.store).insufficient_evidence)

    def test_claim_heartbeat_retry_and_stale_fencing(self):
        self.ready_document(); consume_retrieval_changes()
        worker = uuid.uuid4(); claim = claim_next_index_job(worker_id=worker)
        self.assertTrue(heartbeat_index_job(claim))
        self.assertEqual(fail_index_job(claim, error_code="controlled", retryable=True), "RETRY_WAIT")
        with self.assertRaises(IndexLeaseLost):
            fail_index_job(claim, error_code="stale", retryable=False)

    def test_publication_rolls_back_on_chunk_insert_failure(self):
        uploaded = self.ready_document(); consume_retrieval_changes()
        with patch.object(RetrievalChunk.objects, "bulk_create", side_effect=RuntimeError("db failure")):
            self.assertEqual(process_one_index_job(store=self.store), "retry")
        self.assertFalse(RetrievalIndexGeneration.objects.exists())
        self.assertFalse(RetrievalChunk.objects.exists())

    def test_reconciliation_is_dry_run_then_bounded_repair(self):
        uploaded = self.ready_document()
        issues, cursor, complete = inventory_index_issues(limit=100)
        self.assertIn("missing_generation", {item.code for item in issues})
        self.assertFalse(RetrievalIndexJob.objects.exists())
        self.assertEqual(repair_index_issues(issues=issues), len(issues))
        self.assertTrue(RetrievalIndexJob.objects.filter(document_version=uploaded.version).exists())

    def test_outbox_requires_transaction(self):
        uploaded = self.ready_document()
        self.assertTrue(DocumentRetrievalChange.objects.filter(document=uploaded.document).exists())
