import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event

from .models import Document, DocumentVersion, ExtractedTextArtifact, OriginalArtifact, ProcessingJob
from .artifact_coordination import (
    ArtifactPublicationRejected,
    lock_artifact_publication,
    reject_quarantined_key,
)
from .storage import ArtifactStorageError


RETRY_DELAYS_SECONDS = (5, 30)
TERMINAL_STATES = {ProcessingJob.State.SUCCEEDED, ProcessingJob.State.FAILED, ProcessingJob.State.CANCELLED}


class LeaseLost(Exception):
    pass


class PublicationRejected(LeaseLost, ArtifactPublicationRejected):
    pass


@dataclass(frozen=True)
class JobClaim:
    job_id: uuid.UUID
    version_id: uuid.UUID
    worker_id: uuid.UUID
    attempt: int


def _terminalize(job, state, now, error_code=""):
    job.state = state
    job.nonterminal_slot = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.completed_at = now
    job.last_error_code = error_code
    job.save(
        update_fields=(
            "state", "nonterminal_slot", "lease_owner", "lease_expires_at", "heartbeat_at",
            "cancellation_requested", "completed_at", "last_error_code", "updated_at",
        )
    )


def _audit_processing_failure(document):
    record_critical_event(
        action=SecurityAuditEvent.Action.DOCUMENT_PROCESSING_FAILED,
        actor_user_id=None,
        target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
        target_id=str(document.pk),
        outcome=SecurityAuditEvent.Outcome.FAILURE,
    )


def _validate_ready_artifacts(*, version, stored, character_count, page_count, extractor_version, store):
    try:
        original = OriginalArtifact.objects.select_for_update().get(document_version=version)
    except OriginalArtifact.DoesNotExist as exc:
        raise PublicationRejected("Original artifact reference is unavailable") from exc
    try:
        reject_quarantined_key(original.storage_key)
        reject_quarantined_key(stored.storage_key)
    except ArtifactPublicationRejected as exc:
        raise PublicationRejected(str(exc)) from exc
    if (
        isinstance(character_count, bool)
        or not isinstance(character_count, int)
        or character_count < 1
        or character_count > settings.DOCUMENT_EXTRACTION_MAX_CHARACTERS
        or stored.byte_length < 1
        or (page_count is not None and (
            isinstance(page_count, bool)
            or not isinstance(page_count, int)
            or page_count < 1
            or page_count > settings.DOCUMENT_MAX_PDF_PAGES
        ))
        or not isinstance(extractor_version, str)
        or not extractor_version.strip()
        or len(extractor_version) > 64
    ):
        raise PublicationRejected("Extracted artifact metadata is invalid")
    try:
        store.validate_integrity(
            original.storage_key,
            expected_byte_length=original.byte_length,
            expected_sha256_digest=original.sha256_digest,
        )
        store.validate_integrity(
            stored.storage_key,
            expected_byte_length=stored.byte_length,
            expected_sha256_digest=stored.sha256_digest,
        )
    except ArtifactStorageError as exc:
        raise PublicationRejected("Artifact validation failed") from exc


def claim_next_job(*, worker_id, now=None):
    worker_id = uuid.UUID(str(worker_id))
    now = now or timezone.now()
    while True:
        with transaction.atomic():
            skipped_document_ids = set()
            while True:
                candidates = (
                    ProcessingJob.objects
                    .filter(
                        Q(state__in=(ProcessingJob.State.PENDING, ProcessingJob.State.RETRY_WAIT), available_at__lte=now)
                        | Q(state=ProcessingJob.State.RUNNING, lease_expires_at__lte=now),
                        cancellation_requested=False,
                        document_version__document__visibility=Document.Visibility.ACTIVE,
                    )
                    .filter(document_version__document__candidate_version_id=F("document_version_id"))
                    .order_by("available_at", "created_at", "id")
                    .values("id", "document_version_id", "document_version__document_id")
                )
                if skipped_document_ids:
                    candidates = candidates.exclude(document_version__document_id__in=skipped_document_ids)
                candidate = candidates.first()
                if candidate is None:
                    return None
                document = (
                    Document.objects.select_for_update(skip_locked=True)
                    .filter(pk=candidate["document_version__document_id"])
                    .first()
                )
                if document is not None:
                    break
                skipped_document_ids.add(candidate["document_version__document_id"])
            version = DocumentVersion.objects.select_for_update().get(pk=candidate["document_version_id"])
            job = ProcessingJob.objects.select_for_update().get(pk=candidate["id"])
            is_due = (
                job.state in {ProcessingJob.State.PENDING, ProcessingJob.State.RETRY_WAIT}
                and job.available_at <= now
            ) or (
                job.state == ProcessingJob.State.RUNNING
                and job.lease_expires_at is not None
                and job.lease_expires_at <= now
            )
            if not is_due or job.cancellation_requested:
                continue
            if document.visibility != Document.Visibility.ACTIVE or document.candidate_version_id != version.pk:
                _terminalize(job, ProcessingJob.State.CANCELLED, now, "document_unavailable")
                version.processing_state = DocumentVersion.ProcessingState.CANCELLED
                version.save(update_fields=("processing_state", "updated_at"))
                _audit_processing_failure(document)
                continue
            if job.attempt_count >= 3:
                _terminalize(job, ProcessingJob.State.FAILED, now, "retry_exhausted")
                version.processing_state = DocumentVersion.ProcessingState.FAILED
                version.save(update_fields=("processing_state", "updated_at"))
                _audit_processing_failure(document)
                continue
            job.attempt_count += 1
            job.state = ProcessingJob.State.RUNNING
            job.lease_owner = worker_id
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=settings.DOCUMENT_JOB_LEASE_SECONDS)
            job.last_error_code = ""
            job.save(
                update_fields=(
                    "attempt_count", "state", "lease_owner", "heartbeat_at", "lease_expires_at",
                    "last_error_code", "updated_at",
                )
            )
            version.processing_state = DocumentVersion.ProcessingState.PROCESSING
            version.save(update_fields=("processing_state", "updated_at"))
            return JobClaim(job.pk, version.pk, worker_id, job.attempt_count)


