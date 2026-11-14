import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.lookups import Exact, GreaterThan, LessThanOrEqual
from django.db.models.functions import Length


ENVELOPE_VERSION = 1
ENVELOPE_SCHEMA_VERSION = 1
NONCE_BYTES = 12
TAG_BYTES = 16
DEK_BYTES = 32
MAX_ENVELOPE_BYTES = 80 * 1024


def _validate_envelope(nonce, ciphertext, tag):
    errors = {}
    if not isinstance(nonce, (bytes, bytearray, memoryview)) or len(nonce) != NONCE_BYTES:
        errors["nonce"] = f"Nonce must be exactly {NONCE_BYTES} bytes"
    if not isinstance(ciphertext, (bytes, bytearray, memoryview)) or not 0 < len(ciphertext) <= MAX_ENVELOPE_BYTES:
        errors["ciphertext"] = "Ciphertext length is invalid"
    if not isinstance(tag, (bytes, bytearray, memoryview)) or len(tag) != TAG_BYTES:
        errors["tag"] = f"Tag must be exactly {TAG_BYTES} bytes"
    if errors:
        raise ValidationError(errors)


class VaultOwnerKey(models.Model):
    """A per-owner DEK wrapped by the external application KEK."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vault_keys")
    key_version = models.PositiveIntegerField()
    envelope_version = models.PositiveSmallIntegerField(default=ENVELOPE_VERSION, editable=False)
    nonce = models.BinaryField(max_length=NONCE_BYTES, editable=False)
    wrapped_dek = models.BinaryField(max_length=DEK_BYTES, editable=False)
    tag = models.BinaryField(max_length=TAG_BYTES, editable=False)
    active_slot = models.BooleanField(default=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    retired_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("owner_id", "-key_version")
        constraints = [
            models.UniqueConstraint(fields=("owner", "key_version"), name="vault_owner_key_version_unique"),
            models.UniqueConstraint(fields=("owner", "active_slot"), name="vault_owner_one_active_key"),
            models.CheckConstraint(condition=models.Q(key_version__gt=0), name="vault_owner_key_version_positive"),
            models.CheckConstraint(condition=models.Q(envelope_version=1), name="vault_owner_key_envelope_v1"),
            models.CheckConstraint(condition=Exact(Length("nonce"), NONCE_BYTES), name="vault_owner_key_nonce_length"),
            models.CheckConstraint(condition=Exact(Length("wrapped_dek"), DEK_BYTES), name="vault_owner_key_wrapped_length"),
            models.CheckConstraint(condition=Exact(Length("tag"), TAG_BYTES), name="vault_owner_key_tag_length"),
            models.CheckConstraint(
                condition=(
                    models.Q(active_slot=True, retired_at__isnull=True)
                    | models.Q(active_slot__isnull=True, retired_at__isnull=False)
                ),
                name="vault_owner_key_state_matches",
            ),
        ]
        indexes = [models.Index(fields=("owner", "active_slot"), name="vault_owner_active_idx")]

    def clean(self):
        super().clean()
        _validate_envelope(self.nonce, self.wrapped_dek, self.tag)
        if len(self.wrapped_dek) != DEK_BYTES:
            raise ValidationError({"wrapped_dek": f"Wrapped DEK must be exactly {DEK_BYTES} bytes"})

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


class VaultRecord(models.Model):
    class CredentialType(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        API_TOKEN = "API_TOKEN", "API token"
        SSH_KEY = "SSH_KEY", "SSH key"
        GENERIC_SECRET = "GENERIC_SECRET", "Generic secret"

    class Lifecycle(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DELETED = "DELETED", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vault_records")
    credential_type = models.CharField(max_length=24, choices=CredentialType.choices)
    label = models.CharField(max_length=120)
    service_label = models.CharField(max_length=120, blank=True)
    origin = models.CharField(max_length=2048, blank=True)
    lifecycle = models.CharField(max_length=16, choices=Lifecycle.choices, default=Lifecycle.ACTIVE)
    revision = models.PositiveBigIntegerField(default=1)
    schema_version = models.PositiveSmallIntegerField(default=ENVELOPE_SCHEMA_VERSION, editable=False)
    envelope_version = models.PositiveSmallIntegerField(default=ENVELOPE_VERSION, editable=False)
    key_version = models.PositiveIntegerField(editable=False)
    nonce = models.BinaryField(max_length=NONCE_BYTES, editable=False)
    ciphertext = models.BinaryField(max_length=MAX_ENVELOPE_BYTES, editable=False)
    tag = models.BinaryField(max_length=TAG_BYTES, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    restore_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(condition=models.Q(revision__gt=0), name="vault_record_revision_positive"),
            models.CheckConstraint(condition=models.Q(key_version__gt=0), name="vault_record_key_version_positive"),
            models.CheckConstraint(condition=models.Q(schema_version=1), name="vault_record_schema_v1"),
            models.CheckConstraint(condition=models.Q(envelope_version=1), name="vault_record_envelope_v1"),
            models.CheckConstraint(condition=Exact(Length("nonce"), NONCE_BYTES), name="vault_record_nonce_length"),
            models.CheckConstraint(
                condition=GreaterThan(Length("ciphertext"), 0) & LessThanOrEqual(Length("ciphertext"), MAX_ENVELOPE_BYTES),
                name="vault_record_ciphertext_length",
            ),
            models.CheckConstraint(condition=Exact(Length("tag"), TAG_BYTES), name="vault_record_tag_length"),
            models.CheckConstraint(
                condition=(
                    models.Q(lifecycle="ACTIVE", deleted_at__isnull=True, restore_expires_at__isnull=True)
                    | models.Q(lifecycle="DELETED", deleted_at__isnull=False, restore_expires_at__isnull=False)
                ),
                name="vault_record_lifecycle_timestamps",
            ),
        ]
        indexes = [
            models.Index(fields=("owner", "lifecycle", "created_at", "id"), name="vault_owner_state_created_idx"),
            models.Index(fields=("owner", "credential_type", "created_at"), name="vault_owner_type_created_idx"),
        ]

    def clean(self):
        super().clean()
        _validate_envelope(self.nonce, self.ciphertext, self.tag)

    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)


class SensitiveOperationGrant(models.Model):
    class Scope(models.TextChoices):
        VAULT_SENSITIVE = "VAULT_SENSITIVE", "Vault sensitive operation"

    class RevocationReason(models.TextChoices):
        EXPLICIT = "EXPLICIT", "Explicit revocation"
        LOGOUT = "LOGOUT", "Logout"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED", "Account deactivated"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vault_sensitive_grants")
    session_digest = models.CharField(max_length=64, editable=False)
    proof_digest = models.CharField(max_length=64, unique=True, editable=False)
    scope = models.CharField(max_length=32, choices=Scope.choices, default=Scope.VAULT_SENSITIVE, editable=False)
    issued_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(editable=False)
    consumed_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)
    revocation_reason = models.CharField(
        max_length=32, choices=RevocationReason.choices, null=True, blank=True, editable=False
    )

    class Meta:
        indexes = [
            models.Index(fields=("user", "session_digest", "expires_at"), name="vault_grant_session_idx"),
            models.Index(fields=("user", "expires_at"), name="vault_grant_user_exp_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("issued_at")), name="vault_grant_expiry_after_issue"),
            models.CheckConstraint(
                condition=(
                    models.Q(revoked_at__isnull=True, revocation_reason__isnull=True)
                    | models.Q(revoked_at__isnull=False, revocation_reason__isnull=False)
                ),
                name="vault_grant_revocation_matches",
            ),
            models.CheckConstraint(
                condition=~(models.Q(consumed_at__isnull=False) & models.Q(revoked_at__isnull=False)),
                name="vault_grant_terminal_state_exclusive",
            ),
        ]


class UserReauthenticationThrottle(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vault_user_throttle")
    failure_window_started_at = models.DateTimeField()
    failure_count = models.PositiveSmallIntegerField(default=0)
    issuance_window_started_at = models.DateTimeField()
    issuance_count = models.PositiveSmallIntegerField(default=0)


class SessionReauthenticationThrottle(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vault_session_throttles")
    session_digest = models.CharField(max_length=64)
    failure_window_started_at = models.DateTimeField()
    failure_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "session_digest"), name="vault_session_throttle_unique"),
        ]
        indexes = [models.Index(fields=("user", "session_digest"), name="vault_session_throttle_idx")]
