import logging
from observationsdatabase.xenia_alchemy import xenia_alchemy, build_pg_connection_string
#from observationsdatabase.xenia_obs_map import Organization, Platform, ObsMap
from observationsdatabase.xenia_utility_functions import check_platform
from observationsdatabase.XeniaTables import platform, organization

logger = logging.getLogger(__name__)

def connect_to_database(db_host: str, db_user: str, db_password: str, db_name: str) -> xenia_alchemy:
    if None not in (db_user, db_password, db_host, db_name):
        # Connect to the database
        xenia_db = xenia_alchemy()
        # build_pg_connection_string(username: str, password: str, host: str, database: str, port: int=5432) -> URL:
        connection_str = build_pg_connection_string(db_user,
                                                    db_password,
                                                    db_host,
                                                    db_name,
                                                    5432)
        logger.info(f"Connecting to database: {db_name}")
        xenia_db.connect_db(connection_str)
        return xenia_db
    else:
        raise Exception("Database airflow variables not set, cannot connect to database.")


def validate_organization(platform_handle: str, organizations_setup: [], db: xenia_alchemy) -> None:
    for organization_nfo in organizations_setup:
        platform_nfo = organization_nfo.get_platform(platform_handle)
        OrgRec = organization(short_name=organization_nfo.short_name,
                              long_name=organization_nfo.long_name)
        platformRec = platform(platform_handle=platform_handle,
                               short_name=platform_nfo.short_name,
                               long_name=platform_nfo.long_name,
                               fixed_latitude=platform_nfo.latitude,
                               fixed_longitude=platform_nfo.longitude)

        check_platform(OrgRec, platformRec, platform_nfo.obs_map, db)

    return
