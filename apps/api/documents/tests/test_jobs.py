import threading
import uuid
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from documents.jobs import JobClaim, LeaseLost, claim_next_job, fail_claim, heartbeat, publish_claim
from documents.models import Document, DocumentVersion, ExtractedTextArtifact, ProcessingJob
from documents.storage import StoredArtifact
from documents.services import archive_document


def create_pending_job():
    owner = User.objects.create_user(f"{uuid.uuid4().hex}@example.test", None, it_role=User.ITRole.IT_MEMBER)
    document = Document.objects.create(owner=owner, title="Queued")
    version = DocumentVersion.objects.create(
        document=document,
        sequence=1,
        processing_state=DocumentVersion.ProcessingState.QUEUED,
        created_by_user_id=owner.pk,
    )
    document.candidate_version = version
    document.save(update_fields=("candidate_version", "updated_at"))
    job = ProcessingJob.objects.create(document_version=version, available_at=timezone.now())
    return document, version, job


class ProcessingJobLifecycleTests(TestCase):
    def test_claim_heartbeat_retry_and_exhaustion_are_bounded(self):
        _, version, job = create_pending_job()
        worker = uuid.uuid4()
        claim = claim_next_job(worker_id=worker)
        self.assertEqual(claim.attempt, 1)
        self.assertTrue(heartbeat(claim))
        now = timezone.now()
        self.assertEqual(fail_claim(claim, error_code="worker_failure", retryable=True, now=now), ProcessingJob.State.RETRY_WAIT)
        job.refresh_from_db()
        self.assertEqual(job.available_at, now + timedelta(seconds=5))

        claim = claim_next_job(worker_id=worker, now=job.available_at)
        self.assertEqual(claim.attempt, 2)
        now = job.available_at
        self.assertEqual(fail_claim(claim, error_code="worker_failure", retryable=True, now=now), ProcessingJob.State.RETRY_WAIT)
        job.refresh_from_db()
        self.assertEqual(job.available_at, now + timedelta(seconds=30))

        claim = claim_next_job(worker_id=worker, now=job.available_at)
        self.assertEqual(claim.attempt, 3)
        self.assertEqual(fail_claim(claim, error_code="worker_failure", retryable=True, now=job.available_at), ProcessingJob.State.FAILED)
        job.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(job.attempt_count, 3)
        self.assertIsNone(job.nonterminal_slot)
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.FAILED)

    def test_expired_claim_is_reclaimed_and_stale_worker_is_fenced(self):
        _, _, job = create_pending_job()
        first = claim_next_job(worker_id=uuid.uuid4())
        expired = timezone.now() - timedelta(seconds=1)
        ProcessingJob.objects.filter(pk=job.pk).update(lease_expires_at=expired)
        second = claim_next_job(worker_id=uuid.uuid4(), now=timezone.now())
        self.assertEqual(second.job_id, first.job_id)
        self.assertEqual(second.attempt, 2)
        self.assertFalse(heartbeat(first))
        with self.assertRaises(LeaseLost):
            fail_claim(first, error_code="stale", retryable=True)

    def test_publication_revalidates_and_is_transactional(self):
        document, version, job = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        stored = StoredArtifact("extracted/" + version.pk.hex + "/" + uuid.uuid4().hex + ".txt", "a" * 64, 4)
        with patch.object(ExtractedTextArtifact.objects, "create", side_effect=RuntimeError("database failure")):
            with self.assertRaises(RuntimeError):
                publish_claim(claim, stored=stored, character_count=4, page_count=None, extractor_version="test")
        job.refresh_from_db()
        document.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(job.state, ProcessingJob.State.RUNNING)
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.PROCESSING)
        self.assertIsNone(document.current_version_id)

        artifact = publish_claim(claim, stored=stored, character_count=4, page_count=None, extractor_version="test")
        document.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(artifact.document_version_id, version.pk)
        self.assertEqual(document.current_version_id, version.pk)
        self.assertIsNone(document.candidate_version_id)
        self.assertEqual(job.state, ProcessingJob.State.SUCCEEDED)
        with self.assertRaises(LeaseLost):
            publish_claim(claim, stored=stored, character_count=4, page_count=None, extractor_version="test")

    def test_cancelled_or_archived_document_cannot_be_claimed(self):
        document, version, job = create_pending_job()
        document.visibility = Document.Visibility.ARCHIVED
        document.save(update_fields=("visibility", "updated_at"))
        self.assertIsNone(claim_next_job(worker_id=uuid.uuid4()))
        job.refresh_from_db()
        self.assertEqual(job.state, ProcessingJob.State.PENDING)
        document.visibility = Document.Visibility.ACTIVE
        document.save(update_fields=("visibility", "updated_at"))
        job.cancellation_requested = True
        job.save(update_fields=("cancellation_requested", "updated_at"))
        self.assertIsNone(claim_next_job(worker_id=uuid.uuid4()))

    def test_archive_cancels_running_job_and_fences_completion(self):
        document, version, job = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        archive_document(actor=document.owner, document_id=document.pk, expected_revision=1)
        job.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(job.state, ProcessingJob.State.CANCELLED)
        self.assertTrue(job.cancellation_requested)
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.CANCELLED)
        self.assertFalse(heartbeat(claim))

    def test_archive_audit_failure_rolls_back_job_cancellation(self):
        document, version, job = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        with patch("documents.services.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                archive_document(actor=document.owner, document_id=document.pk, expected_revision=1)
        document.refresh_from_db()
        version.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(document.visibility, Document.Visibility.ACTIVE)
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.PROCESSING)
        self.assertEqual(job.state, ProcessingJob.State.RUNNING)
        self.assertTrue(heartbeat(claim))


