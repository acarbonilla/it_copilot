import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from .models import Document, DocumentVersion, ExtractedTextArtifact, ProcessingJob


RETRY_DELAYS_SECONDS = (5, 30)
TERMINAL_STATES = {ProcessingJob.State.SUCCEEDED, ProcessingJob.State.FAILED, ProcessingJob.State.CANCELLED}


class LeaseLost(Exception):
    pass


class PublicationRejected(LeaseLost):
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


def claim_next_job(*, worker_id, now=None):
    worker_id = uuid.UUID(str(worker_id))
    now = now or timezone.now()
    while True:
        with transaction.atomic():
            candidate = (
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
                .first()
            )
            if candidate is None:
                return None
            document = (
                Document.objects.select_for_update(skip_locked=True)
                .filter(pk=candidate["document_version__document_id"])
                .first()
            )
            if document is None:
                return None
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
                continue
            if job.attempt_count >= 3:
                _terminalize(job, ProcessingJob.State.FAILED, now, "retry_exhausted")
                version.processing_state = DocumentVersion.ProcessingState.FAILED
                version.save(update_fields=("processing_state", "updated_at"))
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
        if job.cancellation_requested or document.visibility != Document.Visibility.ACTIVE:
            _terminalize(job, ProcessingJob.State.CANCELLED, now, "cancelled")
            version.processing_state = DocumentVersion.ProcessingState.CANCELLED
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
        version.save(update_fields=("processing_state", "updated_at"))
        return job.state


def publish_claim(claim, *, stored, character_count, page_count, extractor_version, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        job, version, document = _locked_claim(claim, now)
        if (
            job.cancellation_requested
            or document.visibility != Document.Visibility.ACTIVE
            or document.candidate_version_id != version.pk
            or version.processing_state != DocumentVersion.ProcessingState.PROCESSING
        ):
            raise PublicationRejected("Processing result is stale")
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
