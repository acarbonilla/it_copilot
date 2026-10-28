from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from accounts.models import User
from accounts.policies import (
    can_access_credential_vault,
    can_access_private_web_document,
    can_create_it_document,
    can_manage_it_categories,
    can_view_it_document,
)

from .factories import subject_factory


class AuthorizationMatrixTests(SimpleTestCase):
    def test_default_deny_subject_matrix(self):
        subjects = {
            "missing": None,
            "anonymous": AnonymousUser(),
            "inactive": subject_factory(it_role=User.ITRole.IT_DOC_ADMIN, is_active=False),
            "unknown_role": subject_factory(it_role="UNKNOWN_ROLE"),
        }
        for label, subject in subjects.items():
            with self.subTest(subject=label):
                self.assertFalse(can_manage_it_categories(subject))
                self.assertFalse(can_create_it_document(subject))
                self.assertFalse(can_view_it_document(subject, published=True, archived=True))
                self.assertFalse(can_access_private_web_document(subject, owner_id=1))
                self.assertFalse(can_access_credential_vault(subject, owner_id=1))

    def test_cross_owner_matrix_has_no_role_or_app_admin_bypass(self):
        roles = [choice.value for choice in User.ITRole] + ["UNKNOWN_ROLE"]
        for role in roles:
            for is_app_admin in (False, True):
                subject = subject_factory(pk=10, it_role=role, is_app_admin=is_app_admin)
                with self.subTest(role=role, is_app_admin=is_app_admin):
                    expected_owner_access = role != "UNKNOWN_ROLE"
                    self.assertEqual(can_access_private_web_document(subject, owner_id=10), expected_owner_access)
                    self.assertEqual(can_access_credential_vault(subject, owner_id=10), expected_owner_access)
                    self.assertFalse(can_access_private_web_document(subject, owner_id=11))
                    self.assertFalse(can_access_credential_vault(subject, owner_id=11))

    def test_app_admin_alone_has_no_it_document_permissions(self):
        subject = subject_factory(is_app_admin=True, it_role=User.ITRole.NONE)
        self.assertFalse(can_manage_it_categories(subject))
        self.assertFalse(can_create_it_document(subject))
        self.assertFalse(can_view_it_document(subject, published=True, archived=True))
