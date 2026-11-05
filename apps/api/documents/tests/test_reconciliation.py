import tempfile
import threading
import uuid
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import DatabaseError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from unittest import skipUnless
from django.utils import timezone

from accounts.models import User
from documents.jobs import claim_next_job, publish_claim
from documents.models import (
    Document, DocumentVersion, ExtractedTextArtifact, OriginalArtifact, ProcessingJob,
    ArtifactPublicationGuard, QuarantinedArtifact,
)
from documents.reconciliation import RecoveryIssue, execute_recovery_issue
from documents.storage import ArtifactStorageError, PrivateArtifactStore
from documents.tests.test_jobs import create_pending_job
from documents.uploads import create_document_upload
from security_audit.models import SecurityAuditEvent


class DocumentReconciliationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user("recovery-admin@example.test", "long-recovery-password-4829", is_app_admin=True)
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(self.temporary.name) / "private")
        self.override.enable(); self.addCleanup(self.override.disable)
        self.store = PrivateArtifactStore(); self.addCleanup(self.store.close)

    def orphan(self):
        return self.store.write_upload(SimpleUploadedFile("orphan.txt", b"orphan-private-content", content_type="text/plain"))

    def test_command_is_dry_run_by_default_and_quarantines_only_on_execute(self):
        orphan = self.orphan(); output = StringIO()
        with patch("documents.reconciliation.PrivateArtifactStore", return_value=self.store):
            call_command("reconcile_documents", actor_id=self.actor.pk, stdout=output)
        self.assertIn("DRY RUN", output.getvalue())
        self.assertTrue(self.store.resolve(orphan.storage_key).exists())
        with patch("documents.reconciliation.PrivateArtifactStore", return_value=self.store):
            call_command("reconcile_documents", actor_id=self.actor.pk, execute=True, stdout=StringIO())
        self.assertFalse((self.store.root / orphan.storage_key).exists())
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.DOCUMENT_RECONCILED).count(), 1)

    def test_orphan_audit_failure_restores_original_artifact(self):
        orphan = self.orphan(); issue = RecoveryIssue("orphan_artifact", orphan.storage_key)
        with patch("documents.reconciliation.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError): execute_recovery_issue(actor=self.actor, issue=issue, store=self.store)
        self.assertTrue((self.store.root / orphan.storage_key).exists())
        self.assertFalse(QuarantinedArtifact.objects.filter(storage_key=orphan.storage_key).exists())

    def _version(self):
        owner = User.objects.create_user(f"{uuid.uuid4().hex}@example.test", None, it_role=User.ITRole.IT_MEMBER)
        document = Document.objects.create(owner=owner, title="Referenced")
        return DocumentVersion.objects.create(
            document=document, sequence=1, processing_state=DocumentVersion.ProcessingState.READY,
            created_by_user_id=owner.pk,
        )

    def test_referenced_original_artifact_is_not_quarantined(self):
        stored = self.orphan()
        OriginalArtifact.objects.create(
            document_version=self._version(), storage_key=stored.storage_key,
            original_filename="referenced.txt", sha256_digest=stored.sha256_digest,
            byte_length=stored.byte_length, detected_media_type="text/plain",
        )
        result = execute_recovery_issue(
            actor=self.actor, issue=RecoveryIssue("orphan_artifact", stored.storage_key), store=self.store,
        )
        self.assertEqual(result, "referenced")
        self.assertTrue(self.store.resolve(stored.storage_key).exists())
        self.assertFalse(QuarantinedArtifact.objects.filter(storage_key=stored.storage_key).exists())

    def test_referenced_extracted_artifact_is_not_quarantined(self):
        version = self._version()
        key, path = self.store.allocate_extracted_path(version.pk)
        path.write_text("referenced extracted text", encoding="utf-8")
        stored, characters = self.store.inspect_text(key)
        ExtractedTextArtifact.objects.create(
            document_version=version, storage_key=key, sha256_digest=stored.sha256_digest,
            byte_length=stored.byte_length, character_count=characters,
            page_count=None, extractor_version="test",
        )
        result = execute_recovery_issue(
            actor=self.actor, issue=RecoveryIssue("orphan_artifact", key), store=self.store,
        )
        self.assertEqual(result, "referenced")
        self.assertTrue(self.store.resolve(key).exists())

    def test_repeated_orphan_reconciliation_is_idempotent(self):
        stored = self.orphan()
        issue = RecoveryIssue("orphan_artifact", stored.storage_key)
        self.assertEqual(execute_recovery_issue(actor=self.actor, issue=issue, store=self.store), "quarantined")
        self.assertEqual(execute_recovery_issue(actor=self.actor, issue=issue, store=self.store), "already_reconciled")
        self.assertEqual(QuarantinedArtifact.objects.filter(storage_key=stored.storage_key).count(), 1)
        self.assertEqual(SecurityAuditEvent.objects.filter(action=SecurityAuditEvent.Action.DOCUMENT_RECONCILED).count(), 1)

    def test_guard_lock_failure_fails_closed_without_storage_or_audit_mutation(self):
        stored = self.orphan()
        OriginalArtifact.objects.create(
            document_version=self._version(), storage_key=stored.storage_key,
            original_filename="referenced.txt", sha256_digest=stored.sha256_digest,
            byte_length=stored.byte_length, detected_media_type="text/plain",
        )
        issue = RecoveryIssue("orphan_artifact", stored.storage_key)
        with patch(
            "documents.reconciliation.lock_artifact_publication",
            side_effect=DatabaseError("guard lock unavailable"),
        ):
            with self.assertRaises(DatabaseError):
                execute_recovery_issue(actor=self.actor, issue=issue, store=self.store)
        self.assertTrue(self.store.resolve(stored.storage_key).exists())
        self.assertTrue(OriginalArtifact.objects.filter(storage_key=stored.storage_key).exists())
        self.assertFalse(QuarantinedArtifact.objects.filter(storage_key=stored.storage_key).exists())
        self.assertFalse(SecurityAuditEvent.objects.filter(
            action=SecurityAuditEvent.Action.DOCUMENT_RECONCILED,
        ).exists())

    def test_audit_and_restore_failure_remains_failed_closed_for_late_publication(self):
        _, version, _ = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        key, path = self.store.allocate_extracted_path(version.pk)
        path.write_text("result awaiting publication", encoding="utf-8")
        stored, characters = self.store.inspect_text(key)
        issue = RecoveryIssue("orphan_artifact", key)
        with (
            patch("documents.reconciliation.record_critical_event", side_effect=RuntimeError("audit unavailable")),
            patch.object(self.store, "restore_quarantined", side_effect=OSError("restore unavailable")),
            self.assertRaises(OSError),
        ):
            execute_recovery_issue(actor=self.actor, issue=issue, store=self.store)
        self.assertFalse((self.store.root / key).exists())
        self.assertFalse(QuarantinedArtifact.objects.filter(storage_key=key).exists())
        self.assertFalse(SecurityAuditEvent.objects.filter(
            action=SecurityAuditEvent.Action.DOCUMENT_RECONCILED,
        ).exists())
        with self.assertRaises(ArtifactStorageError):
            publish_claim(
                claim, stored=stored, character_count=characters, page_count=None,
                extractor_version="test", store=self.store,
            )
        self.assertFalse(ExtractedTextArtifact.objects.filter(storage_key=key).exists())

    def test_expired_lease_is_requeued_idempotently(self):
        _, version, job = create_pending_job(); claim_next_job(worker_id=uuid.uuid4())
        expired = timezone.now() - timedelta(seconds=1)
        ProcessingJob.objects.filter(pk=job.pk).update(lease_expires_at=expired)
        issue = RecoveryIssue("stale_job", str(job.pk))
        self.assertEqual(execute_recovery_issue(actor=self.actor, issue=issue, store=self.store, now=timezone.now()), "reconciled")
        job.refresh_from_db(); version.refresh_from_db()
        self.assertEqual(job.state, ProcessingJob.State.RETRY_WAIT)
        self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.QUEUED)
        self.assertEqual(execute_recovery_issue(actor=self.actor, issue=issue, store=self.store), "already_reconciled")

    def test_invalid_actor_is_rejected_without_mutation(self):
        invalid = User.objects.create_user("member-recovery@example.test", "long-recovery-password-4829", it_role=User.ITRole.IT_MEMBER)
        orphan = self.orphan()
        with self.assertRaisesMessage(Exception, "active, activated App Admin"):
            call_command("reconcile_documents", actor_id=invalid.pk, execute=True)
        self.assertTrue((self.store.root / orphan.storage_key).exists())

    def test_missing_artifact_marks_version_failed_and_audit_failure_rolls_back(self):
        owner = User.objects.create_user("missing-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        document = Document.objects.create(owner=owner, title="Missing")
        version = DocumentVersion.objects.create(document=document, sequence=1,
            processing_state=DocumentVersion.ProcessingState.QUEUED, created_by_user_id=owner.pk)
        document.candidate_version = version; document.save(update_fields=("candidate_version", "updated_at"))
        OriginalArtifact.objects.create(document_version=version,
            storage_key="originals/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.bin", sha256_digest="a" * 64,
            byte_length=10, detected_media_type="text/plain", original_filename="missing.txt")
        issue = RecoveryIssue("invalid_artifact", str(version.pk))
        with patch("documents.reconciliation.record_critical_event", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError): execute_recovery_issue(actor=self.actor, issue=issue, store=self.store)
        version.refresh_from_db(); self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.QUEUED)
        self.assertEqual(execute_recovery_issue(actor=self.actor, issue=issue, store=self.store), "reconciled")
        version.refresh_from_db(); self.assertEqual(version.processing_state, DocumentVersion.ProcessingState.FAILED)


