from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("vault", "0006_vaultpurgejournalscope_vaultrecoveryevidence")]

    operations = [
        migrations.AddField(
            model_name="vaultownerkey",
            name="kek_generation",
            field=models.PositiveIntegerField(default=1, editable=False),
            preserve_default=True,
        ),
        migrations.AddConstraint(
            model_name="vaultownerkey",
            constraint=models.CheckConstraint(
                condition=models.Q(kek_generation__gt=0),
                name="vault_owner_kek_generation_positive",
            ),
        ),
    ]
