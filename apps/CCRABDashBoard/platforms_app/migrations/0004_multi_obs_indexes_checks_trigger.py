from django.db import migrations, models


MULTI_OBS_TABLE = '"platforms"."multi_obs"'


ADD_MULTI_OBS_GEOM_SQL = f"""
CREATE OR REPLACE FUNCTION public.mk_the_geom() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW.the_geom IS NULL AND NEW.m_lon IS NOT NULL AND NEW.m_lat IS NOT NULL) THEN
        NEW.the_geom = ST_SetSRID(ST_MakePoint(NEW.m_lon, NEW.m_lat), 4326);
    END IF;
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'enforce_dims_the_geom'
          AND conrelid = '{MULTI_OBS_TABLE}'::regclass
    ) THEN
        ALTER TABLE {MULTI_OBS_TABLE}
        ADD CONSTRAINT enforce_dims_the_geom CHECK (ST_NDims(the_geom) = 2);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'enforce_geotype_the_geom'
          AND conrelid = '{MULTI_OBS_TABLE}'::regclass
    ) THEN
        ALTER TABLE {MULTI_OBS_TABLE}
        ADD CONSTRAINT enforce_geotype_the_geom
        CHECK (geometrytype(the_geom) = 'POINT'::text OR the_geom IS NULL);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'enforce_srid_the_geom'
          AND conrelid = '{MULTI_OBS_TABLE}'::regclass
    ) THEN
        ALTER TABLE {MULTI_OBS_TABLE}
        ADD CONSTRAINT enforce_srid_the_geom CHECK (st_srid(the_geom) = 4326);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'mk_the_geom'
          AND tgrelid = '{MULTI_OBS_TABLE}'::regclass
    ) THEN
        CREATE TRIGGER mk_the_geom
        BEFORE INSERT ON {MULTI_OBS_TABLE}
        FOR EACH ROW EXECUTE PROCEDURE public.mk_the_geom();
    END IF;
END $$;
"""


DROP_MULTI_OBS_GEOM_SQL = f"""
DROP TRIGGER IF EXISTS mk_the_geom ON {MULTI_OBS_TABLE};
ALTER TABLE {MULTI_OBS_TABLE} DROP CONSTRAINT IF EXISTS enforce_srid_the_geom;
ALTER TABLE {MULTI_OBS_TABLE} DROP CONSTRAINT IF EXISTS enforce_geotype_the_geom;
ALTER TABLE {MULTI_OBS_TABLE} DROP CONSTRAINT IF EXISTS enforce_dims_the_geom;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0003_multi_obs_required_keys_unique_constraint"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="multi_obs",
            name="i_multi_obs",
        ),
        migrations.AddConstraint(
            model_name="multi_obs",
            constraint=models.UniqueConstraint(
                fields=("m_date", "m_type_id", "sensor_id"),
                name="i_multi_obs",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        f"CREATE INDEX IF NOT EXISTS i_multi_obs_date_platform "
                        f"ON {MULTI_OBS_TABLE} (m_date, platform_handle);"
                    ),
                    reverse_sql=(
                        "DROP INDEX IF EXISTS platforms.i_multi_obs_date_platform;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="multi_obs",
                    index=models.Index(
                        fields=("m_date", "platform_handle"),
                        name="i_multi_obs_date_platform",
                    ),
                ),
            ],
        ),
        migrations.RunSQL(
            sql=ADD_MULTI_OBS_GEOM_SQL,
            reverse_sql=DROP_MULTI_OBS_GEOM_SQL,
        ),
    ]
