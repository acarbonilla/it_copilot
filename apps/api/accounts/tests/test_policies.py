from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import User
from accounts.policies import (
    can_access_private_resource,
    can_access_private_web_document,
    can_access_credential_vault,
    can_archive_it_document,
    can_create_it_document,
    can_delete_it_document_permanently,
    can_manage_it_categories,
    can_publish_it_document,
    can_request_correction,
    can_revise_it_document,
    can_review_corrections,
    can_view_it_document,
)


SHARED_ACTIONS = {
    "manage_categories": can_manage_it_categories,
    "create": can_create_it_document,
    "revise": can_revise_it_document,
    "publish": can_publish_it_document,
    "archive": can_archive_it_document,
    "request_correction": can_request_correction,
    "review_corrections": can_review_corrections,
    "delete_permanently": can_delete_it_document_permanently,
}


class PolicyTests(TestCase):
    def user(self, role=User.ITRole.NONE, **flags):
        defaults = {"is_active": True, "is_app_admin": False, "is_staff": False, "is_superuser": False}
        pk = flags.pop("pk", 1)
        defaults.update(flags)
        return SimpleNamespace(pk=pk, is_authenticated=True, it_role=role, **defaults)

    def test_it_doc_admin_matrix(self):
        user = self.user(User.ITRole.IT_DOC_ADMIN)
        expected = {name: name != "request_correction" for name in SHARED_ACTIONS}
        self.assertEqual({name: policy(user) for name, policy in SHARED_ACTIONS.items()}, expected)
        self.assertTrue(can_view_it_document(user, published=False, archived=False))

    def test_it_editor_matrix(self):
        user = self.user(User.ITRole.IT_EDITOR)
        allowed = {"create", "revise", "publish", "archive", "review_corrections"}
        self.assertEqual({name for name, policy in SHARED_ACTIONS.items() if policy(user)}, allowed)
        self.assertTrue(can_view_it_document(user, published=False, archived=False))

    def test_it_member_matrix(self):
        user = self.user(User.ITRole.IT_MEMBER)
        self.assertEqual({name for name, policy in SHARED_ACTIONS.items() if policy(user)}, {"request_correction"})
        self.assertFalse(can_view_it_document(user, published=False, archived=False))
        self.assertTrue(can_view_it_document(user, published=True, archived=False))
        self.assertTrue(can_view_it_document(user, published=False, archived=True))

    def test_app_admin_without_it_role_is_denied_shared_actions(self):
        user = self.user(is_app_admin=True)
        self.assertTrue(all(not policy(user) for policy in SHARED_ACTIONS.values()))
        self.assertFalse(can_view_it_document(user, published=True, archived=True))

    def test_superuser_without_it_role_is_denied_shared_actions(self):
        user = self.user(is_staff=True, is_superuser=True)
        self.assertTrue(all(not policy(user) for policy in SHARED_ACTIONS.values()))
        self.assertFalse(can_view_it_document(user, published=True, archived=True))

    def test_anonymous_inactive_and_unknown_role_are_default_denied(self):
        users = [None, AnonymousUser(), self.user(User.ITRole.IT_EDITOR, is_active=False), self.user("UNKNOWN")]
        for user in users:
            with self.subTest(user=user):
                self.assertTrue(all(not policy(user) for policy in SHARED_ACTIONS.values()))
                self.assertFalse(can_view_it_document(user, published=True, archived=True))
                self.assertFalse(can_access_private_resource(user, owner_id=1))

    def test_private_resources_are_owner_only_without_admin_bypass(self):
        roles = [choice.value for choice in User.ITRole]
        flag_sets = [{}, {"is_app_admin": True}, {"is_staff": True, "is_superuser": True}]
        for role in roles:
            for flags in flag_sets:
                user = self.user(role, pk=10, **flags)
                with self.subTest(role=role, flags=flags):
                    self.assertTrue(can_access_private_resource(user, owner_id=10))
                    self.assertFalse(can_access_private_resource(user, owner_id=11))
                    self.assertTrue(can_access_private_web_document(user, owner_id=10))
                    self.assertFalse(can_access_private_web_document(user, owner_id=11))
                    self.assertTrue(can_access_credential_vault(user, owner_id=10))
                    self.assertFalse(can_access_credential_vault(user, owner_id=11))
