from django.db import migrations


FIX_MK_THE_GEOM_SQL = """
CREATE OR REPLACE FUNCTION public.mk_the_geom() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW.the_geom IS NULL AND NEW.m_lon IS NOT NULL AND NEW.m_lat IS NOT NULL) THEN
        NEW.the_geom = public.ST_SetSRID(public.ST_MakePoint(NEW.m_lon, NEW.m_lat), 4326);
    END IF;
    RETURN NEW;
END;
$$;
"""


RESTORE_MK_THE_GEOM_SQL = """
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platforms_app", "0004_multi_obs_indexes_checks_trigger"),
    ]

    operations = [
        migrations.RunSQL(
            sql=FIX_MK_THE_GEOM_SQL,
            reverse_sql=RESTORE_MK_THE_GEOM_SQL,
        ),
    ]
