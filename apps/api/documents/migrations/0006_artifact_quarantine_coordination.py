from django.db import migrations, models


def create_guard(apps, schema_editor):
    apps.get_model("documents", "ArtifactPublicationGuard").objects.create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("documents", "0005_processing_job_state_constraints")]

    operations = [
        migrations.CreateModel(
            name="ArtifactPublicationGuard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="QuarantinedArtifact",
            fields=[
                ("storage_key", models.CharField(editable=False, max_length=255, primary_key=True, serialize=False)),
                ("quarantined_at", models.DateTimeField(auto_now_add=True, editable=False)),
            ],
        ),
        migrations.RunPython(create_guard, migrations.RunPython.noop),
    ]
