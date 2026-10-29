from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0004_processing_metadata")]

    operations = [
        migrations.AddConstraint(
            model_name="processingjob",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        state="RUNNING",
                        lease_owner__isnull=False,
                        lease_expires_at__isnull=False,
                        heartbeat_at__isnull=False,
                    )
                    | (
                        ~models.Q(state="RUNNING")
                        & models.Q(lease_owner__isnull=True, lease_expires_at__isnull=True, heartbeat_at__isnull=True)
                    )
                ),
                name="processing_job_lease_matches_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="processingjob",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(state__in=("SUCCEEDED", "FAILED", "CANCELLED"), completed_at__isnull=False)
                    | (
                        ~models.Q(state__in=("SUCCEEDED", "FAILED", "CANCELLED"))
                        & models.Q(completed_at__isnull=True)
                    )
                ),
                name="processing_job_completion_matches_state",
            ),
        ),
    ]
