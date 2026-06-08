from django.db import migrations


MOVE_TABLES_SQL = """
CREATE SCHEMA IF NOT EXISTS projects;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'hosting_location_product_types',
        'hosting_locations',
        'product_category',
        'product_types',
        'project_catalog_pages',
        'project_partners',
        'project_pictures'
    ]
    LOOP
        IF to_regclass(format('django.%I', table_name)) IS NOT NULL
           AND to_regclass(format('projects.%I', table_name)) IS NULL THEN
            EXECUTE format('ALTER TABLE django.%I SET SCHEMA projects', table_name);
        END IF;
    END LOOP;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("projects_catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=MOVE_TABLES_SQL, reverse_sql=migrations.RunSQL.noop),
    ]
