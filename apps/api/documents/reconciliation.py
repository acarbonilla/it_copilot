import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.lifecycle import _lock_guard
from accounts.models import User
from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event

from .jobs import _terminalize
from .models import Document, DocumentVersion, ExtractedTextArtifact, OriginalArtifact, ProcessingJob
from .storage import ArtifactStorageError, PrivateArtifactStore


@dataclass(frozen=True)
class RecoveryIssue:
    kind: str
    identifier: str


def validate_recovery_actor(actor):
    if (actor is None or not actor.is_active or not actor.is_app_admin
            or actor.lifecycle_state != User.LifecycleState.ACTIVE or not actor.has_usable_password()):
        raise ValueError("Recovery actor must be an active, activated App Admin")
    return actor


def _artifact_valid(store, artifact):
    try:
        path = store.resolve(artifact.storage_key)
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as source:
            while chunk := source.read(65536):
                digest.update(chunk); size += len(chunk)
        return size == artifact.byte_length and digest.hexdigest() == artifact.sha256_digest
    except (ArtifactStorageError, OSError):
        return False


def inventory_recovery_issues(*, store=None, now=None, limit=100):
    store = store or PrivateArtifactStore(); now = now or timezone.now(); issues = []
    try:
        for job_id in ProcessingJob.objects.filter(state=ProcessingJob.State.RUNNING,
                lease_expires_at__lte=now).order_by("lease_expires_at", "id").values_list("pk", flat=True):
            issues.append(RecoveryIssue("stale_job", str(job_id)))
        artifacts = list(OriginalArtifact.objects.select_related("document_version")[:limit])
        artifacts += list(ExtractedTextArtifact.objects.select_related("document_version")[:limit])
        for artifact in artifacts:
            if not _artifact_valid(store, artifact):
                issues.append(RecoveryIssue("invalid_artifact", str(artifact.document_version_id)))
        known = set(OriginalArtifact.objects.values_list("storage_key", flat=True))
        known.update(ExtractedTextArtifact.objects.values_list("storage_key", flat=True))
        for key in store.inventory_keys():
            if key not in known:
                issues.append(RecoveryIssue("orphan_artifact", key))
        cutoff = now - timedelta(days=30)
        for document_id in Document.objects.filter(visibility=Document.Visibility.DELETED,
                deleted_at__lte=cutoff).order_by("deleted_at", "id").values_list("pk", flat=True):
            issues.append(RecoveryIssue("purge_eligible", str(document_id)))
        return issues[:limit]
    finally:
        if store is not None: store.close()


def _audit(actor, target_type, target_id):
    record_critical_event(action=SecurityAuditEvent.Action.DOCUMENT_RECONCILED,
        actor_user_id=actor.pk, target_type=target_type, target_id=target_id,
        outcome=SecurityAuditEvent.Outcome.SUCCESS)


def execute_recovery_issue(*, actor, issue, store=None, now=None):
    validate_recovery_actor(actor); now = now or timezone.now(); store = store or PrivateArtifactStore()
    try:
        if issue.kind == "orphan_artifact":
            quarantined = store.quarantine(issue.identifier)
            try:
                with transaction.atomic():
                    _lock_guard(); fresh = User.objects.select_for_update().get(pk=actor.pk); validate_recovery_actor(fresh)
                    opaque_id = str(uuid.uuid5(uuid.NAMESPACE_URL, issue.identifier))
                    _audit(fresh, SecurityAuditEvent.TargetType.PRIVATE_RESOURCE, opaque_id)
            except Exception:
                store.restore_quarantined(quarantined, issue.identifier)
                raise
            return "quarantined"
        if issue.kind == "purge_eligible":
            return "reported_only"
        with transaction.atomic():
            _lock_guard(); fresh = User.objects.select_for_update().get(pk=actor.pk); validate_recovery_actor(fresh)
            if issue.kind == "stale_job":
                snapshot = ProcessingJob.objects.only("document_version_id").get(pk=issue.identifier)
                version_snapshot = DocumentVersion.objects.only("document_id").get(pk=snapshot.document_version_id)
                document = Document.objects.select_for_update().get(pk=version_snapshot.document_id)
                version = DocumentVersion.objects.select_for_update().get(pk=snapshot.document_version_id)
                job = ProcessingJob.objects.select_for_update().get(pk=issue.identifier)
                if job.state != ProcessingJob.State.RUNNING or job.lease_expires_at is None or job.lease_expires_at > now:
                    return "already_reconciled"
                if job.attempt_count >= 3:
                    _terminalize(job, ProcessingJob.State.FAILED, now, "stale_lease")
                    version.processing_state = DocumentVersion.ProcessingState.FAILED
                else:
                    job.state = ProcessingJob.State.RETRY_WAIT; job.available_at = now
                    job.lease_owner = job.lease_expires_at = job.heartbeat_at = None
                    job.last_error_code = "stale_lease"
                    job.save(update_fields=("state", "available_at", "lease_owner", "lease_expires_at", "heartbeat_at", "last_error_code", "updated_at"))
                    version.processing_state = DocumentVersion.ProcessingState.QUEUED
                version.save(update_fields=("processing_state", "updated_at")); _audit(fresh, SecurityAuditEvent.TargetType.IT_DOCUMENT, str(document.pk))
                return "reconciled"
            version = DocumentVersion.objects.select_related("document").get(pk=issue.identifier)
            document = Document.objects.select_for_update().get(pk=version.document_id)
            version = DocumentVersion.objects.select_for_update().get(pk=version.pk)
            artifacts = list(OriginalArtifact.objects.filter(document_version=version)) + list(ExtractedTextArtifact.objects.filter(document_version=version))
            if artifacts and all(_artifact_valid(store, artifact) for artifact in artifacts): return "already_reconciled"
            for job in ProcessingJob.objects.select_for_update().filter(document_version=version, nonterminal_slot=True):
                _terminalize(job, ProcessingJob.State.FAILED, now, "artifact_invalid")
            version.processing_state = DocumentVersion.ProcessingState.FAILED
            version.save(update_fields=("processing_state", "updated_at")); _audit(fresh, SecurityAuditEvent.TargetType.IT_DOCUMENT, str(document.pk))
            return "reconciled"
    finally:
        store.close()
