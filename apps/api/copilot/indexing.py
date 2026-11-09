import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F, Q
from django.utils import timezone

from documents.artifact_coordination import lock_artifact_publication
from documents.models import Document, DocumentRetrievalChange, DocumentVersion
from documents.retrieval import (
    RetrievalBoundaryError,
    open_verified_extracted_text,
    validate_indexable_version,
)
from documents.storage import PrivateArtifactStore

from .chunking import CHUNKER_VERSION, TOKENIZER_VERSION, chunk_text
from .models import RetrievalChunk, RetrievalIndexGeneration, RetrievalIndexJob


INDEX_VERSION = "mysql-fulltext-v1"
RETRY_DELAYS_SECONDS = (5, 30)


class IndexLeaseLost(Exception):
    pass


@dataclass(frozen=True)
class IndexJobClaim:
    job_id: uuid.UUID
    version_id: uuid.UUID
    worker_id: uuid.UUID
    attempt: int
    digest: str


def _terminalize(job, state, now, error_code=""):
    job.state = state
    job.nonterminal_slot = None
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.completed_at = now
    job.last_error_code = error_code[:32]
    job.save(update_fields=(
        "state", "nonterminal_slot", "lease_owner", "lease_expires_at", "heartbeat_at",
        "completed_at", "last_error_code", "updated_at",
    ))


def _invalidate_document(document):
    RetrievalIndexGeneration.objects.filter(
        document=document, status=RetrievalIndexGeneration.Status.PUBLISHED,
    ).update(status=RetrievalIndexGeneration.Status.OBSOLETE, searchable_slot=None)


def _schedule_current(document, now):
    if document.visibility != Document.Visibility.ACTIVE or document.current_version_id is None:
        return None
    version = (
        DocumentVersion.objects.select_related("extracted_text_artifact")
        .filter(
            pk=document.current_version_id,
            processing_state=DocumentVersion.ProcessingState.READY,
            extracted_text_artifact__isnull=False,
        )
        .first()
    )
    if version is None:
        return None
    digest = version.extracted_text_artifact.sha256_digest
    published = RetrievalIndexGeneration.objects.filter(
        document=document,
        document_version=version,
        source_digest=digest,
        status=RetrievalIndexGeneration.Status.PUBLISHED,
    ).exists()
    if published:
        return None
    job = RetrievalIndexJob.objects.filter(document_version=version, nonterminal_slot=True).first()
    if job is not None:
        return job
    return RetrievalIndexJob.objects.create(
        document_version=version, source_digest=digest, available_at=now,
    )


def consume_retrieval_changes(*, limit=100, now=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 256:
        raise ValueError("Change batch limit is invalid")
    now = now or timezone.now()
    consumed = 0
    with transaction.atomic():
        queryset = DocumentRetrievalChange.objects.filter(consumed_at__isnull=True).order_by("id")
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        for change in list(queryset[:limit]):
            document = Document.objects.select_for_update().filter(pk=change.document_id).first()
            if document is not None:
                _invalidate_document(document)
                _schedule_current(document, now)
            change.consumed_at = now
            change.save(update_fields=("consumed_at",))
            consumed += 1
    return consumed


def claim_next_index_job(*, worker_id, now=None):
    worker_id = uuid.UUID(str(worker_id))
    now = now or timezone.now()
    with transaction.atomic():
        queryset = RetrievalIndexJob.objects.filter(
            Q(state__in=(RetrievalIndexJob.State.PENDING, RetrievalIndexJob.State.RETRY_WAIT), available_at__lte=now)
            | Q(state=RetrievalIndexJob.State.RUNNING, lease_expires_at__lte=now)
        ).order_by("available_at", "created_at", "id")
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        job = queryset.first()
        if job is None:
            return None
        version = DocumentVersion.objects.select_for_update().select_related(
            "document", "extracted_text_artifact",
        ).filter(pk=job.document_version_id).first()
        valid = (
            version is not None
            and version.document.visibility == Document.Visibility.ACTIVE
            and version.document.current_version_id == version.pk
            and version.processing_state == DocumentVersion.ProcessingState.READY
            and hasattr(version, "extracted_text_artifact")
            and version.extracted_text_artifact.sha256_digest == job.source_digest
        )
        if not valid:
            _terminalize(job, RetrievalIndexJob.State.CANCELLED, now, "source_unavailable")
            return None
        if job.attempt_count >= 3:
            _terminalize(job, RetrievalIndexJob.State.FAILED, now, "retry_exhausted")
            return None
        job.attempt_count += 1
        job.state = RetrievalIndexJob.State.RUNNING
        job.lease_owner = worker_id
        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=settings.COPILOT_INDEX_JOB_LEASE_SECONDS)
        job.last_error_code = ""
        job.save(update_fields=(
            "attempt_count", "state", "lease_owner", "heartbeat_at", "lease_expires_at",
            "last_error_code", "updated_at",
        ))
        return IndexJobClaim(job.pk, version.pk, worker_id, job.attempt_count, job.source_digest)


