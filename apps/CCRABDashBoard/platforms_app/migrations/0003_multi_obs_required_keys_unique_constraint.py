import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0002_move_existing_tables_to_platforms_schema"),
    ]

    operations = [
        migrations.AlterField(
            model_name="multi_obs",
            name="m_type_id",
            field=models.ForeignKey(
                db_column="m_type_id",
                on_delete=django.db.models.deletion.CASCADE,
                to="platforms_app.m_type",
            ),
        ),
        migrations.AlterField(
            model_name="multi_obs",
            name="sensor_id",
            field=models.ForeignKey(
                db_column="sensor_id",
                on_delete=django.db.models.deletion.CASCADE,
                to="platforms_app.sensor",
            ),
        ),
        migrations.AddConstraint(
            model_name="multi_obs",
            constraint=models.UniqueConstraint(
                fields=("m_date", "sensor_id", "m_type_id"),
                name="i_multi_obs",
            ),
        ),
    ]
