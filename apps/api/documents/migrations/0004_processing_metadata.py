from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("documents", "0003_originalartifact")]

    operations = [
        migrations.AddField(
            model_name="processingjob",
            name="last_error_code",
            field=models.CharField(blank=True, editable=False, max_length=32),
        ),
        migrations.AddField(
            model_name="processingjob",
            name="completed_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="extractedtextartifact",
            name="page_count",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