@skipUnless(connection.vendor == "mysql", "Native MySQL quarantine concurrency evidence")
class ArtifactQuarantineConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        ArtifactPublicationGuard.objects.get_or_create(pk=1)
        self.actor = User.objects.create_user(
            "concurrent-recovery@example.test", "long-recovery-password-4829", is_app_admin=True,
        )
        self.owner = User.objects.create_user(
            "concurrent-owner@example.test", None, it_role=User.ITRole.IT_MEMBER,
        )
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(self.temporary.name) / "private")
        self.override.enable(); self.addCleanup(self.override.disable)
        self.store = PrivateArtifactStore(); self.addCleanup(self.store.close)

    def _ready_claim_and_file(self):
        document, version, _ = create_pending_job()
        claim = claim_next_job(worker_id=uuid.uuid4())
        key, path = self.store.allocate_extracted_path(version.pk)
        path.write_text("controlled concurrent result", encoding="utf-8")
        stored, characters = self.store.inspect_text(key)
        return document, version, claim, stored, characters

    def _run_threads(self, threads):
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))

    def test_publication_winning_race_prevents_quarantine(self):
        from documents.jobs import publish_claim

        _, version, claim, stored, characters = self._ready_claim_and_file()
        publication_holds_guard = threading.Event(); release_publication = threading.Event(); outcomes = []

        def hold_after_claim(*args, **kwargs):
            from documents.jobs import _locked_claim
            # The saved function is installed below before this patch takes effect.
            result = real_locked_claim(*args, **kwargs)
            publication_holds_guard.set(); release_publication.wait(timeout=10)
            return result

        def publisher():
            close_old_connections()
            try:
                publish_claim(claim, stored=stored, character_count=characters, page_count=None, extractor_version="test", store=self.store)
                outcomes.append("published")
            finally: close_old_connections()

        def quarantiner():
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                outcomes.append(execute_recovery_issue(
                    actor=actor, issue=RecoveryIssue("orphan_artifact", stored.storage_key),
                    store=PrivateArtifactStore(),
                ))
            finally: close_old_connections()

        from documents.jobs import _locked_claim as real_locked_claim
        with patch("documents.jobs._locked_claim", side_effect=hold_after_claim):
            first = threading.Thread(target=publisher); first.start()
            self.assertTrue(publication_holds_guard.wait(timeout=10))
            second = threading.Thread(target=quarantiner); second.start()
            release_publication.set()
            first.join(timeout=20); second.join(timeout=20)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertCountEqual(outcomes, ["published", "referenced"])
        self.assertTrue(ExtractedTextArtifact.objects.filter(document_version=version).exists())
        self.assertTrue(self.store.resolve(stored.storage_key).exists())

    def test_quarantine_winning_race_rejects_publication(self):
        from documents.jobs import LeaseLost, publish_claim

        _, version, claim, stored, characters = self._ready_claim_and_file()
        quarantine_holds_guard = threading.Event(); release_quarantine = threading.Event(); outcomes = []

        def hold_during_audit(*args, **kwargs):
            quarantine_holds_guard.set(); release_quarantine.wait(timeout=10)
            return real_audit(*args, **kwargs)

        def quarantiner():
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                outcomes.append(execute_recovery_issue(
                    actor=actor, issue=RecoveryIssue("orphan_artifact", stored.storage_key),
                    store=PrivateArtifactStore(),
                ))
            finally: close_old_connections()

        def publisher():
            close_old_connections()
            try:
                publish_claim(claim, stored=stored, character_count=characters, page_count=None, extractor_version="test", store=self.store)
                outcomes.append("published")
            except LeaseLost:
                outcomes.append("rejected")
            finally: close_old_connections()

        from documents.reconciliation import _audit as real_audit
        with patch("documents.reconciliation._audit", side_effect=hold_during_audit):
            first = threading.Thread(target=quarantiner); first.start()
            self.assertTrue(quarantine_holds_guard.wait(timeout=10))
            second = threading.Thread(target=publisher); second.start()
            release_quarantine.set()
            first.join(timeout=20); second.join(timeout=20)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertCountEqual(outcomes, ["quarantined", "rejected"])
        self.assertFalse(ExtractedTextArtifact.objects.filter(document_version=version).exists())
        self.assertTrue(QuarantinedArtifact.objects.filter(storage_key=stored.storage_key).exists())

    def test_concurrent_original_reference_creation_prevents_quarantine(self):
        from django.db import transaction
        from documents.artifact_coordination import lock_artifact_publication, reject_quarantined_key

        document = Document.objects.create(owner=self.owner, title="Concurrent original")
        version = DocumentVersion.objects.create(
            document=document, sequence=1, processing_state=DocumentVersion.ProcessingState.QUEUED,
            created_by_user_id=self.owner.pk,
        )
        stored = self.store.write_upload(SimpleUploadedFile("original.txt", b"concurrent original"))
        publication_holds_guard = threading.Event(); release_publication = threading.Event(); outcomes = []

        def publisher():
            close_old_connections()
            try:
                with transaction.atomic():
                    lock_artifact_publication(); reject_quarantined_key(stored.storage_key)
                    publication_holds_guard.set(); release_publication.wait(timeout=10)
                    OriginalArtifact.objects.create(
                        document_version_id=version.pk, storage_key=stored.storage_key,
                        original_filename="original.txt", sha256_digest=stored.sha256_digest,
                        byte_length=stored.byte_length, detected_media_type="text/plain",
                    )
                outcomes.append("published")
            finally: close_old_connections()

        def quarantiner():
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                outcomes.append(execute_recovery_issue(
                    actor=actor, issue=RecoveryIssue("orphan_artifact", stored.storage_key),
                    store=PrivateArtifactStore(),
                ))
            finally: close_old_connections()

        first = threading.Thread(target=publisher); first.start()
        self.assertTrue(publication_holds_guard.wait(timeout=10))
        second = threading.Thread(target=quarantiner); second.start()
        release_publication.set()
        first.join(timeout=20); second.join(timeout=20)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertCountEqual(outcomes, ["published", "referenced"])
        self.assertTrue(OriginalArtifact.objects.filter(storage_key=stored.storage_key).exists())
        self.assertTrue(self.store.resolve(stored.storage_key).exists())

    def test_real_upload_winning_race_prevents_orphan_quarantine(self):
        from documents.artifact_coordination import lock_artifact_publication as real_lock

        upload_holds_guard = threading.Event(); release_upload = threading.Event(); outcomes = []

        def hold_upload_guard():
            guard = real_lock()
            upload_holds_guard.set(); release_upload.wait(timeout=10)
            return guard

        def uploader():
            close_old_connections()
            try:
                owner = User.objects.get(pk=self.owner.pk)
                result = create_document_upload(
                    actor=owner, title="Concurrent upload", description="",
                    uploaded_file=SimpleUploadedFile("concurrent.txt", b"real upload race", content_type="text/plain"),
                    store=self.store,
                )
                outcomes.append(("uploaded", result.version.pk))
            finally: close_old_connections()

        def quarantiner(storage_key):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                outcomes.append(("quarantine", execute_recovery_issue(
                    actor=actor, issue=RecoveryIssue("orphan_artifact", storage_key),
                    store=PrivateArtifactStore(),
                )))
            finally: close_old_connections()

        with patch("documents.uploads.lock_artifact_publication", side_effect=hold_upload_guard):
            first = threading.Thread(target=uploader); first.start()
            self.assertTrue(upload_holds_guard.wait(timeout=10))
            keys = self.store.inventory_keys()
            self.assertEqual(len(keys), 1)
            second = threading.Thread(target=quarantiner, args=(keys[0],)); second.start()
            release_upload.set()
            first.join(timeout=20); second.join(timeout=20)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertIn(("quarantine", "referenced"), outcomes)
        uploaded = [outcome for outcome in outcomes if outcome[0] == "uploaded"]
        self.assertEqual(len(uploaded), 1)
        artifact = OriginalArtifact.objects.get(document_version_id=uploaded[0][1])
        self.assertEqual(artifact.storage_key, keys[0])
        self.assertTrue(self.store.resolve(keys[0]).exists())
        self.assertFalse(QuarantinedArtifact.objects.filter(storage_key=keys[0]).exists())
