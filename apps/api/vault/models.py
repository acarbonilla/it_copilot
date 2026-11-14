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
        PURGED = "PURGED", "Purged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vault_records")
    credential_type = models.CharField(max_length=24, choices=CredentialType.choices)
    label = models.CharField(max_length=120, null=True)
    service_label = models.CharField(max_length=120, blank=True, null=True, default="")
    origin = models.CharField(max_length=2048, blank=True, null=True, default="")
    lifecycle = models.CharField(max_length=16, choices=Lifecycle.choices, default=Lifecycle.ACTIVE)
    revision = models.PositiveBigIntegerField(default=1)
    schema_version = models.PositiveSmallIntegerField(default=ENVELOPE_SCHEMA_VERSION, editable=False, null=True)
    envelope_version = models.PositiveSmallIntegerField(default=ENVELOPE_VERSION, editable=False, null=True)
    key_version = models.PositiveIntegerField(editable=False, null=True)
    nonce = models.BinaryField(max_length=NONCE_BYTES, editable=False, null=True)
    ciphertext = models.BinaryField(max_length=MAX_ENVELOPE_BYTES, editable=False, null=True)
    tag = models.BinaryField(max_length=TAG_BYTES, editable=False, null=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    restore_expires_at = models.DateTimeField(null=True, blank=True)
    purged_at = models.DateTimeField(null=True, blank=True, editable=False)
    purge_operation_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(condition=models.Q(revision__gt=0), name="vault_record_revision_positive"),
            models.CheckConstraint(condition=models.Q(key_version__isnull=True) | models.Q(key_version__gt=0), name="vault_record_key_version_positive"),
            models.CheckConstraint(condition=models.Q(schema_version__isnull=True) | models.Q(schema_version=1), name="vault_record_schema_v1"),
            models.CheckConstraint(condition=models.Q(envelope_version__isnull=True) | models.Q(envelope_version=1), name="vault_record_envelope_v1"),
            models.CheckConstraint(condition=models.Q(nonce__isnull=True) | Exact(Length("nonce"), NONCE_BYTES), name="vault_record_nonce_length"),
            models.CheckConstraint(
                condition=models.Q(ciphertext__isnull=True) | (GreaterThan(Length("ciphertext"), 0) & LessThanOrEqual(Length("ciphertext"), MAX_ENVELOPE_BYTES)),
                name="vault_record_ciphertext_length",
            ),
            models.CheckConstraint(condition=models.Q(tag__isnull=True) | Exact(Length("tag"), TAG_BYTES), name="vault_record_tag_length"),
            models.CheckConstraint(
                condition=(
                    models.Q(lifecycle="ACTIVE", deleted_at__isnull=True, restore_expires_at__isnull=True,
                             purged_at__isnull=True, purge_operation_id__isnull=True,
                             label__isnull=False, service_label__isnull=False, origin__isnull=False,
                             schema_version__isnull=False, envelope_version__isnull=False, key_version__isnull=False,
                             nonce__isnull=False, ciphertext__isnull=False, tag__isnull=False)
                    | models.Q(lifecycle="DELETED", deleted_at__isnull=False, restore_expires_at__isnull=False,
                               purged_at__isnull=True, purge_operation_id__isnull=True,
                               label__isnull=False, service_label__isnull=False, origin__isnull=False,
                               schema_version__isnull=False, envelope_version__isnull=False, key_version__isnull=False,
                               nonce__isnull=False, ciphertext__isnull=False, tag__isnull=False)
                    | models.Q(lifecycle="PURGED", deleted_at__isnull=False, restore_expires_at__isnull=False,
                               purged_at__isnull=False, purge_operation_id__isnull=False,
                               label__isnull=True, service_label__isnull=True, origin__isnull=True,
                               schema_version__isnull=True, envelope_version__isnull=True, key_version__isnull=True,
                               nonce__isnull=True, ciphertext__isnull=True, tag__isnull=True)
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
        if self.lifecycle == self.Lifecycle.PURGED:
            forbidden = (self.label, self.service_label, self.origin, self.schema_version, self.envelope_version,
                         self.key_version, self.nonce, self.ciphertext, self.tag)
            if any(value is not None for value in forbidden):
                raise ValidationError("Purged credentials cannot retain metadata, key references, or envelope material")
        else:
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


class VaultMaintenanceGuard(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class VaultMaintenanceOperation(models.Model):
    class Capability(models.TextChoices):
        CREDENTIAL_PURGE = "credential.purge", "Credential purge"
        HOLD_CREATE = "credential.hold.create", "Create credential hold"
        HOLD_RELEASE = "credential.hold.release", "Release credential hold"
        ROTATE_KEK = "key.rotate.kek", "Rotate KEK"
        ROTATE_DEK = "key.rotate.dek", "Rotate DEK"
        BACKUP_CREATE = "backup.create", "Create backup"
        RECOVERY_VERIFY = "recovery.verify", "Verify recovery"
        RETIRE_ONLINE = "key.retire.online", "Retire key online"

    class Mode(models.TextChoices):
        DRY_RUN = "DRY_RUN", "Dry run"
        EXECUTE = "EXECUTE", "Execute"
        CONTROL = "CONTROL", "Control action"

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator_id = models.CharField(max_length=64, editable=False)
    capability = models.CharField(max_length=32, choices=Capability.choices, editable=False)
    mode = models.CharField(max_length=16, choices=Mode.choices, editable=False)
    parameter_digest = models.CharField(max_length=64, editable=False)
    parent_dry_run = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="executions")
    backup_checkpoint_id = models.UUIDField(null=True, blank=True, editable=False)
    application_version = models.CharField(max_length=64, editable=False)
    schema_version = models.CharField(max_length=128, editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    eligible_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    resume_cursor = models.CharField(max_length=256, null=True, blank=True)
    failure_code = models.CharField(max_length=32, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    checkpoint_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    failed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(mode__in=("DRY_RUN", "CONTROL"), parent_dry_run__isnull=True) |
                                    models.Q(mode="EXECUTE", parent_dry_run__isnull=False), name="vault_maint_mode_parent"),
            models.CheckConstraint(condition=(models.Q(state="FAILED", failed_at__isnull=False, completed_at__isnull=True) |
                                    models.Q(state="COMPLETED", completed_at__isnull=False, failed_at__isnull=True) |
                                    models.Q(state__in=("PENDING", "RUNNING"), completed_at__isnull=True, failed_at__isnull=True)),
                                   name="vault_maint_terminal_time"),
        ]
        indexes = [models.Index(fields=("capability", "state", "created_at"), name="vault_maint_action_state_idx")]


class VaultMaintenanceConfirmation(models.Model):
    operation = models.OneToOneField(VaultMaintenanceOperation, on_delete=models.PROTECT, related_name="confirmation")
    parameter_digest = models.CharField(max_length=64, editable=False)
    artifact_digest = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField(editable=False)
    consumed_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("created_at")),
                                               name="vault_confirm_expiry_after_create")]


