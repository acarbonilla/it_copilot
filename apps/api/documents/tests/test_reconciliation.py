import tempfile
import uuid
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from documents.jobs import claim_next_job
from documents.models import Document, DocumentVersion, OriginalArtifact, ProcessingJob
from documents.reconciliation import RecoveryIssue, execute_recovery_issue
from documents.storage import PrivateArtifactStore
from documents.tests.test_jobs import create_pending_job
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
