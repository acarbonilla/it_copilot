import uuid

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
        try:
            email = canonicalize_email(username)
        except ValueError as exc:
            raise self.model.DoesNotExist from exc
        return self.get(email=email)


class User(AbstractBaseUser, PermissionsMixin):
    class LifecycleState(models.TextChoices):
        ACTIVE = "ACTIVE", "Active or legacy account"
        PENDING_INVITATION = "PENDING_INVITATION", "Pending invitation"
        DEACTIVATED = "DEACTIVATED", "Deactivated account"

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
    lifecycle_state = models.CharField(max_length=24, choices=LifecycleState.choices, default=LifecycleState.ACTIVE)

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


class AccountInvitation(models.Model):
    class DeliveryFormat(models.TextChoices):
        LEGACY_PATH = "LEGACY_PATH", "Legacy path token"
        FRAGMENT_V1 = "FRAGMENT_V1", "URL fragment token v1"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="invitations")
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    invited_by_user_id = models.BigIntegerField(editable=False)
    delivery_format = models.CharField(
        max_length=16,
        choices=DeliveryFormat.choices,
        default=DeliveryFormat.FRAGMENT_V1,
        editable=False,
    )

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(invited_by_user_id__gt=0), name="invitation_actor_positive"),
            models.CheckConstraint(
                condition=models.Q(consumed_at__isnull=True) | models.Q(revoked_at__isnull=True),
                name="invitation_not_consumed_and_revoked",
            ),
        ]
        indexes = [models.Index(fields=("user", "created_at"), name="invitation_user_time_idx")]


class AdminLifecycleGuard(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class AccountDeletionReview(models.Model):
    class Reason(models.TextChoices):
        NO_LONGER_NEEDED = "NO_LONGER_NEEDED", "Account no longer needed"
        SECURITY_CONCERN = "SECURITY_CONCERN", "Security concern"
        DUPLICATE_ACCOUNT = "DUPLICATE_ACCOUNT", "Duplicate account"

    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "Pending review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey(User, on_delete=models.PROTECT, related_name="deletion_reviews")
    requested_by_user_id = models.BigIntegerField(editable=False)
    reason_code = models.CharField(max_length=32, choices=Reason.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_REVIEW)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(requested_by_user_id__gt=0), name="deletion_review_actor_positive")
        ]