def _locked_claim(claim, now):
    job = RetrievalIndexJob.objects.select_for_update().get(pk=claim.job_id)
    if (
        job.state != RetrievalIndexJob.State.RUNNING
        or job.lease_owner != claim.worker_id
        or job.attempt_count != claim.attempt
        or job.document_version_id != claim.version_id
        or job.source_digest != claim.digest
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise IndexLeaseLost("Index lease is no longer valid")
    return job


def heartbeat_index_job(claim, *, now=None):
    now = now or timezone.now()
    try:
        with transaction.atomic():
            job = _locked_claim(claim, now)
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=settings.COPILOT_INDEX_JOB_LEASE_SECONDS)
            job.save(update_fields=("heartbeat_at", "lease_expires_at", "updated_at"))
            return True
    except (RetrievalIndexJob.DoesNotExist, IndexLeaseLost):
        return False


def fail_index_job(claim, *, error_code, retryable, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        job = _locked_claim(claim, now)
        if retryable and job.attempt_count < 3:
            job.state = RetrievalIndexJob.State.RETRY_WAIT
            job.available_at = now + timedelta(seconds=RETRY_DELAYS_SECONDS[job.attempt_count - 1])
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.last_error_code = error_code[:32]
            job.save(update_fields=(
                "state", "available_at", "lease_owner", "lease_expires_at", "heartbeat_at",
                "last_error_code", "updated_at",
            ))
        else:
            _terminalize(job, RetrievalIndexJob.State.FAILED, now, error_code)
        return job.state


def publish_index_generation(claim, chunks, *, store=None, now=None):
    chunks = tuple(chunks)
    if not chunks:
        raise RetrievalBoundaryError("Extracted text has no searchable tokens")
    now = now or timezone.now()
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        with transaction.atomic():
            lock_artifact_publication()
            job = _locked_claim(claim, now)
            version = DocumentVersion.objects.select_for_update().select_related("document").get(pk=claim.version_id)
            document = Document.objects.select_for_update().get(pk=version.document_id)
            validate_indexable_version(version_id=version.pk, expected_digest=claim.digest, store=store)
            if document.current_version_id != version.pk or document.visibility != Document.Visibility.ACTIVE:
                raise RetrievalBoundaryError("Document evidence is unavailable")
            RetrievalIndexGeneration.objects.filter(
                document=document, status=RetrievalIndexGeneration.Status.PUBLISHED,
            ).update(status=RetrievalIndexGeneration.Status.OBSOLETE, searchable_slot=None)
            generation = RetrievalIndexGeneration.objects.create(
                id=job.generation_id,
                document=document,
                document_version=version,
                source_digest=claim.digest,
                chunker_version=f"{CHUNKER_VERSION}:{TOKENIZER_VERSION}",
                index_version=INDEX_VERSION,
            )
            RetrievalChunk.objects.bulk_create([
                RetrievalChunk(
                    generation=generation,
                    document=document,
                    document_version=version,
                    ordinal=chunk.ordinal,
                    searchable_text=chunk.text,
                    content_digest=chunk.digest,
                    token_count=chunk.token_count,
                    character_count=chunk.character_count,
                )
                for chunk in chunks
            ], batch_size=256)
            generation.status = RetrievalIndexGeneration.Status.PUBLISHED
            generation.searchable_slot = True
            generation.published_at = now
            generation.save(update_fields=("status", "searchable_slot", "published_at"))
            _terminalize(job, RetrievalIndexJob.State.SUCCEEDED, now)
            return generation
    finally:
        if owns_store:
            store.close()


def process_one_index_job(*, worker_id=None, store=None):
    worker_id = uuid.UUID(str(worker_id)) if worker_id else uuid.uuid4()
    consume_retrieval_changes(limit=100)
    claim = claim_next_index_job(worker_id=worker_id)
    if claim is None:
        return None
    owns_store = store is None
    store = store or PrivateArtifactStore()
    try:
        try:
            verified = open_verified_extracted_text(
                version_id=claim.version_id, expected_digest=claim.digest, store=store,
            )
            chunks = chunk_text(
                verified.stream.read(),
                max_tokens=settings.COPILOT_CHUNK_MAX_TOKENS,
                overlap_tokens=settings.COPILOT_CHUNK_OVERLAP_TOKENS,
            )
            publish_index_generation(claim, chunks, store=store)
            return "succeeded"
        except RetrievalBoundaryError:
            try:
                fail_index_job(claim, error_code="source_unavailable", retryable=False)
            except IndexLeaseLost:
                return "stale"
            return "failed"
        except Exception:
            try:
                fail_index_job(claim, error_code="index_failure", retryable=True)
            except IndexLeaseLost:
                return "stale"
            return "retry"
    finally:
        if owns_store:
            store.close()
