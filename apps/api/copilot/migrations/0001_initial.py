import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("documents", "0007_document_retrieval_change")]

    operations = [
        migrations.CreateModel(
            name="RetrievalIndexGeneration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_digest", models.CharField(editable=False, max_length=64)),
                ("chunker_version", models.CharField(editable=False, max_length=64)),
                ("index_version", models.CharField(editable=False, max_length=64)),
                ("status", models.CharField(choices=[("PREPARING", "Preparing"), ("PUBLISHED", "Published"), ("OBSOLETE", "Obsolete")], default="PREPARING", max_length=16)),
                ("searchable_slot", models.BooleanField(default=None, editable=False, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("published_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_generations", to="documents.document")),
                ("document_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_generations", to="documents.documentversion")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="RetrievalIndexJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_digest", models.CharField(editable=False, max_length=64)),
                ("generation_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("state", models.CharField(choices=[("PENDING", "Pending"), ("RUNNING", "Running"), ("RETRY_WAIT", "Retry wait"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=16)),
                ("nonterminal_slot", models.BooleanField(default=True, editable=False, null=True)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("available_at", models.DateTimeField()),
                ("lease_owner", models.UUIDField(blank=True, editable=False, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("heartbeat_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("completed_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("last_error_code", models.CharField(blank=True, editable=False, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_index_jobs", to="documents.documentversion")),
            ],
            options={"ordering": ("available_at", "created_at", "id")},
        ),
        migrations.CreateModel(
            name="RetrievalChunk",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("ordinal", models.PositiveIntegerField()),
                ("searchable_text", models.TextField()),
                ("content_digest", models.CharField(editable=False, max_length=64)),
                ("token_count", models.PositiveIntegerField(editable=False)),
                ("character_count", models.PositiveIntegerField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_chunks", to="documents.document")),
                ("document_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_chunks", to="documents.documentversion")),
                ("generation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="copilot.retrievalindexgeneration")),
            ],
            options={"ordering": ("generation_id", "ordinal")},
        ),
        migrations.AddConstraint(model_name="retrievalindexgeneration", constraint=models.UniqueConstraint(fields=("document", "searchable_slot"), name="copilot_one_searchable_generation")),
        migrations.AddConstraint(model_name="retrievalindexgeneration", constraint=models.CheckConstraint(condition=models.Q(models.Q(("published_at__isnull", False), ("searchable_slot", True), ("status", "PUBLISHED")), models.Q(models.Q(("status", "PUBLISHED"), _negated=True), ("searchable_slot__isnull", True)), _connector="OR"), name="copilot_generation_publication_matches")),
        migrations.AddIndex(model_name="retrievalindexgeneration", index=models.Index(fields=["status", "document"], name="copilot_generation_status_idx")),
        migrations.AddConstraint(model_name="retrievalindexjob", constraint=models.UniqueConstraint(fields=("document_version", "nonterminal_slot"), name="copilot_one_active_index_job")),
        migrations.AddConstraint(model_name="retrievalindexjob", constraint=models.CheckConstraint(condition=models.Q(("attempt_count__lte", 3)), name="copilot_index_attempt_limit")),
        migrations.AddConstraint(model_name="retrievalindexjob", constraint=models.CheckConstraint(condition=models.Q(models.Q(("nonterminal_slot", True), ("state__in", ("PENDING", "RUNNING", "RETRY_WAIT"))), models.Q(("nonterminal_slot__isnull", True), ("state__in", ("SUCCEEDED", "FAILED", "CANCELLED"))), _connector="OR"), name="copilot_index_slot_matches_state")),
        migrations.AddConstraint(model_name="retrievalindexjob", constraint=models.CheckConstraint(condition=models.Q(models.Q(("heartbeat_at__isnull", False), ("lease_expires_at__isnull", False), ("lease_owner__isnull", False), ("state", "RUNNING")), models.Q(models.Q(("state", "RUNNING"), _negated=True), ("heartbeat_at__isnull", True), ("lease_expires_at__isnull", True), ("lease_owner__isnull", True)), _connector="OR"), name="copilot_index_lease_matches_state")),
        migrations.AddIndex(model_name="retrievalindexjob", index=models.Index(fields=["state", "available_at"], name="copilot_index_claim_idx")),
        migrations.AddConstraint(model_name="retrievalchunk", constraint=models.UniqueConstraint(fields=("generation", "ordinal"), name="copilot_chunk_ordinal_unique")),
        migrations.AddConstraint(model_name="retrievalchunk", constraint=models.CheckConstraint(condition=models.Q(("token_count__gt", 0)), name="copilot_chunk_tokens_positive")),
        migrations.AddConstraint(model_name="retrievalchunk", constraint=models.CheckConstraint(condition=models.Q(("character_count__gt", 0)), name="copilot_chunk_chars_positive")),
        migrations.AddIndex(model_name="retrievalchunk", index=models.Index(fields=["document", "document_version", "ordinal"], name="copilot_chunk_document_idx")),
    ]
