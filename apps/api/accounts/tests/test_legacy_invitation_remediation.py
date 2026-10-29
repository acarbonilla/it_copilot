import json
import secrets
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from accounts.invitations import InvalidActivation, _token_digest, activate_invitation, create_or_reissue_invitation
from accounts.legacy_invitation_remediation import remediate_legacy_invitation
from accounts.models import AccountInvitation, User
from security_audit.models import SecurityAuditEvent


class LegacyInvitationRemediationTests(TransactionTestCase):
    def setUp(self):
        self.mailbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.mailbox.cleanup)
        self.settings_override = override_settings(
            DEBUG=True,
            INVITATION_DELIVERY_MODE="file",
            INVITATION_MAILBOX_ROOT=Path(self.mailbox.name),
            INVITATION_ACTIVATION_BASE_URL="http://localhost:3000/activate",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.actor = User.objects.create_user(
            "actor@example.test", "strong-actor-password", is_app_admin=True,
            lifecycle_state=User.LifecycleState.ACTIVE,
        )

    def legacy(self, *, email="pending@example.test", expires_at=None):
        user = User.objects.create_user(
            email, password=None, is_active=False,
            lifecycle_state=User.LifecycleState.PENDING_INVITATION,
        )
        invitation = AccountInvitation.objects.create(
            user=user,
            token_digest=("a" if not AccountInvitation.objects.exists() else "b") * 64,
            expires_at=expires_at or timezone.now() + timezone.timedelta(hours=1),
            invited_by_user_id=self.actor.pk,
            delivery_format=AccountInvitation.DeliveryFormat.LEGACY_PATH,
        )
        return invitation

    def test_dry_run_is_default_and_changes_nothing(self):
        invitation = self.legacy()
        output = StringIO()
        call_command("remediate_legacy_invitations", actor_id=self.actor.pk, stdout=output)
        invitation.refresh_from_db()
        self.assertIsNone(invitation.revoked_at)
        self.assertIn("DRY RUN: 1", output.getvalue())
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_execute_revokes_and_reissues_fragment_invitation_with_actor_audit(self):
        original = self.legacy()
        call_command("remediate_legacy_invitations", actor_id=self.actor.pk, execute=True, stdout=StringIO())
        original.refresh_from_db()
        replacement = AccountInvitation.objects.exclude(pk=original.pk).get()
        artifact = Path(self.mailbox.name) / f"{replacement.pk}.json"
        delivery = json.loads(artifact.read_text(encoding="utf-8"))
        token = delivery["activation_url"].split("#token=", 1)[1]
        self.assertIsNotNone(original.revoked_at)
        self.assertEqual(replacement.delivery_format, AccountInvitation.DeliveryFormat.FRAGMENT_V1)
        self.assertNotEqual(replacement.token_digest, token)
        self.assertNotIn(token, replacement.token_digest)
        self.assertEqual(
            set(SecurityAuditEvent.objects.values_list("action", flat=True)),
            {SecurityAuditEvent.Action.ACCOUNT_INVITE_REVOKED, SecurityAuditEvent.Action.ACCOUNT_INVITE_REISSUED},
        )
        self.assertFalse(SecurityAuditEvent.objects.exclude(actor_user_id=self.actor.pk).exists())

    def test_expired_legacy_invitation_is_revoked_without_reissue(self):
        original = self.legacy(expires_at=timezone.now() - timezone.timedelta(seconds=1))
        result = remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        original.refresh_from_db()
        self.assertEqual(result.outcome, "revoked_without_reissue")
        self.assertIsNotNone(original.revoked_at)
        self.assertEqual(AccountInvitation.objects.count(), 1)
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_repeat_execution_is_idempotent(self):
        original = self.legacy()
        first = remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        second = remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        self.assertEqual(first.outcome, "reissued")
        self.assertEqual(second.outcome, "already_remediated")
        self.assertEqual(AccountInvitation.objects.count(), 2)
        self.assertEqual(len(list(Path(self.mailbox.name).iterdir())), 1)

    def test_delivery_failure_rolls_back_revocation_reissue_and_audit(self):
        original = self.legacy()
        with patch("accounts.legacy_invitation_remediation._delivery_file", side_effect=OSError("delivery failed")):
            with self.assertRaises(OSError):
                remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        original.refresh_from_db()
        self.assertIsNone(original.revoked_at)
        self.assertEqual(AccountInvitation.objects.count(), 1)
        self.assertFalse(SecurityAuditEvent.objects.exists())

    def test_audit_failure_rolls_back_and_removes_delivery_artifact(self):
        original = self.legacy()
        calls = 0

        def fail_second_audit(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise DatabaseError("audit unavailable")
            return SecurityAuditEvent.objects.create(**kwargs)

        with patch("accounts.legacy_invitation_remediation.record_critical_event", side_effect=fail_second_audit):
            with self.assertRaises(DatabaseError):
                remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        original.refresh_from_db()
        self.assertIsNone(original.revoked_at)
        self.assertEqual(AccountInvitation.objects.count(), 1)
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_database_commit_failure_rolls_back_and_removes_delivery_artifact(self):
        original = self.legacy()
        with patch.object(connection, "commit", side_effect=DatabaseError("commit failed")):
            with self.assertRaises(DatabaseError):
                remediate_legacy_invitation(actor=self.actor, invitation_id=original.pk)
        original.refresh_from_db()
        self.assertIsNone(original.revoked_at)
        self.assertEqual(AccountInvitation.objects.count(), 1)
        self.assertFalse(SecurityAuditEvent.objects.exists())
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_actor_must_be_active_activated_app_admin(self):
        self.legacy()
        invalid = User.objects.create_user("member@example.test", "member-password")
        with self.assertRaises(CommandError):
            call_command("remediate_legacy_invitations", actor_id=invalid.pk, execute=True)

    def test_concurrent_remediation_reissues_only_once(self):
        if connection.vendor != "mysql":
            self.skipTest("requires native MySQL row locking")
        original = self.legacy()

        def attempt():
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                return remediate_legacy_invitation(actor=actor, invitation_id=original.pk).outcome
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(outcomes, ["reissued", "already_remediated"])
        self.assertEqual(AccountInvitation.objects.count(), 2)
        self.assertEqual(len(list(Path(self.mailbox.name).iterdir())), 1)

    def test_ordinary_reinvitation_racing_legacy_remediation_is_guard_serialized(self):
        if connection.vendor != "mysql":
            self.skipTest("requires native MySQL row locking")
        original = self.legacy(email="race@example.test")
        legacy_token = secrets.token_urlsafe(32)
        AccountInvitation.objects.filter(pk=original.pk).update(token_digest=_token_digest(legacy_token))
        legacy_artifact = Path(self.mailbox.name) / f"{original.pk}.json"
        legacy_artifact.write_text(
            json.dumps(
                {
                    "recipient": original.user.email,
                    "activation_url": f"http://localhost:3000/activate/{legacy_token}",
                }
            ),
            encoding="utf-8",
        )
        start = Barrier(2)

        def ordinary_reinvite():
            close_old_connections()
            try:
                start.wait()
                actor = User.objects.get(pk=self.actor.pk)
                invitation = create_or_reissue_invitation(
                    actor=actor,
                    email=original.user.email,
                    it_role=User.ITRole.IT_EDITOR,
                    is_app_admin=False,
                )
                return "ordinary", str(invitation.pk)
            finally:
                close_old_connections()

        def legacy_remediation():
            close_old_connections()
            try:
                start.wait()
                actor = User.objects.get(pk=self.actor.pk)
                result = remediate_legacy_invitation(actor=actor, invitation_id=original.pk)
                return result.outcome, result.replacement_id
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            ordinary_future = executor.submit(ordinary_reinvite)
            remediation_future = executor.submit(legacy_remediation)
            ordinary_result = ordinary_future.result()
            remediation_result = remediation_future.result()

        original.refresh_from_db()
        self.assertIsNotNone(original.revoked_at)
        active_invitations = list(
            AccountInvitation.objects.filter(
                user=original.user,
                consumed_at__isnull=True,
                revoked_at__isnull=True,
            )
        )
        self.assertEqual(len(active_invitations), 1)
        active = active_invitations[0]
        self.assertEqual(active.delivery_format, AccountInvitation.DeliveryFormat.FRAGMENT_V1)
        self.assertEqual(ordinary_result, ("ordinary", str(active.pk)))
        self.assertIn(remediation_result[0], {"reissued", "already_remediated"})

        artifacts = {}
        for artifact in Path(self.mailbox.name).glob("*.json"):
            invitation_id = artifact.stem
            delivery = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertTrue(AccountInvitation.objects.filter(pk=invitation_id).exists())
            artifacts[invitation_id] = delivery["activation_url"]
        self.assertEqual(artifacts[str(original.pk)], f"http://localhost:3000/activate/{legacy_token}")
        self.assertIn(str(active.pk), artifacts)
        self.assertEqual(artifacts[str(active.pk)].split("#token=", 1)[0], "http://localhost:3000/activate")

        delivered_tokens = {}
        for invitation_id, url in artifacts.items():
            delivered_tokens[invitation_id] = url.split("#token=", 1)[1] if "#token=" in url else url.rsplit("/", 1)[1]
        for invitation_id, token in delivered_tokens.items():
            if invitation_id == str(active.pk):
                continue
            with self.assertRaises(InvalidActivation):
                activate_invitation(token=token, password="unique-long-passphrase-4829")
        activated = activate_invitation(
            token=delivered_tokens[str(active.pk)],
            password="unique-long-passphrase-4829",
        )
        self.assertEqual(activated.pk, original.user_id)

        events = list(SecurityAuditEvent.objects.order_by("id"))
        self.assertTrue(events)
        self.assertTrue(all(event.actor_user_id in {None, self.actor.pk} for event in events))
        self.assertEqual(
            sum(event.action == SecurityAuditEvent.Action.ACCOUNT_INVITE_CREATED for event in events),
            1,
        )
        expected_remediation_events = 1 if remediation_result[0] == "reissued" else 0
        self.assertEqual(
            sum(event.action == SecurityAuditEvent.Action.ACCOUNT_INVITE_REVOKED for event in events),
            expected_remediation_events,
        )
        self.assertEqual(
            sum(event.action == SecurityAuditEvent.Action.ACCOUNT_INVITE_REISSUED for event in events),
            expected_remediation_events,
        )
        serialized_events = json.dumps(
            list(
                SecurityAuditEvent.objects.values(
                    "action", "actor_user_id", "target_type", "target_id", "outcome"
                )
            )
        )
        for token in delivered_tokens.values():
            self.assertNotIn(token, serialized_events)
