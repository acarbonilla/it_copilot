import threading
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase

from accounts.models import User
from copilot.conversations import create_conversation, submit_question
from copilot.models import CopilotMessage
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
