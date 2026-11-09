import uuid

from django.conf import settings
from django.db import models

from documents.models import Document, DocumentVersion


class RetrievalIndexGeneration(models.Model):
    class Status(models.TextChoices):
        PREPARING = "PREPARING", "Preparing"
        PUBLISHED = "PUBLISHED", "Published"
        OBSOLETE = "OBSOLETE", "Obsolete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="retrieval_generations")
    document_version = models.ForeignKey(
        DocumentVersion, on_delete=models.CASCADE, related_name="retrieval_generations",
    )
    source_digest = models.CharField(max_length=64, editable=False)
    chunker_version = models.CharField(max_length=64, editable=False)
    index_version = models.CharField(max_length=64, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREPARING)
    searchable_slot = models.BooleanField(null=True, default=None, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "searchable_slot"), name="copilot_one_searchable_generation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="PUBLISHED", searchable_slot=True, published_at__isnull=False)
                    | (~models.Q(status="PUBLISHED") & models.Q(searchable_slot__isnull=True))
                ),
                name="copilot_generation_publication_matches",
            ),
        ]
        indexes = [models.Index(fields=("status", "document"), name="copilot_generation_status_idx")]


class RetrievalChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.ForeignKey(
        RetrievalIndexGeneration, on_delete=models.CASCADE, related_name="chunks",
    )
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="retrieval_chunks")
    document_version = models.ForeignKey(
        DocumentVersion, on_delete=models.CASCADE, related_name="retrieval_chunks",
    )
    ordinal = models.PositiveIntegerField()
    searchable_text = models.TextField()
    content_digest = models.CharField(max_length=64, editable=False)
    token_count = models.PositiveIntegerField(editable=False)
    character_count = models.PositiveIntegerField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("generation_id", "ordinal")
        constraints = [
            models.UniqueConstraint(fields=("generation", "ordinal"), name="copilot_chunk_ordinal_unique"),
            models.CheckConstraint(condition=models.Q(token_count__gt=0), name="copilot_chunk_tokens_positive"),
            models.CheckConstraint(condition=models.Q(character_count__gt=0), name="copilot_chunk_chars_positive"),
        ]
        indexes = [
            models.Index(fields=("document", "document_version", "ordinal"), name="copilot_chunk_document_idx"),
        ]


class RetrievalIndexJob(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        RETRY_WAIT = "RETRY_WAIT", "Retry wait"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_version = models.ForeignKey(
        DocumentVersion, on_delete=models.CASCADE, related_name="retrieval_index_jobs",
    )
    source_digest = models.CharField(max_length=64, editable=False)
    generation_id = models.UUIDField(default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    nonterminal_slot = models.BooleanField(default=True, null=True, editable=False)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_owner = models.UUIDField(null=True, blank=True, editable=False)
    lease_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    heartbeat_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_error_code = models.CharField(max_length=32, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("available_at", "created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("document_version", "nonterminal_slot"), name="copilot_one_active_index_job",
            ),
            models.CheckConstraint(condition=models.Q(attempt_count__lte=3), name="copilot_index_attempt_limit"),
            models.CheckConstraint(
                condition=(
                    models.Q(state__in=("PENDING", "RUNNING", "RETRY_WAIT"), nonterminal_slot=True)
                    | models.Q(state__in=("SUCCEEDED", "FAILED", "CANCELLED"), nonterminal_slot__isnull=True)
                ),
                name="copilot_index_slot_matches_state",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state="RUNNING", lease_owner__isnull=False,
                        lease_expires_at__isnull=False, heartbeat_at__isnull=False,
                    )
                    | (~models.Q(state="RUNNING") & models.Q(
                        lease_owner__isnull=True, lease_expires_at__isnull=True, heartbeat_at__isnull=True,
                    ))
                ),
                name="copilot_index_lease_matches_state",
            ),
        ]
        indexes = [models.Index(fields=("state", "available_at"), name="copilot_index_claim_idx")]


class CopilotConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="copilot_conversations",
    )
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField()
    retention_expires_at = models.DateTimeField()

    class Meta:
        ordering = ("-last_activity_at", "-id")
        indexes = [
            models.Index(fields=("owner", "last_activity_at"), name="copilot_convo_owner_idx"),
            models.Index(fields=("retention_expires_at", "id"), name="copilot_convo_expiry_idx"),
        ]


class CopilotMessage(models.Model):
    class Role(models.TextChoices):
        USER = "USER", "User"
        ASSISTANT = "ASSISTANT", "Assistant"

    class GroundingStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        REFERENCES = "REFERENCES", "Authorized references"
        INSUFFICIENT = "INSUFFICIENT", "Insufficient evidence"

    class ProviderStatus(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        DISABLED = "DISABLED", "Disabled"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(CopilotConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    grounding_status = models.CharField(
        max_length=24, choices=GroundingStatus.choices, default=GroundingStatus.NOT_APPLICABLE,
    )
    provider_status = models.CharField(
        max_length=24, choices=ProviderStatus.choices, default=ProviderStatus.NOT_APPLICABLE,
    )
    citations = models.JSONField(default=list, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("conversation", "created_at"), name="copilot_message_history_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role="USER", grounding_status="NOT_APPLICABLE", provider_status="NOT_APPLICABLE")
                    | models.Q(role="ASSISTANT")
                ),
                name="copilot_message_user_statuses",
            ),
        ]