class VaultMaintenanceHold(models.Model):
    class Scope(models.TextChoices):
        OWNER = "OWNER", "Owner"
        RECORD = "RECORD", "Record"

    class Reason(models.TextChoices):
        LEGAL = "LEGAL", "Legal hold"
        SECURITY = "SECURITY", "Security investigation"
        RECOVERY = "RECOVERY", "Recovery verification"
        OPERATIONAL = "OPERATIONAL", "Operational hold"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=16, choices=Scope.choices)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vault_maintenance_holds")
    record = models.ForeignKey(VaultRecord, on_delete=models.PROTECT, null=True, blank=True, related_name="maintenance_holds")
    reason = models.CharField(max_length=16, choices=Reason.choices)
    created_by_operator_id = models.CharField(max_length=64, editable=False)
    created_operation = models.ForeignKey(VaultMaintenanceOperation, on_delete=models.PROTECT, related_name="created_holds")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    released_by_operator_id = models.CharField(max_length=64, null=True, blank=True, editable=False)
    released_operation = models.ForeignKey(VaultMaintenanceOperation, on_delete=models.PROTECT, null=True, blank=True,
                                           related_name="released_holds")
    released_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(scope="OWNER", record__isnull=True) |
                                    models.Q(scope="RECORD", record__isnull=False), name="vault_hold_scope_target"),
            models.CheckConstraint(condition=(models.Q(released_at__isnull=True, released_operation__isnull=True,
                                                       released_by_operator_id__isnull=True) |
                                    models.Q(released_at__isnull=False, released_operation__isnull=False,
                                             released_by_operator_id__isnull=False)), name="vault_hold_release_matches"),
        ]
        indexes = [models.Index(fields=("owner", "released_at"), name="vault_hold_owner_active_idx")]


