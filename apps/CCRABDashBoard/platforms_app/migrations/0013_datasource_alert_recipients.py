import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0012_data_freshness_monitoring"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasource",
            name="alert_recipients",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.EmailField(max_length=254),
                blank=True,
                default=list,
                help_text=(
                    "Email addresses that receive freshness alerts. Enter "
                    "addresses separated by commas."
                ),
                size=None,
            ),
        ),
    ]
