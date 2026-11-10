import base64
import os
import threading
from queue import Queue
from unittest import mock

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import User
from vault.models import VaultRecord
from vault.services import VaultConflictError, create_credential, update_credential
from vault.testing import authorize_sensitive_operation_for_test


TEST_KEK = base64.b64encode(b"mysql-concurrency-kek-material-32"[:32]).decode("ascii")


class VaultMySQLConcurrencyTests(TransactionTestCase):
    """Authoritative races: each worker obtains its own native DB connection."""

    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative concurrency evidence")
        self.env = mock.patch.dict(os.environ, {"VAULT_KEK_BASE64": TEST_KEK}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.owner = User.objects.create_user("mysql-race@example.test", "password")
        authorization = authorize_sensitive_operation_for_test(self.owner)
        self.record = create_credential(actor=self.owner, authorization=authorization, credential_type="LOGIN",
                                        label="Race", secret_fields={"password": "opaque-race-value"})

    def test_two_updates_at_one_revision_yield_one_commit_and_one_conflict(self):
        start = threading.Barrier(3)
        results = Queue()

        def worker(label):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.owner.pk)
                authorization = authorize_sensitive_operation_for_test(actor)
                start.wait(timeout=10)
                updated = update_credential(actor=actor, authorization=authorization, record_id=self.record.pk,
                                            expected_revision=1, metadata_changes={"label": label})
                results.put(("updated", updated.revision))
            except VaultConflictError:
                results.put(("conflict", None))
            except Exception as exc:  # surfaced by assertion without leaking request data
                results.put(("error", type(exc).__name__))
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(label,), daemon=True) for label in ("First", "Second")]
        for thread in threads:
            thread.start()
        start.wait(timeout=10)
        for thread in threads:
            thread.join(timeout=20)
            self.assertFalse(thread.is_alive(), "Concurrent update did not terminate")

        outcomes = sorted(results.get(timeout=2)[0] for _ in threads)
        self.assertEqual(outcomes, ["conflict", "updated"])
        self.record.refresh_from_db()
        self.assertEqual(self.record.revision, 2)
        self.assertIn(self.record.label, {"First", "Second"})