@skipUnless(connection.vendor == "mysql", "Native MySQL concurrency evidence")
class ProcessingJobConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_competing_workers_claim_only_one_attempt(self):
        _, _, job = create_pending_job()
        barrier = threading.Barrier(2)
        outcomes = []

        def claimant():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                claim = claim_next_job(worker_id=uuid.uuid4())
                outcomes.append(None if claim is None else claim.job_id)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=claimant) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(outcomes.count(job.pk), 1)
        self.assertEqual(outcomes.count(None), 1)
        job.refresh_from_db()
        self.assertEqual(job.attempt_count, 1)

    def test_competing_completion_accepts_only_one_result(self):
        document, version, _ = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        barrier = threading.Barrier(2)
        outcomes = []

        def publisher(index):
            close_old_connections()
            stored = StoredArtifact(
                f"extracted/{version.pk.hex}/{index:032x}.txt",
                f"{index:064x}",
                4,
            )
            try:
                barrier.wait(timeout=10)
                publish_claim(claim, stored=stored, character_count=4, page_count=None, extractor_version="test")
                outcomes.append("success")
            except LeaseLost:
                outcomes.append("stale")
            finally:
                close_old_connections()

        threads = [threading.Thread(target=publisher, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ["success", "stale"])
        self.assertEqual(ExtractedTextArtifact.objects.filter(document_version=version).count(), 1)
        document.refresh_from_db()
        self.assertEqual(document.current_version_id, version.pk)

    def test_archive_completion_race_never_exposes_active_stale_result(self):
        document, version, job = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        barrier = threading.Barrier(2)
        outcomes = []

        def publisher():
            close_old_connections()
            stored = StoredArtifact(f"extracted/{version.pk.hex}/{uuid.uuid4().hex}.txt", "b" * 64, 4)
            try:
                barrier.wait(timeout=10)
                publish_claim(claim, stored=stored, character_count=4, page_count=None, extractor_version="test")
                outcomes.append("published")
            except LeaseLost:
                outcomes.append("fenced")
            finally:
                close_old_connections()

        def archiver():
            close_old_connections()
            try:
                actor = User.objects.get(pk=document.owner_id)
                barrier.wait(timeout=10)
                archive_document(actor=actor, document_id=document.pk, expected_revision=1)
                outcomes.append("archived")
            finally:
                close_old_connections()

        threads = [threading.Thread(target=publisher), threading.Thread(target=archiver)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        document.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(document.visibility, Document.Visibility.ARCHIVED)
        self.assertIn("archived", outcomes)
        self.assertIn(job.state, {ProcessingJob.State.SUCCEEDED, ProcessingJob.State.CANCELLED})
        self.assertLessEqual(ExtractedTextArtifact.objects.filter(document_version=version).count(), 1)
