from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models


def canonicalize_email(email):
    if not email or not email.strip():
        raise ValueError("Users must have an email address")
    return email.strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        email = canonicalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(email=canonicalize_email(username))


class User(AbstractBaseUser, PermissionsMixin):
    class ITRole(models.TextChoices):
        NONE = "NONE", "No IT role"
        IT_DOC_ADMIN = "IT_DOC_ADMIN", "IT documentation administrator"
        IT_EDITOR = "IT_EDITOR", "IT editor"
        IT_MEMBER = "IT_MEMBER", "IT member"

    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_app_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    it_role = models.CharField(max_length=20, choices=ITRole.choices, default=ITRole.NONE)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    def clean(self):
        super().clean()
        try:
            self.email = canonicalize_email(self.email)
        except ValueError as exc:
            raise ValidationError({"email": str(exc)}) from exc

    def save(self, *args, **kwargs):
        self.email = canonicalize_email(self.email)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email
