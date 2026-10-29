import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Document(models.Model):
    class Visibility(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"
        DELETED = "DELETED", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_documents")
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, blank=True)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.ACTIVE)
    metadata_revision = models.PositiveBigIntegerField(default=1)
    current_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_for_documents",
    )
    candidate_version = models.ForeignKey(
        "DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="candidate_for_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(condition=models.Q(metadata_revision__gt=0), name="document_revision_positive"),
            models.CheckConstraint(
                condition=(
                    models.Q(visibility="DELETED", deleted_at__isnull=False)
                    | (~models.Q(visibility="DELETED") & models.Q(deleted_at__isnull=True))
                ),
                name="document_deleted_timestamp_matches",
            ),
        ]
        indexes = [
            models.Index(fields=("owner", "visibility", "created_at"), name="document_owner_state_idx"),
            models.Index(fields=("visibility", "created_at"), name="document_state_time_idx"),
        ]

    def _validate_version_ownership(self):
        errors = {}
        for field_name in ("current_version", "candidate_version"):
            version_id = getattr(self, f"{field_name}_id")
            if version_id is None:
                continue
            if self.pk is None or not DocumentVersion.objects.filter(pk=version_id, document_id=self.pk).exists():
                errors[field_name] = "Version must belong to this document"
        if errors:
            raise ValidationError(errors)

    def clean(self):
        super().clean()
        self._validate_version_ownership()

    def save(self, *args, **kwargs):
        self._validate_version_ownership()
        return super().save(*args, **kwargs)


class DocumentVersion(models.Model):
    class ProcessingState(models.TextChoices):
        STAGED = "STAGED", "Staged"
        QUEUED = "QUEUED", "Queued"
        PROCESSING = "PROCESSING", "Processing"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    sequence = models.PositiveIntegerField()
    processing_state = models.CharField(max_length=16, choices=ProcessingState.choices, default=ProcessingState.STAGED)
    created_by_user_id = models.BigIntegerField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("document_id", "-sequence")
        constraints = [
            models.UniqueConstraint(fields=("document", "sequence"), name="document_version_sequence_unique"),
            models.CheckConstraint(condition=models.Q(sequence__gt=0), name="document_version_sequence_positive"),
            models.CheckConstraint(condition=models.Q(created_by_user_id__gt=0), name="document_version_actor_positive"),
        ]
        indexes = [models.Index(fields=("document", "processing_state"), name="document_version_state_idx")]


class ProcessingJob(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        RETRY_WAIT = "RETRY_WAIT", "Retry wait"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="processing_jobs")
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    nonterminal_slot = models.BooleanField(default=True, null=True, editable=False)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_owner = models.UUIDField(null=True, blank=True, editable=False)
    lease_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    heartbeat_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancellation_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("available_at", "created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("document_version", "nonterminal_slot"),
                name="processing_job_one_nonterminal",
            ),
            models.CheckConstraint(condition=models.Q(attempt_count__lte=3), name="processing_job_attempt_limit"),
            models.CheckConstraint(
                condition=(
                    models.Q(state__in=("PENDING", "RUNNING", "RETRY_WAIT"), nonterminal_slot=True)
                    | models.Q(state__in=("SUCCEEDED", "FAILED", "CANCELLED"), nonterminal_slot__isnull=True)
                ),
                name="processing_job_slot_matches_state",
            ),
        ]
        indexes = [models.Index(fields=("state", "available_at"), name="processing_job_claim_idx")]


class ExtractedTextArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.OneToOneField(DocumentVersion, on_delete=models.CASCADE, related_name="extracted_text_artifact")
    storage_key = models.CharField(max_length=255, unique=True, editable=False)
    sha256_digest = models.CharField(max_length=64, editable=False)
    byte_length = models.PositiveBigIntegerField()
    character_count = models.PositiveIntegerField()
    extractor_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(byte_length__gt=0), name="extracted_text_bytes_positive"),
            models.CheckConstraint(condition=models.Q(character_count__lte=2_000_000), name="extracted_text_character_limit"),
        ]