def _locked_claim(claim, now):
    snapshot = ProcessingJob.objects.only("document_version_id").get(pk=claim.job_id)
    version_snapshot = DocumentVersion.objects.only("document_id").get(pk=snapshot.document_version_id)
    document = Document.objects.select_for_update().get(pk=version_snapshot.document_id)
    version = DocumentVersion.objects.select_for_update().get(pk=snapshot.document_version_id)
    job = ProcessingJob.objects.select_for_update().get(pk=claim.job_id)
    if (
        job.state != ProcessingJob.State.RUNNING
        or job.lease_owner != claim.worker_id
        or job.attempt_count != claim.attempt
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise LeaseLost("Processing lease is no longer valid")
    return job, version, document


def heartbeat(claim, *, now=None):
    now = now or timezone.now()
    try:
        with transaction.atomic():
            job, _, _ = _locked_claim(claim, now)
            if job.cancellation_requested:
                return False
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=settings.DOCUMENT_JOB_LEASE_SECONDS)
            job.save(update_fields=("heartbeat_at", "lease_expires_at", "updated_at"))
            return True
    except (LeaseLost, ProcessingJob.DoesNotExist):
        return False


def fail_claim(claim, *, error_code, retryable, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        job, version, document = _locked_claim(claim, now)
        terminal = False
        if job.cancellation_requested or document.visibility != Document.Visibility.ACTIVE:
            _terminalize(job, ProcessingJob.State.CANCELLED, now, "cancelled")
            version.processing_state = DocumentVersion.ProcessingState.CANCELLED
            terminal = True
        elif retryable and job.attempt_count < 3:
            delay = RETRY_DELAYS_SECONDS[job.attempt_count - 1]
            job.state = ProcessingJob.State.RETRY_WAIT
            job.available_at = now + timedelta(seconds=delay)
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.last_error_code = error_code[:32]
            job.save(
                update_fields=(
                    "state", "available_at", "lease_owner", "lease_expires_at", "heartbeat_at",
                    "last_error_code", "updated_at",
                )
            )
            version.processing_state = DocumentVersion.ProcessingState.QUEUED
        else:
            _terminalize(job, ProcessingJob.State.FAILED, now, error_code[:32])
            version.processing_state = DocumentVersion.ProcessingState.FAILED
            terminal = True
        version.save(update_fields=("processing_state", "updated_at"))
        if terminal:
            _audit_processing_failure(document)
        return job.state


def publish_claim(claim, *, stored, character_count, page_count, extractor_version, store, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        lock_artifact_publication()
        job, version, document = _locked_claim(claim, now)
        if (
            job.cancellation_requested
            or document.visibility != Document.Visibility.ACTIVE
            or document.candidate_version_id != version.pk
            or version.processing_state != DocumentVersion.ProcessingState.PROCESSING
        ):
            raise PublicationRejected("Processing result is stale")
        _validate_ready_artifacts(
            version=version,
            stored=stored,
            character_count=character_count,
            page_count=page_count,
            extractor_version=extractor_version,
            store=store,
        )
        artifact = ExtractedTextArtifact.objects.create(
            document_version=version,
            storage_key=stored.storage_key,
            sha256_digest=stored.sha256_digest,
            byte_length=stored.byte_length,
            character_count=character_count,
            page_count=page_count,
            extractor_version=extractor_version,
        )
        version.processing_state = DocumentVersion.ProcessingState.READY
        version.save(update_fields=("processing_state", "updated_at"))
        document.current_version = version
        document.candidate_version = None
        document.save(update_fields=("current_version", "candidate_version", "updated_at"))
        _terminalize(job, ProcessingJob.State.SUCCEEDED, now)
        record_critical_event(
            action=SecurityAuditEvent.Action.DOCUMENT_PROCESSING_SUCCEEDED,
            actor_user_id=None,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=str(document.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        from .retrieval import queue_retrieval_change
        queue_retrieval_change(document=document, version=version, reason="ready_published")
        return artifact


def cancel_document_jobs(document, *, now=None):
    now = now or timezone.now()
    jobs = list(
        ProcessingJob.objects.select_for_update()
        .filter(document_version__document=document, nonterminal_slot=True)
        .select_related("document_version")
    )
    for job in jobs:
        job.cancellation_requested = True
        _terminalize(job, ProcessingJob.State.CANCELLED, now, "cancelled")
        version = job.document_version
        version.processing_state = DocumentVersion.ProcessingState.CANCELLED
        version.save(update_fields=("processing_state", "updated_at"))
        _audit_processing_failure(document)
