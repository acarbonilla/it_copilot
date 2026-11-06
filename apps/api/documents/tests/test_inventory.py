import hashlib
import os
import tempfile
import uuid
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.core import signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from documents import inventory
from documents.inventory import (
    InventoryCursorError, RecoveryIssue, assess_ready_consistency_page,
    inventory_recovery_page,
)
from documents.models import Document, DocumentVersion, ExtractedTextArtifact, OriginalArtifact, QuarantinedArtifact
from documents.storage import (
    ArtifactInventoryCapacityExceeded,
    ArtifactInventoryChanged,
    ArtifactStorageError,
    PrivateArtifactStore,
)


class BoundedArtifactInventoryTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "private"
        self.override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=self.root)
        self.override.enable(); self.addCleanup(self.override.disable)
        self.store = PrivateArtifactStore(); self.addCleanup(self.store.close)
        self.actor_id = 73

    def original(self, number, *, shard="00"):
        name = f"{number:032x}.bin"
        path = self.root / "originals" / shard / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"artifact-{number}".encode())
        return f"originals/{shard}/{name}"

    def cursor(self, state, *, actor_id=None):
        return inventory._encode_cursor(state, actor_id=actor_id or self.actor_id, store=self.store)

    def filesystem_cursor(self):
        fs = {"mode": "leaf", "directory": "00", "offset": 0, "digest": None,
              "root_offset": 1, "root_digest": None}
        return self.cursor({"v": 1, "phase": "filesystem_originals", "position": None, "fs": fs})

    def test_small_work_budget_bounds_directory_enumeration(self):
        for number in range(4): self.original(number)
        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4):
            with self.assertRaisesMessage(inventory.InventoryWorkLimitError, "directory snapshot"):
                inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, work_limit=5,
                    findings_limit=100, cursor=self.filesystem_cursor(),
                )
            page = inventory_recovery_page(
                actor_id=self.actor_id, store=self.store, work_limit=6,
                findings_limit=100, cursor=self.filesystem_cursor(),
            )
        self.assertEqual(page.work_performed, 6)
        self.assertFalse(page.complete)
        self.assertEqual(len(page.issues), 1)
        self.assertIsNotNone(page.next_cursor)

    def test_directory_overflow_stops_after_cap_plus_one_entries(self):
        for number in range(10): self.original(number)
        real_scandir = os.scandir
        yielded = 0

        class CountingScan:
            def __init__(self, path): self.iterator = real_scandir(path)
            def __enter__(self): return self
            def __exit__(self, *args): self.iterator.close()
            def __iter__(self): return self
            def __next__(self):
                nonlocal yielded
                entry = next(self.iterator); yielded += 1; return entry

        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4), patch(
            "documents.storage.os.scandir", side_effect=CountingScan,
        ):
            with self.assertRaises(ArtifactInventoryCapacityExceeded):
                inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, work_limit=20,
                    cursor=self.filesystem_cursor(),
                )
        self.assertEqual(yielded, 5)

    def test_stable_continuation_has_no_duplicate_or_missing_orphans(self):
        expected = {self.original(number) for number in range(3)}
        found = []
        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4):
            cursor = self.filesystem_cursor()
            for _ in range(10):
                page = inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, findings_limit=1,
                    work_limit=5000, cursor=cursor,
                )
                found.extend(issue.identifier for issue in page.issues if issue.kind == "orphan_artifact")
                if page.complete: break
                cursor = page.next_cursor
            else:
                self.fail("Inventory did not complete")
        self.assertEqual(set(found), expected)
        self.assertEqual(len(found), len(set(found)))

    def test_current_directory_mutation_invalidates_cursor(self):
        self.original(1); self.original(2)
        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4):
            first = inventory_recovery_page(
                actor_id=self.actor_id, store=self.store, findings_limit=1,
                work_limit=5000, cursor=self.filesystem_cursor(),
            )
            self.original(3)
            with self.assertRaises(ArtifactInventoryChanged):
                inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, findings_limit=1,
                    work_limit=5000, cursor=first.next_cursor,
                )

    def test_current_directory_deletion_invalidates_cursor(self):
        first_key = self.original(1); self.original(2)
        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4):
            first = inventory_recovery_page(
                actor_id=self.actor_id, store=self.store, findings_limit=1,
                work_limit=5000, cursor=self.filesystem_cursor(),
            )
            (self.root / first_key).unlink()
            with self.assertRaises(ArtifactInventoryChanged):
                inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, findings_limit=1,
                    work_limit=5000, cursor=first.next_cursor,
                )

    def test_cursor_tampering_expiry_and_scope_mismatch_fail_closed(self):
        token = self.filesystem_cursor()
        with self.assertRaises(InventoryCursorError):
            inventory_recovery_page(actor_id=self.actor_id, store=self.store, cursor=token + "x")
        with patch("documents.inventory.signing.loads", side_effect=signing.SignatureExpired("expired")):
            with self.assertRaisesMessage(InventoryCursorError, "expired"):
                inventory_recovery_page(actor_id=self.actor_id, store=self.store, cursor=token)
        with self.assertRaisesMessage(InventoryCursorError, "scope"):
            inventory_recovery_page(actor_id=self.actor_id + 1, store=self.store, cursor=token)
        other_root = Path(self.temporary.name) / "other-private"
        other_store = PrivateArtifactStore(other_root); self.addCleanup(other_store.close)
        with self.assertRaisesMessage(InventoryCursorError, "scope"):
            inventory_recovery_page(actor_id=self.actor_id, store=other_store, cursor=token)

    def test_filesystem_and_database_failures_do_not_report_completion(self):
        with patch.object(self.store, "inventory_directory_snapshot", side_effect=ArtifactStorageError("disk")):
            with self.assertRaises(ArtifactStorageError):
                inventory_recovery_page(
                    actor_id=self.actor_id, store=self.store, cursor=self.filesystem_cursor(),
                )
        with patch("documents.inventory.ProcessingJob.objects.filter", side_effect=DatabaseError("database")):
            with self.assertRaises(DatabaseError):
                inventory_recovery_page(actor_id=self.actor_id, store=self.store)

    def test_inventory_is_observational_and_never_quarantines(self):
        key = self.original(1)
        before = (self.root / key).read_bytes()
        with patch.object(self.store, "quarantine", side_effect=AssertionError("must not quarantine")):
            page = inventory_recovery_page(actor_id=self.actor_id, store=self.store)
        self.assertTrue(page.complete)
        self.assertIn(RecoveryIssue("orphan_artifact", key), page.issues)
        self.assertEqual((self.root / key).read_bytes(), before)
        self.assertFalse(QuarantinedArtifact.objects.exists())

    def test_referenced_original_and_extracted_artifacts_are_not_orphans(self):
        owner = User.objects.create_user("inventory-reference@example.test", None, it_role=User.ITRole.IT_MEMBER)
        document = Document.objects.create(owner=owner, title="Referenced")
        version = DocumentVersion.objects.create(
            document=document, sequence=1, processing_state=DocumentVersion.ProcessingState.READY,
            created_by_user_id=owner.pk,
        )
        original_key = self.original(1)
        original_bytes = (self.root / original_key).read_bytes()
        OriginalArtifact.objects.create(
            document_version=version, storage_key=original_key, original_filename="reference.txt",
            sha256_digest=hashlib.sha256(original_bytes).hexdigest(), byte_length=len(original_bytes),
            detected_media_type="text/plain",
        )
        extracted_key = f"extracted/{version.pk.hex}/{2:032x}.txt"
        extracted_path = self.root / extracted_key; extracted_path.parent.mkdir(parents=True); extracted_path.write_text("text")
        ExtractedTextArtifact.objects.create(
            document_version=version, storage_key=extracted_key,
            sha256_digest=hashlib.sha256(b"text").hexdigest(), byte_length=4,
            character_count=4, extractor_version="test",
        )
        page = inventory_recovery_page(actor_id=self.actor_id, store=self.store)
        self.assertTrue(page.complete)
        orphan_keys = {issue.identifier for issue in page.issues if issue.kind == "orphan_artifact"}
        self.assertNotIn(original_key, orphan_keys)
        self.assertNotIn(extracted_key, orphan_keys)

    def test_signed_cursor_rejects_invalid_internal_position(self):
        state = {"v": 1, "phase": "stale_jobs", "position": ["invalid", "id"], "fs": None}
        with self.assertRaises(InventoryCursorError):
            inventory_recovery_page(actor_id=self.actor_id, store=self.store, cursor=self.cursor(state))

    def test_command_reports_incomplete_page_and_continuation(self):
        actor = User.objects.create_user(
            "inventory-admin@example.test", "long-inventory-password-4829", is_app_admin=True,
        )
        key = self.original(1)
        output = StringIO()
        with patch.object(inventory, "DIRECTORY_ENTRY_CAP", 4):
            call_command(
                "reconcile_documents", actor_id=actor.pk, limit=1, work_limit=5000,
                stdout=output,
            )
        self.assertIn("complete=false", output.getvalue())
        self.assertIn("CONTINUATION:", output.getvalue())
        self.assertTrue((self.root / key).exists())
        with self.assertRaises(CommandError):
            call_command("reconcile_documents", actor_id=actor.pk, work_limit=10001)

    def test_historical_ready_assessment_is_bounded_read_only_and_continuable(self):
        owner = User.objects.create_user("assessment-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)
        documents = [Document(owner=owner, title=f"Historical {index}") for index in range(257)]
        Document.objects.bulk_create(documents)
        DocumentVersion.objects.bulk_create([
            DocumentVersion(
                document=document, sequence=1,
                processing_state=DocumentVersion.ProcessingState.READY,
                created_by_user_id=owner.pk,
            )
            for document in documents
        ])
        first = assess_ready_consistency_page(
            actor_id=self.actor_id, store=self.store, findings_limit=1000, work_limit=256,
        )
        self.assertFalse(first.complete)
        self.assertEqual(first.work_performed, 256)
        self.assertEqual(len(first.issues), 512)
        second = assess_ready_consistency_page(
            actor_id=self.actor_id, store=self.store, findings_limit=1000,
            work_limit=256, cursor=first.next_cursor,
        )
        self.assertTrue(second.complete)
        self.assertEqual(len(second.issues), 2)
        self.assertEqual(DocumentVersion.objects.filter(processing_state=DocumentVersion.ProcessingState.READY).count(), 257)


@skipUnless(connection.vendor == "mysql", "Native MySQL keyset evidence")
class InventoryKeysetMySQLTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.override = override_settings(DOCUMENT_PRIVATE_STORAGE_ROOT=Path(self.temporary.name) / "private")
        self.override.enable(); self.addCleanup(self.override.disable)
        self.store = PrivateArtifactStore(); self.addCleanup(self.store.close)
        self.owner = User.objects.create_user("inventory-owner@example.test", None, it_role=User.ITRole.IT_MEMBER)

    def test_database_batches_continue_at_256_without_duplicates(self):
        deleted_at = timezone.now() - timedelta(days=31)
        Document.objects.bulk_create([
            Document(
                owner=self.owner, title=f"Deleted {index}", visibility=Document.Visibility.DELETED,
                deleted_at=deleted_at,
            )
            for index in range(257)
        ])
        state = {"v": 1, "phase": "purge", "position": None, "fs": None}
        cursor = inventory._encode_cursor(state, actor_id=self.owner.pk, store=self.store)
        first = inventory_recovery_page(
            actor_id=self.owner.pk, store=self.store, findings_limit=1000,
            work_limit=256, cursor=cursor,
        )
        self.assertFalse(first.complete)
        self.assertEqual(first.work_performed, 256)
        self.assertEqual(len(first.issues), 256)
        second = inventory_recovery_page(
            actor_id=self.owner.pk, store=self.store, findings_limit=1000,
            work_limit=256, cursor=first.next_cursor,
        )
        self.assertTrue(second.complete)
        identifiers = [issue.identifier for issue in (*first.issues, *second.issues)]
        self.assertEqual(len(identifiers), 257)
        self.assertEqual(len(set(identifiers)), 257)
