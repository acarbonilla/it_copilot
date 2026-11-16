from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("vault", "0005_vaultmaintenanceconfirmation_issued_by_operator_id")]

    operations = [
        migrations.CreateModel(
            name="VaultPurgeJournalScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expected_revision", models.PositiveBigIntegerField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("journal", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="purge_scopes", to="vault.vaultmaintenancejournal")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="vault_purge_journal_scopes", to=settings.AUTH_USER_MODEL)),
                ("record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name="purge_journal_scopes", to="vault.vaultrecord")),
            ],
            options={"indexes": [models.Index(fields=["owner", "record"], name="vault_purge_owner_record_idx")]},
        ),
        migrations.AddConstraint(model_name="vaultpurgejournalscope",
            constraint=models.UniqueConstraint(fields=("journal", "record"), name="vault_purge_scope_journal_record_unique")),
        migrations.AddConstraint(model_name="vaultpurgejournalscope",
            constraint=models.CheckConstraint(condition=models.Q(("expected_revision__gt", 0)), name="vault_purge_scope_revision_positive")),
        migrations.CreateModel(
            name="VaultRecoveryEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prepared_operation_id", models.UUIDField(editable=False, unique=True)),
                ("dry_run_id", models.UUIDField(editable=False)),
                ("parameter_digest", models.CharField(editable=False, max_length=64)),
                ("candidate_set_digest", models.CharField(editable=False, max_length=64)),
                ("owner_set_digest", models.CharField(editable=False, max_length=64)),
                ("evidence_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("backup_operator_id", models.CharField(editable=False, max_length=64)),
                ("verifier_operator_id", models.CharField(editable=False, max_length=64)),
                ("verification_policy_version", models.CharField(editable=False, max_length=32)),
                ("invalidation_generation", models.PositiveIntegerField(default=0, editable=False)),
                ("verified_at", models.DateTimeField(editable=False)),
                ("expires_at", models.DateTimeField(editable=False)),
                ("cleanup_complete", models.BooleanField(default=False, editable=False)),
                ("invalidated_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("failure_code", models.CharField(blank=True, editable=False, max_length=32, null=True)),
                ("backup_set", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name="recovery_evidence", to="vault.vaultbackupset")),
            ],
        ),
        migrations.AddConstraint(model_name="vaultrecoveryevidence",
            constraint=models.CheckConstraint(condition=models.Q(("expires_at__gt", models.F("verified_at"))), name="vault_recovery_evidence_expiry")),
        migrations.AddConstraint(model_name="vaultrecoveryevidence",
            constraint=models.CheckConstraint(condition=models.Q(("backup_operator_id", models.F("verifier_operator_id")), _negated=True), name="vault_recovery_operator_separation")),
    ]
