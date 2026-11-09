from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from documents.models import Document, DocumentVersion
from documents.retrieval import validate_indexable_version

from .indexing import _invalidate_document, _schedule_current
from .models import RetrievalIndexGeneration, RetrievalIndexJob


@dataclass(frozen=True)
class IndexIssue:
    code: str
    document_id: object
    version_id: object | None


def inventory_index_issues(*, cursor=None, limit=100, now=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 256:
        raise ValueError("Reconciliation limit is invalid")
    now = now or timezone.now()
    queryset = Document.objects.order_by("id")
    if cursor is not None:
        queryset = queryset.filter(id__gt=cursor)
    documents = list(queryset[: limit + 1])
    complete = len(documents) <= limit
    documents = documents[:limit]
    issues = []
    for document in documents:
        published = RetrievalIndexGeneration.objects.filter(
            document=document, status=RetrievalIndexGeneration.Status.PUBLISHED,
        ).first()
        eligible = (
            document.visibility == Document.Visibility.ACTIVE
            and document.current_version_id is not None
            and DocumentVersion.objects.filter(
                pk=document.current_version_id,
                processing_state=DocumentVersion.ProcessingState.READY,
                extracted_text_artifact__isnull=False,
            ).exists()
        )
        if eligible and published is None:
            issues.append(IndexIssue("missing_generation", document.pk, document.current_version_id))
        elif not eligible and published is not None:
            issues.append(IndexIssue("extra_generation", document.pk, published.document_version_id))
        elif published is not None and published.document_version_id != document.current_version_id:
            issues.append(IndexIssue("stale_generation", document.pk, published.document_version_id))
        elif published is not None:
            try:
                validate_indexable_version(
                    version_id=published.document_version_id, expected_digest=published.source_digest,
                )
            except Exception:
                issues.append(IndexIssue("invalid_source", document.pk, published.document_version_id))
    interrupted = RetrievalIndexJob.objects.filter(
        state=RetrievalIndexJob.State.RUNNING, lease_expires_at__lte=now,
    ).order_by("id")[:limit]
    issues.extend(IndexIssue("expired_lease", job.document_version.document_id, job.document_version_id) for job in interrupted)
    return tuple(issues), (None if complete or not documents else documents[-1].pk), complete


def repair_index_issues(*, issues, limit=100, now=None):
    issues = tuple(issues)
    if len(issues) > limit or limit < 1 or limit > 256:
        raise ValueError("Repair batch is invalid")
    now = now or timezone.now()
    repaired = 0
    for issue in issues:
        with transaction.atomic():
            document = Document.objects.select_for_update().filter(pk=issue.document_id).first()
            if document is None:
                continue
            if issue.code in {"extra_generation", "stale_generation", "invalid_source"}:
                _invalidate_document(document)
            if issue.code in {"missing_generation", "stale_generation"}:
                _schedule_current(document, now)
            if issue.code == "expired_lease":
                RetrievalIndexJob.objects.filter(
                    document_version_id=issue.version_id,
                    state=RetrievalIndexJob.State.RUNNING,
                    lease_expires_at__lte=now,
                ).update(state=RetrievalIndexJob.State.RETRY_WAIT, lease_owner=None,
                         lease_expires_at=None, heartbeat_at=None, available_at=now)
            repaired += 1
    return repaired
