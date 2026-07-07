from django.db import migrations, models


MULTI_OBS_TABLE = '"platforms"."multi_obs"'


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("platforms_app", "0008_alter_platformsource_unique_together_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                        "i_multi_obs_platform_date "
                        f"ON {MULTI_OBS_TABLE} (platform_handle, m_date) "
                        "INCLUDE (sensor_id, m_value, m_lon, m_lat);"
                    ),
                    reverse_sql=(
                        'DROP INDEX CONCURRENTLY IF EXISTS '
                        '"platforms"."i_multi_obs_platform_date";'
                    ),
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="multi_obs",
                    index=models.Index(
                        fields=("platform_handle", "m_date"),
                        include=("sensor_id", "m_value", "m_lon", "m_lat"),
                        name="i_multi_obs_platform_date",
                    ),
                ),
            ],
        ),
    ]
