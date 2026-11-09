from collections.abc import Mapping
from math import ceil

from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response
from rest_framework.views import APIView

from .conversations import (
    ConversationLimitReached, ConversationUnavailable, create_conversation,
    delete_conversation, owned_conversation, owned_conversations, submit_question,
)
from .retrieval import InvalidQuestion


def _error(code, message, status):
    return Response({"error": {"code": code, "message": message}}, status=status)


def _conversation_payload(conversation):
    return {
        "id": str(conversation.pk), "title": conversation.title,
        "created_at": conversation.created_at, "updated_at": conversation.updated_at,
        "last_activity_at": conversation.last_activity_at,
        "retention_expires_at": conversation.retention_expires_at,
    }


def _message_payload(message):
    return {
        "id": str(message.pk), "role": message.role.lower(), "content": message.content,
        "grounding_status": message.grounding_status.lower(),
        "provider_status": message.provider_status.lower(), "citations": message.citations,
        "created_at": message.created_at,
    }


def _failure(exc):
    if isinstance(exc, PermissionDenied):
        return _error("authentication_required", "Authentication required", 401)
    if isinstance(exc, ConversationUnavailable):
        return _error("not_found", "Conversation not found", 404)
    if isinstance(exc, (InvalidQuestion, ValueError, TypeError)):
        return _error("invalid_request", "Request is invalid", 400)
    if isinstance(exc, ConversationLimitReached):
        return _error("conversation_limit", "Conversation message limit reached", 409)
    return _error("request_failed", "Request could not be completed", 503)


@method_decorator(csrf_protect, name="dispatch")
class ConversationCollectionView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 25))
            if page < 1 or not 1 <= page_size <= 100:
                raise ValueError
            queryset = owned_conversations(actor=request.user)
            count = queryset.count(); start = (page - 1) * page_size
            return Response({
                "conversations": [_conversation_payload(item) for item in queryset[start:start + page_size]],
                "pagination": {"page": page, "page_size": page_size, "count": count,
                               "total_pages": ceil(count / page_size) if count else 0},
            })
        except Exception as exc:
            return _failure(exc)

    def post(self, request):
        try:
            if not isinstance(request.data, Mapping) or set(request.data) - {"title"}:
                raise ValueError
            conversation = create_conversation(actor=request.user, title=request.data.get("title", "New conversation"))
            return Response({"conversation": _conversation_payload(conversation)}, status=201)
        except Exception as exc:
            return _failure(exc)


@method_decorator(csrf_protect, name="dispatch")
class ConversationDetailView(APIView):
    permission_classes = []

    def get(self, request, conversation_id):
        try:
            conversation = owned_conversation(actor=request.user, conversation_id=conversation_id)
            messages = conversation.messages.all()[:100]
            return Response({"conversation": _conversation_payload(conversation),
                             "messages": [_message_payload(item) for item in messages]})
        except Exception as exc:
            return _failure(exc)

    def delete(self, request, conversation_id):
        try:
            delete_conversation(actor=request.user, conversation_id=conversation_id)
            return Response(status=204)
        except Exception as exc:
            return _failure(exc)


@method_decorator(csrf_protect, name="dispatch")
class ConversationMessageView(APIView):
    permission_classes = []

    def post(self, request, conversation_id):
        try:
            if not isinstance(request.data, Mapping) or set(request.data) != {"question"}:
                raise ValueError
            result = submit_question(
                actor=request.user, conversation_id=conversation_id, question=request.data["question"],
            )
            return Response({
                "conversation": _conversation_payload(result.conversation),
                "user_message": _message_payload(result.user_message),
                "assistant_message": _message_payload(result.assistant_message),
            }, status=201)
        except Exception as exc:
            return _failure(exc)
