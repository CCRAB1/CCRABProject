from django.db import migrations


MOVE_TABLES_SQL = """
CREATE SCHEMA IF NOT EXISTS platforms;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'collection',
        'collection_type',
        'data_source',
        'm_scalar_type',
        'm_type',
        'multi_obs',
        'obs_type',
        'organization',
        'platform',
        'platform_images',
        'platform_metadata',
        'platform_source',
        'platform_status',
        'platform_type',
        'product_type',
        'sample',
        'sample_answer',
        'sample_attachment',
        'sensor',
        'sensor_status',
        'source_observation_map',
        'timestamp_lkp',
        'uom_type'
    ]
    LOOP
        IF to_regclass(format('django.%I', table_name)) IS NOT NULL
           AND to_regclass(format('platforms.%I', table_name)) IS NULL THEN
            EXECUTE format('ALTER TABLE django.%I SET SCHEMA platforms', table_name);
        END IF;
    END LOOP;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=MOVE_TABLES_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
