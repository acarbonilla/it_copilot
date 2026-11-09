from datetime import timedelta
from unittest.mock import Mock, patch

from django.db import DatabaseError
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from copilot.citations import InvalidCitation, released_citations, validate_citation_ids
from copilot.conversations import (
    ConversationLimitReached, ConversationUnavailable, create_conversation, delete_conversation,
    owned_conversation, owned_conversations, purge_expired_conversations, submit_question,
)
from copilot.models import CopilotConversation, CopilotMessage
from copilot.provider import DisabledByDefaultProviderAdapter, ProviderUnavailable
from copilot.retrieval import EvidenceChunk, RetrievalResult


def evidence_result():
    item = EvidenceChunk(
        chunk_id="b5878120-b2f0-4a38-901d-b452eaaca100",
        document_id="23fc6dc7-89c3-4a23-8915-f6a8f75fe300",
        version_id="a21b75d7-1c13-498d-aa08-417b08808000",
        document_title="Reset guide", version_sequence=2, ordinal=0,
        text="Use the authorized reset portal.", token_count=6, score=4.0,
    )
    return RetrievalResult("reset password", (item,), False)


class ConversationServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("conversation-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.other = User.objects.create_user("conversation-other@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.conversation = create_conversation(actor=self.owner)

    @patch("copilot.conversations.retrieve_authorized_evidence", return_value=evidence_result())
    def test_disabled_provider_returns_references_without_synthesis(self, retrieve):
        provider = Mock(); provider.generate.side_effect = ProviderUnavailable("disabled")
        turn = submit_question(actor=self.owner, conversation_id=self.conversation.pk,
                               question=" reset password ", provider=provider)
        self.assertEqual(turn.user_message.content, "reset password")
        self.assertEqual(turn.assistant_message.content, "")
        self.assertEqual(turn.assistant_message.grounding_status, "REFERENCES")
        self.assertEqual(turn.assistant_message.provider_status, "DISABLED")
        self.assertEqual(len(turn.assistant_message.citations), 1)
        self.assertNotIn("text", turn.assistant_message.citations[0])
        provider.generate.assert_called_once()

    @patch("copilot.conversations.retrieve_authorized_evidence")
    def test_insufficient_evidence_is_persisted_atomically(self, retrieve):
        retrieve.return_value = RetrievalResult("unknown issue", (), True)
        turn = submit_question(actor=self.owner, conversation_id=self.conversation.pk, question="unknown issue")
        self.assertEqual(turn.assistant_message.grounding_status, "INSUFFICIENT")
        self.assertEqual(turn.assistant_message.citations, [])
        self.assertEqual(self.conversation.messages.count(), 2)

    def test_cross_owner_and_deactivated_actor_are_denied(self):
        with self.assertRaises(ConversationUnavailable):
            submit_question(actor=self.other, conversation_id=self.conversation.pk, question="question")
        self.owner.lifecycle_state = User.LifecycleState.DEACTIVATED; self.owner.save()
        with self.assertRaises(PermissionDenied):
            submit_question(actor=self.owner, conversation_id=self.conversation.pk, question="question")

    @patch("copilot.conversations.retrieve_authorized_evidence", return_value=evidence_result())
    def test_turn_rolls_back_when_assistant_persistence_fails(self, retrieve):
        original = CopilotMessage.objects.create
        calls = 0
        def create(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise DatabaseError("controlled")
            return original(**kwargs)
        with patch.object(CopilotMessage.objects, "create", side_effect=create):
            with self.assertRaises(DatabaseError):
                submit_question(actor=self.owner, conversation_id=self.conversation.pk, question="reset password")
        self.assertFalse(self.conversation.messages.exists())

    @override_settings(COPILOT_CONVERSATION_MAX_MESSAGES=2)
    @patch("copilot.conversations.retrieve_authorized_evidence", return_value=evidence_result())
    def test_history_limit_is_enforced(self, retrieve):
        submit_question(actor=self.owner, conversation_id=self.conversation.pk, question="reset password")
        with self.assertRaises(ConversationLimitReached):
            submit_question(actor=self.owner, conversation_id=self.conversation.pk, question="again")

    def test_retention_is_dry_run_first_and_bounded(self):
        CopilotConversation.objects.filter(pk=self.conversation.pk).update(
            retention_expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(purge_expired_conversations(limit=1, execute=False), (self.conversation.pk,))
        self.assertTrue(CopilotConversation.objects.filter(pk=self.conversation.pk).exists())
        purge_expired_conversations(limit=1, execute=True)
        self.assertFalse(CopilotConversation.objects.filter(pk=self.conversation.pk).exists())

    def test_expired_conversation_is_unavailable_for_all_normal_operations(self):
        boundary = timezone.now()
        CopilotConversation.objects.filter(pk=self.conversation.pk).update(retention_expires_at=boundary)
        self.assertFalse(owned_conversations(actor=self.owner, now=boundary).exists())
        with self.assertRaises(ConversationUnavailable):
            owned_conversation(actor=self.owner, conversation_id=self.conversation.pk, now=boundary)
        with self.assertRaises(ConversationUnavailable):
            submit_question(actor=self.owner, conversation_id=self.conversation.pk,
                            question="cannot renew", now=boundary)
        with self.assertRaises(ConversationUnavailable):
            delete_conversation(actor=self.owner, conversation_id=self.conversation.pk, now=boundary)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.retention_expires_at, boundary)
        self.assertEqual(purge_expired_conversations(limit=1, execute=True, now=boundary), (self.conversation.pk,))

    def test_citations_are_stable_bounded_metadata_and_tamper_rejected(self):
        available = released_citations(evidence_result().evidence)
        self.assertEqual(available, released_citations(evidence_result().evidence))
        self.assertEqual(validate_citation_ids([available[0]["id"]], available), available)
        with self.assertRaises(InvalidCitation):
            validate_citation_ids(["cite_unknown"], available)

    def test_provider_boundary_never_calls_network(self):
        adapter = DisabledByDefaultProviderAdapter()
        with patch("socket.create_connection") as network:
            with self.assertRaises(ProviderUnavailable):
                adapter.generate(question="q", evidence=())
        network.assert_not_called()


class ConversationApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("api-conversation@example.test", None, it_role=User.ITRole.IT_EDITOR)
        self.other = User.objects.create_user("api-other@example.test", None, it_role=User.ITRole.IT_MEMBER)
        self.client = APIClient()

    def test_anonymous_denied_and_owner_crud_is_private(self):
        self.assertEqual(self.client.get("/api/v1/copilot/conversations").status_code, 401)
        self.client.force_login(self.owner)
        created = self.client.post("/api/v1/copilot/conversations", {"title": "Private"}, format="json")
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["conversation"]["id"]
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/api/v1/copilot/conversations/{conversation_id}").status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/v1/copilot/conversations?page_size=1").json()["pagination"]["count"], 1)
        self.assertEqual(self.client.delete(f"/api/v1/copilot/conversations/{conversation_id}").status_code, 204)

    @patch("copilot.conversations.retrieve_authorized_evidence", return_value=evidence_result())
    def test_message_endpoint_returns_reference_only_fallback(self, retrieve):
        conversation = create_conversation(actor=self.owner)
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/api/v1/copilot/conversations/{conversation.pk}/messages",
            {"question": "reset password"}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        assistant = response.json()["assistant_message"]
        self.assertEqual(assistant["content"], "")
        self.assertEqual(assistant["grounding_status"], "references")
        self.assertEqual(len(assistant["citations"]), 1)

    def test_input_and_pagination_are_bounded(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/v1/copilot/conversations?page_size=101").status_code, 400)
        conversation = create_conversation(actor=self.owner)
        response = self.client.post(
            f"/api/v1/copilot/conversations/{conversation.pk}/messages",
            {"question": "x" * 2001}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_conversation_is_hidden_and_generically_unavailable(self):
        conversation = create_conversation(actor=self.owner)
        CopilotConversation.objects.filter(pk=conversation.pk).update(
            retention_expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.client.force_login(self.owner)
        listed = self.client.get("/api/v1/copilot/conversations")
        self.assertEqual(listed.json()["pagination"]["count"], 0)
        url = f"/api/v1/copilot/conversations/{conversation.pk}"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertEqual(self.client.post(f"{url}/messages", {"question": "renew"}, format="json").status_code, 404)
        self.assertTrue(CopilotConversation.objects.filter(pk=conversation.pk).exists())
