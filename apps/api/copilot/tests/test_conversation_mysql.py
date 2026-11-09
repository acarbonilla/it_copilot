import threading
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from copilot.conversations import _delete_expired_ids, create_conversation, submit_question
from copilot.models import CopilotConversation, CopilotMessage
from copilot.retrieval import RetrievalResult


@skipUnless(connection.vendor == "mysql", "Native MySQL contract")
class NativeMySQLConversationTests(TransactionTestCase):
    def test_concurrent_turns_serialize_without_partial_pairs(self):
        owner = User.objects.create_user("native-turns@example.test", None, it_role=User.ITRole.IT_MEMBER)
        conversation = create_conversation(actor=owner)
        barrier = threading.Barrier(2); errors = []

        def submit(question):
            try:
                connections.close_all(); actor = User.objects.get(pk=owner.pk); barrier.wait()
                with patch("copilot.conversations.retrieve_authorized_evidence",
                           return_value=RetrievalResult(question, (), True)):
                    submit_question(actor=actor, conversation_id=conversation.pk, question=question)
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=submit, args=(f"question {index}",)) for index in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(15)
        self.assertEqual(errors, [])
        self.assertEqual(CopilotMessage.objects.filter(conversation=conversation).count(), 4)

    def test_renewal_after_stale_cleanup_selection_prevents_deletion(self):
        owner = User.objects.create_user("native-retention@example.test", None, it_role=User.ITRole.IT_MEMBER)
        selected_at = timezone.now()
        conversation = create_conversation(actor=owner, now=selected_at - timedelta(days=31))
        stale_candidates = tuple(CopilotConversation.objects.filter(
            retention_expires_at__lte=selected_at,
        ).values_list("id", flat=True))
        selected = threading.Event(); renewed = threading.Event(); errors = []; deleted = []

        def cleanup():
            try:
                connections.close_all(); selected.set()
                if not renewed.wait(10):
                    raise RuntimeError("renewal synchronization timed out")
                deleted.extend(_delete_expired_ids(candidate_ids=stale_candidates, now=selected_at))
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        def renew():
            try:
                connections.close_all()
                if not selected.wait(10):
                    raise RuntimeError("selection synchronization timed out")
                CopilotConversation.objects.filter(pk=conversation.pk).update(
                    last_activity_at=selected_at,
                    retention_expires_at=selected_at + timedelta(days=30),
                )
            except Exception as exc:
                errors.append(exc)
            finally:
                renewed.set(); connections.close_all()

        threads = [threading.Thread(target=cleanup), threading.Thread(target=renew)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(15)
        self.assertEqual(errors, [])
        self.assertEqual(deleted, [])
        self.assertTrue(CopilotConversation.objects.filter(pk=conversation.pk).exists())
