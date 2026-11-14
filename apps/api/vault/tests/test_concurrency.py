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
from vault.tests.testing import authorize_sensitive_operation_for_test, patch_sensitive_authorization_for_test

import uuid


TEST_KEK = base64.b64encode(b"mysql-concurrency-kek-material-32"[:32]).decode("ascii")


class VaultMySQLConcurrencyTests(TransactionTestCase):
    """Authoritative races: each worker obtains its own native DB connection."""

    reset_sequences = True

    def setUp(self):
        if connection.vendor != "mysql":
            self.skipTest("Native MySQL is required for authoritative concurrency evidence")
        self.auth_patch = patch_sensitive_authorization_for_test()
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
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



    def test_concurrent_creates_at_owner_limit_allow_only_one(self):
        from vault import services

        # The existing setup creates one credential.
        # Lower the cap to two so only one additional slot remains.
        self.assertEqual(
            VaultRecord.objects.filter(owner=self.owner).count(),
            1,
        )

        start = threading.Barrier(3)
        results = Queue()

        def worker(label):
            close_old_connections()

            try:
                actor = User.objects.get(pk=self.owner.pk)
                authorization = authorize_sensitive_operation_for_test(actor)

                start.wait(timeout=10)

                record = create_credential(
                    actor=actor,
                    authorization=authorization,
                    credential_type="LOGIN",
                    label=label,
                    secret_fields={"password": "opaque-race-value"},
                )

                results.put(("created", str(record.pk)))

            except VaultConflictError:
                results.put(("conflict", None))

            except Exception as exc:
                results.put(("error", type(exc).__name__))

            finally:
                close_old_connections()

        with mock.patch.object(services, "MAX_RECORDS_PER_OWNER", 2):
            threads = [
                threading.Thread(
                    target=worker,
                    args=(label,),
                    daemon=True,
                )
                for label in ("First", "Second")
            ]

            for thread in threads:
                thread.start()

            start.wait(timeout=10)

            for thread in threads:
                thread.join(timeout=20)
                self.assertFalse(
                    thread.is_alive(),
                    "Concurrent create did not terminate",
                )

        outcomes = sorted(
            results.get(timeout=2)[0]
            for _ in threads
        )

        self.assertEqual(
            outcomes,
            ["conflict", "created"],
        )

        self.assertEqual(
            VaultRecord.objects.filter(owner=self.owner).count(),
            2,
        )



    def test_concurrent_creates_at_exact_1000_record_limit(self):
        from vault import services

        # setUp() already created one valid encrypted record.
        # Reuse its encrypted envelope for the remaining fixture rows.
        template = self.record

        fixture_records = [
            VaultRecord(
                id=uuid.uuid4(),
                owner=self.owner,
                credential_type=template.credential_type,
                label=f"Capacity fixture {index}",
                service_label=template.service_label,
                origin=template.origin,
                lifecycle=VaultRecord.Lifecycle.ACTIVE,
                revision=1,
                schema_version=template.schema_version,
                envelope_version=template.envelope_version,
                key_version=template.key_version,
                nonce=template.nonce,
                ciphertext=template.ciphertext,
                tag=template.tag,
            )
            for index in range(998)
        ]

        VaultRecord.objects.bulk_create(
            fixture_records,
            batch_size=200,
        )

        self.assertEqual(
            VaultRecord.objects.filter(owner=self.owner).count(),
            999,
        )

        self.assertEqual(
            services.MAX_RECORDS_PER_OWNER,
            1_000,
        )

        start = threading.Barrier(3)
        results = Queue()

        def worker(label):
            close_old_connections()

            try:
                actor = User.objects.get(pk=self.owner.pk)
                authorization = authorize_sensitive_operation_for_test(actor)

                start.wait(timeout=10)

                record = create_credential(
                    actor=actor,
                    authorization=authorization,
                    credential_type="LOGIN",
                    label=label,
                    secret_fields={"password": "opaque-race-value"},
                )

                results.put(("created", str(record.pk)))

            except VaultConflictError:
                results.put(("conflict", None))

            except Exception as exc:
                results.put(("error", type(exc).__name__))

            finally:
                close_old_connections()

        threads = [
            threading.Thread(
                target=worker,
                args=(label,),
                daemon=True,
            )
            for label in ("First", "Second")
        ]

        for thread in threads:
            thread.start()

        start.wait(timeout=10)

        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(
                thread.is_alive(),
                "Concurrent create did not terminate",
            )

        outcomes = sorted(
            results.get(timeout=2)[0]
            for _ in threads
        )

        self.assertEqual(
            outcomes,
            ["conflict", "created"],
        )

        self.assertEqual(
            VaultRecord.objects.filter(owner=self.owner).count(),
            1_000,
        )
