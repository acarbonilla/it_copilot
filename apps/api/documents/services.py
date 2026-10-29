from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from security_audit.models import SecurityAuditEvent
from security_audit.services import record_critical_event, record_denied_event_best_effort

from .models import Document
from .policies import DocumentCapability, authorize_document


class DocumentConflictError(Exception):
    pass


@dataclass(frozen=True)
class LifecycleResult:
    document: Document
    previous_visibility: str


def _actor_id(actor):
    return getattr(actor, "pk", None)


def _audit_denial(actor, document_id):
    record_denied_event_best_effort(
        action=SecurityAuditEvent.Action.AUTHORIZATION_DENIED,
        actor_user_id=_actor_id(actor),
        target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
        target_id=str(document_id) if document_id else None,
    )


def _require(actor, capability, document=None):
    decision = authorize_document(actor, capability, document=document)
    if not decision.allowed:
        _audit_denial(actor, getattr(document, "pk", None))
        raise PermissionDenied("Document operation is not permitted")


def _clean_text(value, *, field, max_length, allow_blank=False):
    if not isinstance(value, str):
        raise ValidationError({field: "Must be a string"})
    value = value.strip()
    if not value and not allow_blank:
        raise ValidationError({field: "Must not be blank"})
    if len(value) > max_length:
        raise ValidationError({field: "Value is too long"})
    return value


def create_document(*, actor, title, description=""):
    _require(actor, DocumentCapability.CREATE)
    with transaction.atomic():
        document = Document.objects.create(
            owner=actor,
            title=_clean_text(title, field="title", max_length=200),
            description=_clean_text(description, field="description", max_length=2000, allow_blank=True),
        )
        record_critical_event(
            action=SecurityAuditEvent.Action.DOCUMENT_CREATED,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=str(document.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return document


def update_document_metadata(*, actor, document_id, expected_revision, title=None, description=None):
    visible_document = Document.objects.get(pk=document_id)
    _require(actor, DocumentCapability.EDIT_METADATA, visible_document)
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if not authorize_document(actor, DocumentCapability.EDIT_METADATA, document=document).allowed:
            raise PermissionDenied("Document operation is not permitted")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision <= 0:
            raise ValidationError({"expected_revision": "Must be a positive integer"})
        if document.metadata_revision != expected_revision:
            raise DocumentConflictError("Document was modified by another request")
        fields = []
        if title is not None:
            document.title = _clean_text(title, field="title", max_length=200)
            fields.append("title")
        if description is not None:
            document.description = _clean_text(description, field="description", max_length=2000, allow_blank=True)
            fields.append("description")
        if not fields:
            raise ValidationError("At least one metadata field is required")
        document.metadata_revision += 1
        document.save(update_fields=(*fields, "metadata_revision", "updated_at"))
        record_critical_event(
            action=SecurityAuditEvent.Action.DOCUMENT_METADATA_UPDATED,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=str(document.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return document


def _transition(*, actor, document_id, expected_revision, from_states, to_state, action):
    visible_document = Document.objects.get(pk=document_id)
    capability = {
        Document.Visibility.ARCHIVED: DocumentCapability.ARCHIVE,
        Document.Visibility.ACTIVE: DocumentCapability.RESTORE,
        Document.Visibility.DELETED: DocumentCapability.DELETE,
    }[to_state]
    _require(actor, capability, visible_document)
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document_id)
        if not authorize_document(actor, capability, document=document).allowed:
            raise PermissionDenied("Document operation is not permitted")
        if document.metadata_revision != expected_revision:
            raise DocumentConflictError("Document was modified by another request")
        if document.visibility not in from_states:
            raise DocumentConflictError("Document lifecycle transition is not allowed")
        previous = document.visibility
        document.visibility = to_state
        document.metadata_revision += 1
        document.deleted_at = timezone.now() if to_state == Document.Visibility.DELETED else None
        document.save(update_fields=("visibility", "metadata_revision", "deleted_at", "updated_at"))
        record_critical_event(
            action=action,
            actor_user_id=actor.pk,
            target_type=SecurityAuditEvent.TargetType.IT_DOCUMENT,
            target_id=str(document.pk),
            outcome=SecurityAuditEvent.Outcome.SUCCESS,
        )
        return LifecycleResult(document=document, previous_visibility=previous)


def archive_document(*, actor, document_id, expected_revision):
    return _transition(
        actor=actor,
        document_id=document_id,
        expected_revision=expected_revision,
        from_states={Document.Visibility.ACTIVE},
        to_state=Document.Visibility.ARCHIVED,
        action=SecurityAuditEvent.Action.DOCUMENT_ARCHIVED,
    )


def restore_document(*, actor, document_id, expected_revision):
    return _transition(
        actor=actor,
        document_id=document_id,
        expected_revision=expected_revision,
        from_states={Document.Visibility.ARCHIVED},
        to_state=Document.Visibility.ACTIVE,
        action=SecurityAuditEvent.Action.DOCUMENT_RESTORED,
    )


def delete_document(*, actor, document_id, expected_revision):
    return _transition(
        actor=actor,
        document_id=document_id,
        expected_revision=expected_revision,
        from_states={Document.Visibility.ACTIVE, Document.Visibility.ARCHIVED},
        to_state=Document.Visibility.DELETED,
        action=SecurityAuditEvent.Action.DOCUMENT_DELETED,
    )
