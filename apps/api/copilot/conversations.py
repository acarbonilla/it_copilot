from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import User
from documents.policies import is_active_identity

from .citations import released_citations
from .models import CopilotConversation, CopilotMessage
from .provider import DisabledByDefaultProviderAdapter, ProviderUnavailable
from .retrieval import InvalidQuestion, retrieve_authorized_evidence


class ConversationUnavailable(Exception):
    pass


class ConversationLimitReached(Exception):
    pass


@dataclass(frozen=True)
class CompletedTurn:
    conversation: CopilotConversation
    user_message: CopilotMessage
    assistant_message: CopilotMessage


def _eligible_actor(actor, *, lock=False):
    actor_id = getattr(actor, "pk", None)
    queryset = User.objects.select_for_update() if lock else User.objects
    fresh = queryset.filter(pk=actor_id).first() if actor_id else None
    if not is_active_identity(fresh) or fresh.it_role not in {
        User.ITRole.IT_MEMBER, User.ITRole.IT_EDITOR, User.ITRole.IT_DOC_ADMIN,
    }:
        raise PermissionDenied
    return fresh


def _expiry(now):
    return now + timedelta(days=settings.COPILOT_CONVERSATION_RETENTION_DAYS)


def create_conversation(*, actor, title="New conversation", now=None):
    now = now or timezone.now()
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise ValueError("Conversation title is invalid")
    with transaction.atomic():
        fresh = _eligible_actor(actor, lock=True)
        return CopilotConversation.objects.create(
            owner=fresh, title=title.strip(), last_activity_at=now, retention_expires_at=_expiry(now),
        )


def owned_conversations(*, actor, now=None):
    fresh = _eligible_actor(actor)
    now = now or timezone.now()
    return CopilotConversation.objects.filter(owner=fresh, retention_expires_at__gt=now)


def owned_conversation(*, actor, conversation_id, lock=False, now=None):
    fresh = _eligible_actor(actor, lock=lock)
    now = now or timezone.now()
    queryset = CopilotConversation.objects.select_for_update() if lock else CopilotConversation.objects
    conversation = queryset.filter(
        pk=conversation_id, owner=fresh, retention_expires_at__gt=now,
    ).first()
    if conversation is None:
        raise ConversationUnavailable
    return conversation


def delete_conversation(*, actor, conversation_id, now=None):
    with transaction.atomic():
        conversation = owned_conversation(
            actor=actor, conversation_id=conversation_id, lock=True, now=now,
        )
        conversation.delete()


def submit_question(*, actor, conversation_id, question, provider=None, store=None, now=None):
    now = now or timezone.now()
    provider = provider or DisabledByDefaultProviderAdapter()
    with transaction.atomic():
        fresh = _eligible_actor(actor, lock=True)
        conversation = CopilotConversation.objects.select_for_update().filter(
            pk=conversation_id, owner=fresh, retention_expires_at__gt=now,
        ).first()
        if conversation is None:
            raise ConversationUnavailable
        if conversation.messages.count() + 2 > settings.COPILOT_CONVERSATION_MAX_MESSAGES:
            raise ConversationLimitReached
        retrieval = retrieve_authorized_evidence(actor=fresh, question=question, store=store)
        citations = released_citations(retrieval.evidence)
        grounding = CopilotMessage.GroundingStatus.INSUFFICIENT
        provider_status = CopilotMessage.ProviderStatus.DISABLED
        content = ""
        selected_citations = ()
        if not retrieval.insufficient_evidence:
            grounding = CopilotMessage.GroundingStatus.REFERENCES
            selected_citations = citations
            try:
                provider.generate(question=retrieval.question, evidence=retrieval.evidence)
            except ProviderUnavailable:
                pass
        user_message = CopilotMessage.objects.create(
            conversation=conversation, role=CopilotMessage.Role.USER, content=retrieval.question,
        )
        assistant_message = CopilotMessage.objects.create(
            conversation=conversation, role=CopilotMessage.Role.ASSISTANT, content=content,
            grounding_status=grounding, provider_status=provider_status,
            citations=list(selected_citations),
        )
        conversation.last_activity_at = now
        conversation.retention_expires_at = _expiry(now)
        if conversation.title == "New conversation":
            conversation.title = retrieval.question[:200]
        conversation.save(update_fields=("title", "last_activity_at", "retention_expires_at", "updated_at"))
        return CompletedTurn(conversation, user_message, assistant_message)


def purge_expired_conversations(*, limit=100, execute=False, now=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 256:
        raise ValueError("Cleanup limit is invalid")
    now = now or timezone.now()
    ids = tuple(CopilotConversation.objects.filter(retention_expires_at__lte=now).order_by("retention_expires_at", "id").values_list("id", flat=True)[:limit])
    if execute and ids:
        return _delete_expired_ids(candidate_ids=ids, now=now)
    return ids


def _delete_expired_ids(*, candidate_ids, now):
    """Lock and revalidate stale cleanup candidates immediately before deletion."""
    candidate_ids = tuple(candidate_ids)
    if not candidate_ids:
        return ()
    deleted = []
    with transaction.atomic():
        queryset = CopilotConversation.objects.filter(pk__in=candidate_ids).order_by(
            "retention_expires_at", "id",
        )
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        for conversation in queryset:
            if conversation.retention_expires_at <= now:
                conversation_id = conversation.pk
                conversation.delete()
                deleted.append(conversation_id)
    return tuple(deleted)
