from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import User


class UserModelTests(TestCase):
    def test_manager_canonicalizes_email_and_hashes_password(self):
        user = User.objects.create_user("  User@Example.COM ", "correct horse battery staple")
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("correct horse battery staple"))
        self.assertNotEqual(user.password, "correct horse battery staple")

    def test_case_insensitive_duplicate_email_is_rejected(self):
        User.objects.create_user("User@Example.com", "first-password")
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                User.objects.create_user("user@example.COM", "second-password")

    def test_model_save_canonicalizes_email(self):
        user = User(email="MixedCase@Example.COM")
        user.set_password("password")
        user.save()
        self.assertEqual(user.email, "mixedcase@example.com")

    def test_natural_key_lookup_canonicalizes_login_email(self):
        user = User.objects.create_user("login@example.com", "password")
        self.assertEqual(User.objects.get_by_natural_key(" LOGIN@EXAMPLE.COM "), user)
        self.assertEqual(authenticate(email=" LOGIN@EXAMPLE.COM ", password="password"), user)

    def test_empty_email_authentication_returns_none(self):
        self.assertIsNone(authenticate(email="", password="password"))

    def test_whitespace_email_authentication_returns_none(self):
        self.assertIsNone(authenticate(email="   ", password="password"))

    def test_user_creation_still_rejects_blank_email(self):
        for email in ("", "   "):
            with self.subTest(email=repr(email)):
                with self.assertRaises(ValueError):
                    User.objects.create_user(email, "password")

    def test_create_superuser_keeps_application_privileges_independent(self):
        user = User.objects.create_superuser("root@example.com", "password")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_app_admin)
        self.assertEqual(user.it_role, User.ITRole.NONE)

    def test_user_defaults_to_active_with_no_it_role(self):
        user = User.objects.create_user("member@example.com", "password")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_app_admin)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.it_role, User.ITRole.NONE)

    def test_inactive_user_is_rejected_by_django_authentication_backend(self):
        active = User.objects.create_user("active@example.com", "password")
        inactive = User.objects.create_user("inactive@example.com", "password", is_active=False)
        backend = ModelBackend()

        self.assertTrue(backend.user_can_authenticate(active))
        self.assertFalse(backend.user_can_authenticate(inactive))
        self.assertIsNone(authenticate(email=inactive.email, password="password"))
