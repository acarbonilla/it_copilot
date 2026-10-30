import threading
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from documents.models import Document
from documents.services import DocumentConflictError, create_document, update_document_metadata


@skipUnless(connection.vendor == "mysql", "Native MySQL concurrency evidence")
class DocumentMetadataConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_writers_with_same_revision_cannot_both_commit(self):
        owner = User.objects.create_user("owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        document = create_document(actor=owner, title="Original")
        barrier = threading.Barrier(2)
        outcomes = []

        def writer(title):
            close_old_connections()
            try:
                thread_owner = User.objects.get(pk=owner.pk)
                barrier.wait(timeout=10)
                update_document_metadata(
                    actor=thread_owner,
                    document_id=document.pk,
                    expected_revision=1,
                    title=title,
                )
                outcomes.append("success")
            except DocumentConflictError:
                outcomes.append("conflict")
            finally:
                close_old_connections()

        threads = [threading.Thread(target=writer, args=(title,)) for title in ("First", "Second")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ["success", "conflict"])
        document.refresh_from_db()
        self.assertEqual(document.metadata_revision, 2)
