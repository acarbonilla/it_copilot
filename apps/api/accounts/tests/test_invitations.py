import json
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.contrib.sessions.models import Session
from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from accounts.invitations import (
    InvalidActivation,
    InvitationConflict,
    PasswordPolicyFailure,
    activate_invitation,
    create_or_reissue_invitation,
)
from accounts.models import AccountInvitation, User
from security_audit.models import SecurityAuditEvent


class InvitationServiceTests(TransactionTestCase):
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
        self.actor = User.objects.create_user("admin@example.test", "admin-password", is_app_admin=True)

    def invite(self, email="invitee@example.test", **overrides):
        fields = {"actor": self.actor, "email": email, "it_role": User.ITRole.IT_MEMBER, "is_app_admin": False}
        fields.update(overrides)
        invitation = create_or_reissue_invitation(**fields)
        artifact = Path(self.mailbox.name) / f"{invitation.pk}.json"
        delivery = json.loads(artifact.read_text(encoding="utf-8"))
        token = delivery["activation_url"].rsplit("/", 1)[-1]
        return invitation, token, artifact

    def test_invitation_creates_pending_user_digest_only_delivery_and_atomic_audit(self):
        with self.assertNoLogs("accounts.invitations"):
            invitation, token, artifact = self.invite(email="  Invitee@Example.TEST ", is_app_admin=True)
        user = invitation.user
        self.assertEqual(user.email, "invitee@example.test")
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_app_admin)
        self.assertEqual(user.lifecycle_state, User.LifecycleState.PENDING_INVITATION)
        self.assertAlmostEqual((invitation.expires_at - invitation.created_at).total_seconds(), 24 * 60 * 60, delta=1)
        self.assertNotEqual(invitation.token_digest, token)
        self.assertNotIn(token, invitation.token_digest)
        self.assertTrue(artifact.exists())
        self.assertTrue(
            SecurityAuditEvent.objects.filter(
                action=SecurityAuditEvent.Action.ACCOUNT_INVITE_CREATED,
                actor_user_id=self.actor.pk,
                target_id=str(user.pk),
                outcome=SecurityAuditEvent.Outcome.SUCCESS,
            ).exists()
        )

    def test_activation_is_single_use_hashes_password_and_does_not_create_session(self):
        invitation, token, _ = self.invite()
        user = activate_invitation(token=token, password="unique-long-passphrase-4829")
        invitation.refresh_from_db()
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.lifecycle_state, User.LifecycleState.ACTIVE)
        self.assertTrue(user.check_password("unique-long-passphrase-4829"))
        self.assertNotEqual(user.password, "unique-long-passphrase-4829")
        self.assertIsNotNone(invitation.consumed_at)
        self.assertFalse(Session.objects.exists())
        with self.assertRaises(InvalidActivation):
            activate_invitation(token=token, password="another-long-passphrase-7391")

    def test_expired_revoked_unknown_and_malformed_tokens_are_invalid(self):
        invitation, token, _ = self.invite()
        AccountInvitation.objects.filter(pk=invitation.pk).update(expires_at=timezone.now())
        values = (token, "x" * 43, "malformed token")
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(InvalidActivation):
                    activate_invitation(token=value, password="unique-long-passphrase-4829")

        invitation, token, _ = self.invite("second@example.test")
        AccountInvitation.objects.filter(pk=invitation.pk).update(revoked_at=timezone.now())
        with self.assertRaises(InvalidActivation):
            activate_invitation(token=token, password="unique-long-passphrase-4829")

    def test_password_policy_rejects_short_common_numeric_and_similar_passwords(self):
        cases = (
            ("short@example.test", "short"),
            ("common@example.test", "password12345"),
            ("numeric@example.test", "1234567890123456"),
            ("similarperson@example.test", "similarperson2026"),
        )
        for email, password in cases:
            with self.subTest(password=password):
                invitation, token, _ = self.invite(email)
                with self.assertRaises(PasswordPolicyFailure):
                    activate_invitation(token=token, password=password)
                invitation.refresh_from_db()
                invitation.user.refresh_from_db()
                self.assertIsNone(invitation.consumed_at)
                self.assertFalse(invitation.user.is_active)
                self.assertFalse(invitation.user.has_usable_password())

    def test_reinvitation_revokes_old_token_and_updates_pending_grants(self):
        first, first_token, _ = self.invite()
        second, second_token, _ = self.invite(it_role=User.ITRole.IT_EDITOR, is_app_admin=True)
        first.refresh_from_db()
        second.user.refresh_from_db()
        self.assertEqual(first.user_id, second.user_id)
        self.assertIsNotNone(first.revoked_at)
        self.assertEqual(second.user.it_role, User.ITRole.IT_EDITOR)
        self.assertTrue(second.user.is_app_admin)
        with self.assertRaises(InvalidActivation):
            activate_invitation(token=first_token, password="unique-long-passphrase-4829")
        self.assertTrue(activate_invitation(token=second_token, password="unique-long-passphrase-4829").is_active)

    def test_active_and_nonpending_inactive_accounts_conflict(self):
        User.objects.create_user("active@example.test", "existing-password", is_active=True)
        User.objects.create_user("deactivated@example.test", "existing-password", is_active=False)
        for email in ("active@example.test", "deactivated@example.test"):
            with self.subTest(email=email):
                with self.assertRaises(InvitationConflict):
                    self.invite(email)

    def test_delivery_must_be_explicitly_enabled_in_debug(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(ImproperlyConfigured):
                create_or_reissue_invitation(
                    actor=self.actor,
                    email="disabled@example.test",
                    it_role=User.ITRole.IT_MEMBER,
                    is_app_admin=False,
                )
        self.assertFalse(User.objects.filter(email="disabled@example.test").exists())

    def test_partial_delivery_failure_rolls_back_and_removes_secret_artifact(self):
        with patch("accounts.invitations.json.dump", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.invite("delivery-failure@example.test")
        self.assertFalse(User.objects.filter(email="delivery-failure@example.test").exists())
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_delivery_collision_preserves_preexisting_file_and_rolls_back(self):
        collision_id = uuid.UUID("123e4567-e89b-42d3-a456-426614174000")
        artifact = Path(self.mailbox.name) / f"{collision_id}.json"
        artifact.write_text("PREEXISTING-SENTINEL", encoding="utf-8")
        with patch("accounts.invitations._invitation_id", return_value=collision_id):
            with self.assertRaises(FileExistsError):
                self.invite("collision@example.test")
        self.assertEqual(artifact.read_text(encoding="utf-8"), "PREEXISTING-SENTINEL")
        self.assertFalse(User.objects.filter(email="collision@example.test").exists())
        self.assertFalse(AccountInvitation.objects.filter(pk=collision_id).exists())

    def test_database_commit_failure_after_delivery_removes_artifact_and_rolls_back(self):
        commit_attempted = False

        def fail_commit():
            nonlocal commit_attempted
            commit_attempted = True
            raise DatabaseError("simulated commit failure")

        with patch.object(connection, "commit", side_effect=fail_commit):
            with self.assertRaises(DatabaseError):
                self.invite("commit-failure@example.test")
        self.assertTrue(commit_attempted)
        self.assertFalse(User.objects.filter(email="commit-failure@example.test").exists())
        self.assertFalse(AccountInvitation.objects.filter(user__email="commit-failure@example.test").exists())
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_invitation_audit_failure_rolls_back_user_invitation_and_delivery(self):
        with patch("accounts.invitations.record_critical_event", side_effect=DatabaseError("audit unavailable")):
            with self.assertRaises(DatabaseError):
                self.invite("rollback@example.test")
        self.assertFalse(User.objects.filter(email="rollback@example.test").exists())
        self.assertEqual(list(Path(self.mailbox.name).iterdir()), [])

    def test_activation_audit_failure_rolls_back_password_state_and_consumption(self):
        invitation, token, _ = self.invite()
        with patch("accounts.invitations.record_critical_event", side_effect=DatabaseError("audit unavailable")):
            with self.assertRaises(DatabaseError):
                activate_invitation(token=token, password="unique-long-passphrase-4829")
        invitation.refresh_from_db()
        invitation.user.refresh_from_db()
        self.assertIsNone(invitation.consumed_at)
        self.assertFalse(invitation.user.is_active)
        self.assertFalse(invitation.user.has_usable_password())


@skipUnless(connection.vendor == "mysql", "requires native MySQL row locking")
class NativeConcurrentActivationTests(InvitationServiceTests):
    def test_two_concurrent_activation_attempts_cannot_both_succeed(self):
        _, token, _ = self.invite("concurrent@example.test")

        def attempt():
            close_old_connections()
            try:
                activate_invitation(token=token, password="unique-long-passphrase-4829")
                return "activated"
            except InvalidActivation:
                return "denied"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ["activated", "denied"])
        invitation = AccountInvitation.objects.get(token_digest__isnull=False, user__email="concurrent@example.test")
        self.assertIsNotNone(invitation.consumed_at)
        self.assertTrue(invitation.user.is_active)
