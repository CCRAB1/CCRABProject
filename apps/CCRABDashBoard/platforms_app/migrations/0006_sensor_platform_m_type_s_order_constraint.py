from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0005_qualify_postgis_trigger_functions"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="sensor",
            constraint=models.UniqueConstraint(
                fields=("platform_id", "m_type_id", "s_order"),
                name="uq_sensor_platform_m_type_s_order",
            ),
        ),
    ]
