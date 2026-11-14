import uuid
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from vault.lifecycle import deleted_metadata_payload, purge_time_is_eligible, restore_is_eligible
from vault.models import VaultRecord


def record_for(owner, *, lifecycle=VaultRecord.Lifecycle.ACTIVE, label="Example", created_offset=0):
    now = timezone.now() + timedelta(seconds=created_offset)
    values = dict(
        owner=owner, credential_type=VaultRecord.CredentialType.LOGIN, label=label,
        service_label="Service", origin="https://example.test", key_version=1,
        nonce=b"n" * 12, ciphertext=b"opaque-ciphertext", tag=b"t" * 16,
    )
    if lifecycle == VaultRecord.Lifecycle.DELETED:
        values.update(lifecycle=lifecycle, deleted_at=now, restore_expires_at=now + timedelta(days=30))
    return VaultRecord.objects.create(**values)


class DeletedCredentialApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("deleted-owner@example.test", "password")
        self.other = User.objects.create_user("deleted-other@example.test", "password", is_staff=True,
                                              is_superuser=True, is_app_admin=True,
                                              it_role=User.ITRole.IT_DOC_ADMIN)

    def test_owner_only_deleted_allowlist_and_cache_headers(self):
        deleted = record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED)
        record_for(self.owner)
        record_for(self.other, lifecycle=VaultRecord.Lifecycle.DELETED, label="Other owner")
        client = Client(); client.force_login(self.owner)
        with mock.patch("vault.services._decrypt_payload", side_effect=AssertionError("must not decrypt")):
            response = client.get("/api/v1/vault/deleted-credentials")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["credentials"]), 1)
        item = body["credentials"][0]
        self.assertEqual(item["id"], str(deleted.pk))
        self.assertEqual(set(item), {"id", "credential_type", "label", "service_label", "origin", "revision",
                                     "restorationEligible", "restorationExpiresAt"})
        self.assertNotIn("Other owner", str(body))
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_anonymous_rejected_and_non_admin_owner_allowed(self):
        self.assertEqual(Client().get("/api/v1/vault/deleted-credentials").status_code, 401)
        client = Client(); client.force_login(self.owner)
        self.assertEqual(client.get("/api/v1/vault/deleted-credentials").status_code, 200)

    def test_deleted_pagination_is_bounded_and_deterministic(self):
        for index in range(3):
            record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED, label=f"Deleted {index}")
        client = Client(); client.force_login(self.owner)
        first = client.get("/api/v1/vault/deleted-credentials?limit=2").json()
        second = client.get("/api/v1/vault/deleted-credentials", {"limit": 2, "cursor": first["nextCursor"]}).json()
        self.assertEqual(len(first["credentials"]), 2)
        self.assertEqual(len(second["credentials"]), 1)
        self.assertTrue({x["id"] for x in first["credentials"]}.isdisjoint(x["id"] for x in second["credentials"]))


class LifecycleFoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("lifecycle-owner@example.test", "password")

    def test_exact_restore_and_purge_boundary(self):
        record = record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED)
        boundary = record.restore_expires_at
        self.assertTrue(restore_is_eligible(record, now=boundary - timedelta(microseconds=1)))
        self.assertFalse(purge_time_is_eligible(record, now=boundary - timedelta(microseconds=1)))
        self.assertFalse(restore_is_eligible(record, now=boundary))
        self.assertTrue(purge_time_is_eligible(record, now=boundary))
        self.assertFalse(deleted_metadata_payload(record, now=boundary)["restorationEligible"])

    def test_purged_shape_allows_only_minimum_tombstone(self):
        record = record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED)
        now = timezone.now()
        VaultRecord.objects.filter(pk=record.pk).update(
            lifecycle=VaultRecord.Lifecycle.PURGED, label=None, service_label=None, origin=None,
            schema_version=None, envelope_version=None, key_version=None, nonce=None, ciphertext=None, tag=None,
            purged_at=now, purge_operation_id=uuid.uuid4(),
        )
        record.refresh_from_db()
        self.assertEqual(record.lifecycle, VaultRecord.Lifecycle.PURGED)
        self.assertIsNone(record.ciphertext)
        client = Client(); client.force_login(self.owner)
        self.assertEqual(client.get("/api/v1/vault/credentials").json()["credentials"], [])
        self.assertEqual(client.get("/api/v1/vault/deleted-credentials").json()["credentials"], [])

    def test_database_rejects_secret_bearing_purged_state(self):
        record = record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            VaultRecord.objects.filter(pk=record.pk).update(
                lifecycle=VaultRecord.Lifecycle.PURGED, purged_at=timezone.now(), purge_operation_id=uuid.uuid4())

    def test_purged_tombstone_does_not_count_as_active_deleted_cap(self):
        record = record_for(self.owner, lifecycle=VaultRecord.Lifecycle.DELETED)
        VaultRecord.objects.filter(pk=record.pk).update(
            lifecycle=VaultRecord.Lifecycle.PURGED, label=None, service_label=None, origin=None,
            schema_version=None, envelope_version=None, key_version=None, nonce=None, ciphertext=None, tag=None,
            purged_at=timezone.now(), purge_operation_id=uuid.uuid4(),
        )
        self.assertEqual(VaultRecord.objects.filter(
            owner=self.owner, lifecycle__in=(VaultRecord.Lifecycle.ACTIVE, VaultRecord.Lifecycle.DELETED)).count(), 0)
