from django.db import migrations, models


def seed_maintenance_guard(apps, schema_editor):
    guard = apps.get_model("vault", "VaultMaintenanceGuard")
    guard.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("vault", "0004_vaultbackupset_vaultmaintenanceconfirmation_and_more")]

    operations = [
        migrations.AddField(
            model_name="vaultmaintenanceconfirmation",
            name="issued_by_operator_id",
            field=models.CharField(default="legacy-unattributed", editable=False, max_length=64),
            preserve_default=False,
        ),
        migrations.RunPython(seed_maintenance_guard, migrations.RunPython.noop),
    ]
