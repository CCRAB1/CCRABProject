from django.db import migrations


def backfill_data_source_sensor_defaults(apps, schema_editor):
    DataSourceSensor = apps.get_model("platforms_app", "DataSourceSensor")
    PlatformSource = apps.get_model("platforms_app", "PlatformSource")
    Sensor = apps.get_model("platforms_app", "Sensor")
    database_alias = schema_editor.connection.alias

    defaults = []
    platform_sources = PlatformSource.objects.using(database_alias).exclude(
        data_source_id__isnull=True,
    ).exclude(platform_id__isnull=True)

    for platform_source in platform_sources.iterator():
        m_type_ids = (
            Sensor.objects.using(database_alias).filter(
                platform_id=platform_source.platform_id_id,
                m_type_id__isnull=False,
            )
            .values_list("m_type_id", flat=True)
            .distinct()
        )
        defaults.extend(
            DataSourceSensor(
                data_source_id_id=platform_source.data_source_id_id,
                m_type_id_id=m_type_id,
            )
            for m_type_id in m_type_ids
        )

    DataSourceSensor.objects.using(database_alias).bulk_create(
        defaults,
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("platforms_app", "0010_data_source_sensor"),
    ]

    operations = [
        migrations.RunPython(
            backfill_data_source_sensor_defaults,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
