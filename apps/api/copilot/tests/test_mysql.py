import tempfile
import threading
import uuid
import importlib
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from unittest import skipUnless

from accounts.models import User
from documents.processor import process_one
from documents.models import ArtifactPublicationGuard
from documents.models import Document
from documents.services import archive_document, delete_document
from documents.storage import PrivateArtifactStore
from documents.uploads import create_document_upload

from copilot.indexing import (
    IndexLeaseLost, claim_next_index_job, consume_retrieval_changes, fail_index_job,
    heartbeat_index_job, process_one_index_job, publish_index_generation,
)
from copilot.chunking import chunk_text
from copilot.models import RetrievalChunk, RetrievalIndexGeneration, RetrievalIndexJob
from copilot.retrieval import retrieve_authorized_evidence


@skipUnless(connection.vendor == "mysql", "Native MySQL contract")
class NativeMySQLRetrievalTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        ArtifactPublicationGuard.objects.get_or_create(pk=1, defaults={"singleton": True})
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "private"
        settings_override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=self.root)
        settings_override.enable(); self.addCleanup(settings_override.disable)
        self.store = PrivateArtifactStore(self.root); self.addCleanup(self.store.close)
        self.owner = User.objects.create_user("mysql-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)

    def ready(self, text=b"kerberos authentication troubleshooting uniquephrase"):
        uploaded = create_document_upload(
            actor=self.owner, title="Kerberos guide", description="",
            uploaded_file=SimpleUploadedFile("guide.txt", text, content_type="text/plain"), store=self.store,
        )
        self.assertEqual(process_one(worker_id=uuid.uuid4(), store=self.store), "succeeded")
        uploaded.document.refresh_from_db(); uploaded.version.refresh_from_db()
        return uploaded

    def indexed(self):
        uploaded = self.ready()
        consume_retrieval_changes()
        self.assertEqual(process_one_index_job(store=self.store), "succeeded")
        return uploaded

    def assert_mutation_serializes_after_evidence_release(self, mutation, *, evidence_after=False):
        uploaded = self.indexed()
        entered = threading.Event(); release = threading.Event(); mutation_done = threading.Event()
        results = []; errors = []
        from documents.retrieval import release_authorized_evidence as real_release

        def controlled_release(**kwargs):
            materialize = kwargs["materialize"]

            def controlled_materialize(authorized):
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("test release synchronization timed out")
                return materialize(authorized)

            return real_release(**{**kwargs, "materialize": controlled_materialize})

        def retrieve():
            try:
                connections.close_all()
                actor = User.objects.get(pk=self.owner.pk)
                with patch("copilot.retrieval.release_authorized_evidence", side_effect=controlled_release):
                    results.append(retrieve_authorized_evidence(actor=actor, question="kerberos uniquephrase"))
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        def mutate():
            try:
                connections.close_all(); mutation(uploaded)
            except Exception as exc:
                errors.append(exc)
            finally:
                mutation_done.set(); connections.close_all()

        retrieval_thread = threading.Thread(target=retrieve)
        retrieval_thread.start(); self.assertTrue(entered.wait(10))
        mutation_thread = threading.Thread(target=mutate)
        mutation_thread.start()
        self.assertFalse(mutation_done.wait(0.25), "mutation escaped the evidence-release locks")
        release.set()
        retrieval_thread.join(15); mutation_thread.join(15)
        self.assertFalse(retrieval_thread.is_alive()); self.assertFalse(mutation_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertFalse(results[0].insufficient_evidence)
        after = retrieve_authorized_evidence(actor=User.objects.get(pk=self.owner.pk), question="kerberos uniquephrase")
        self.assertEqual(not after.insufficient_evidence, evidence_after)

    def test_fulltext_index_exists_and_natural_language_retrieves(self):
        self.ready(); consume_retrieval_changes(); self.assertEqual(process_one_index_job(store=self.store), "succeeded")
        with connection.cursor() as cursor:
            cursor.execute("SHOW INDEX FROM copilot_retrievalchunk WHERE Key_name = %s", ["copilot_chunk_text_fulltext"])
            self.assertTrue(cursor.fetchall())
        result = retrieve_authorized_evidence(actor=self.owner, question="kerberos uniquephrase", store=self.store)
        self.assertFalse(result.insufficient_evidence)

    def test_short_and_punctuation_only_queries_fail_safely(self):
        self.ready(b"DNS IP MFA VPN support reference"); consume_retrieval_changes()
        self.assertEqual(process_one_index_job(store=self.store), "succeeded")
        punctuation = retrieve_authorized_evidence(actor=self.owner, question="---", store=self.store)
        self.assertTrue(punctuation.insufficient_evidence)
        short = retrieve_authorized_evidence(actor=self.owner, question="IP", store=self.store)
        self.assertLessEqual(len(short.evidence), 8)

    def test_concurrent_claim_is_exclusive(self):
        self.ready(); consume_retrieval_changes()
        barrier = threading.Barrier(2); claims = []; errors = []

        def claim():
            try:
                connections.close_all(); barrier.wait()
                claims.append(claim_next_index_job(worker_id=uuid.uuid4()))
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(15)
        self.assertEqual(errors, [])
        self.assertEqual(sum(item is not None for item in claims), 1)

    def test_generation_publication_rolls_back_atomically(self):
        self.ready(); consume_retrieval_changes()
        with patch.object(RetrievalChunk.objects, "bulk_create", side_effect=RuntimeError("controlled")):
            self.assertEqual(process_one_index_job(store=self.store), "retry")
        self.assertFalse(RetrievalIndexGeneration.objects.exists())
        self.assertFalse(RetrievalChunk.objects.exists())

    def test_lease_expiry_fences_stale_worker(self):
        self.ready(); consume_retrieval_changes()
        start = timezone.now(); stale = claim_next_index_job(worker_id=uuid.uuid4(), now=start)
        replacement = claim_next_index_job(worker_id=uuid.uuid4(), now=start + timedelta(seconds=61))
        self.assertIsNotNone(replacement)
        self.assertFalse(heartbeat_index_job(stale, now=start + timedelta(seconds=61)))
        with self.assertRaises(IndexLeaseLost):
            fail_index_job(stale, error_code="stale", retryable=False, now=start + timedelta(seconds=61))

    def test_retries_are_bounded_and_terminal(self):
        self.ready(); consume_retrieval_changes(); now = timezone.now()
        for attempt in range(3):
            claim = claim_next_index_job(worker_id=uuid.uuid4(), now=now)
            self.assertIsNotNone(claim)
            state = fail_index_job(claim, error_code="controlled", retryable=True, now=now)
            if attempt < 2:
                self.assertEqual(state, "RETRY_WAIT")
                now += timedelta(seconds=(5, 30)[attempt])
            else:
                self.assertEqual(state, "FAILED")

    def test_archive_serializes_after_evidence_release(self):
        def mutation(uploaded):
            document = Document.objects.get(pk=uploaded.document.pk)
            archive_document(actor=User.objects.get(pk=self.owner.pk), document_id=document.pk,
                             expected_revision=document.metadata_revision)
        self.assert_mutation_serializes_after_evidence_release(mutation)

    def test_delete_serializes_after_evidence_release(self):
        def mutation(uploaded):
            document = Document.objects.get(pk=uploaded.document.pk)
            delete_document(actor=User.objects.get(pk=self.owner.pk), document_id=document.pk,
                            expected_revision=document.metadata_revision)
        self.assert_mutation_serializes_after_evidence_release(mutation)

    def test_version_replacement_serializes_after_evidence_release(self):
        def mutation(uploaded):
            with transaction.atomic():
                document = Document.objects.select_for_update().get(pk=uploaded.document.pk)
                document.current_version = None
                document.save(update_fields=("current_version", "updated_at"))
        self.assert_mutation_serializes_after_evidence_release(mutation)

    def test_role_removal_serializes_after_evidence_release(self):
        def mutation(uploaded):
            User.objects.filter(pk=self.owner.pk).update(it_role=User.ITRole.NONE)
        self.assert_mutation_serializes_after_evidence_release(mutation)

    def test_deactivation_serializes_after_evidence_release(self):
        def mutation(uploaded):
            User.objects.filter(pk=self.owner.pk).update(lifecycle_state=User.LifecycleState.DEACTIVATED)
        self.assert_mutation_serializes_after_evidence_release(mutation)

    def test_publication_serializes_after_evidence_release(self):
        def mutation(uploaded):
            job = RetrievalIndexJob.objects.create(
                document_version_id=uploaded.version.pk,
                source_digest=uploaded.version.extracted_text_artifact.sha256_digest,
                available_at=timezone.now(),
            )
            claim = claim_next_index_job(worker_id=uuid.uuid4())
            self.assertEqual(claim.job_id, job.pk)
            publish_index_generation(claim, chunk_text("kerberos uniquephrase replacement"))
        self.assert_mutation_serializes_after_evidence_release(mutation, evidence_after=True)

    def test_fulltext_partial_state_is_resumable_and_validated(self):
        migration = importlib.import_module("copilot.migrations.0002_retrieval_chunk_fulltext")
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE copilot_retrievalchunk DROP INDEX copilot_chunk_text_fulltext")
            try:
                cursor.execute(
                    "CREATE FULLTEXT INDEX copilot_chunk_text_fulltext "
                    "ON copilot_retrievalchunk (searchable_text)"
                )
                raise RuntimeError("injected failure after nontransactional DDL")
            except RuntimeError:
                pass
        with connection.schema_editor(atomic=False) as schema_editor:
            migration.ensure_fulltext_index(None, schema_editor)
            migration.ensure_fulltext_index(None, schema_editor)
        with connection.cursor() as cursor:
            cursor.execute("SHOW INDEX FROM copilot_retrievalchunk WHERE Key_name = %s", ["copilot_chunk_text_fulltext"])
            rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0][10]).upper(), "FULLTEXT")

    def test_incompatible_fulltext_partial_state_is_rejected(self):
        migration = importlib.import_module("copilot.migrations.0002_retrieval_chunk_fulltext")
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE copilot_retrievalchunk DROP INDEX copilot_chunk_text_fulltext")
            cursor.execute("CREATE INDEX copilot_chunk_text_fulltext ON copilot_retrievalchunk (token_count)")
        try:
            with self.assertRaisesRegex(RuntimeError, "Incompatible existing"):
                with connection.schema_editor(atomic=False) as schema_editor:
                    migration.ensure_fulltext_index(None, schema_editor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE copilot_retrievalchunk DROP INDEX copilot_chunk_text_fulltext")
            with connection.schema_editor(atomic=False) as schema_editor:
                migration.ensure_fulltext_index(None, schema_editor)
