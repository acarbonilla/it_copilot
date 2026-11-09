from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("documents", "0006_artifact_quarantine_coordination")]

    operations = [
        migrations.CreateModel(
            name="DocumentRetrievalChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_version_id", models.UUIDField(blank=True, editable=False, null=True)),
                ("reason", models.CharField(editable=False, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("consumed_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retrieval_changes", to="documents.document")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddIndex(
            model_name="documentretrievalchange",
            index=models.Index(fields=["consumed_at", "id"], name="document_retrieval_outbox_idx"),
        ),
    ]