class VaultMaintenanceJournal(models.Model):
    class OperationType(models.TextChoices):
        PURGE = "PURGE", "Purge"
        KEK_ROTATION = "KEK_ROTATION", "KEK rotation"
        DEK_ROTATION = "DEK_ROTATION", "DEK rotation"
        RECOVERY = "RECOVERY", "Recovery"

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        PAUSED = "PAUSED", "Paused"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.OneToOneField(VaultMaintenanceOperation, on_delete=models.PROTECT, related_name="journal")
    operation_type = models.CharField(max_length=20, choices=OperationType.choices)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                              related_name="vault_maintenance_journals")
    record = models.ForeignKey(VaultRecord, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="maintenance_journals")
    old_key_version = models.PositiveIntegerField(null=True, blank=True)
    new_key_version = models.PositiveIntegerField(null=True, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    batch_cursor = models.CharField(max_length=256, null=True, blank=True)
    checkpoint_digest = models.CharField(max_length=64, null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    failure_code = models.CharField(max_length=32, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(state="COMPLETED", completed_at__isnull=False) |
                                               ~models.Q(state="COMPLETED"), name="vault_journal_completion")]
        indexes = [models.Index(fields=("operation_type", "state"), name="vault_journal_type_state_idx")]


class VaultBackupSet(models.Model):
    class State(models.TextChoices):
        PREPARING = "PREPARING", "Preparing"
        FILES_COMPLETE = "FILES_COMPLETE", "Files complete"
        REGISTERED = "REGISTERED", "Registered"
        VERIFIED = "VERIFIED", "Verified"
        FAILED = "FAILED", "Failed"
        RECONCILE = "RECONCILE", "Needs reconciliation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.OneToOneField(VaultMaintenanceOperation, on_delete=models.PROTECT, related_name="backup_set")
    database_snapshot_id = models.UUIDField(unique=True)
    manifest_id = models.UUIDField(unique=True)
    protected_bundle_id = models.UUIDField(unique=True)
    snapshot_digest = models.CharField(max_length=64)
    bundle_digest = models.CharField(max_length=64)
    application_version = models.CharField(max_length=64)
    schema_version = models.CharField(max_length=128)
    key_inventory_digest = models.CharField(max_length=64)
    journal_checkpoint_id = models.UUIDField(null=True, blank=True)
    retention_state = models.CharField(max_length=24)
    hold_summary = models.CharField(max_length=64)
    manifest_auth_key_id = models.CharField(max_length=64)
    state = models.CharField(max_length=20, choices=State.choices, default=State.PREPARING)
    verification_evidence_digest = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    failed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(state="VERIFIED", verified_at__isnull=False,
                                                       verification_evidence_digest__isnull=False, failed_at__isnull=True) |
                                    ~models.Q(state="VERIFIED")), name="vault_backup_verified_evidence"),
            models.CheckConstraint(condition=(models.Q(state="FAILED", failed_at__isnull=False) |
                                    ~models.Q(state="FAILED")), name="vault_backup_failed_time"),
        ]
