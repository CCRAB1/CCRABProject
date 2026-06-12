import logging
from datetime import datetime

from sqlalchemy import MetaData, create_engine, exc, func
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from typing import Any, Dict, Optional, Type

from .xenia_alchemy import xenia_alchemy
from .xenia_obs_map import ObsMap

class XeniaUtilityException(Exception):
    pass

from .XeniaTables import (
    organization,
    platform
)

logger = logging.getLogger(__name__
                           )
def check_organization(organizationRec: organization, db: xenia_alchemy) -> organization:
    org_id = db.organization_exists(organizationRec.short_name)
    if org_id is None:
        try:
            db.session.add(organizationRec)
            db.session.commit()
            org_id = organizationRec.row_id
        # Trying to add record that already exists.
        except exc.IntegrityError as e:
            db.session.rollback()
            raise e
    return org_id

def build_platform(        platformRec: platform,
                           observation_list: ObsMap,
                           db: xenia_alchemy):

    if db.platform_exists(platformRec.platform_handle) is None:
        logger.info(f"Adding platform handle: {platformRec.platform_handle}")
        try:
            db.session.add(platformRec)
            db.session.commit()
        # Trying to add record that already exists.
        except exc.IntegrityError as e:
            db.session.rollback()
            raise e

    for obs_info in observation_list:
        try:
            #Check to see if the sensor already exists, if it doesn't we'll try and create it.
            sensor_id = db.sensor_exists(obs_info.target_obs,
                                         obs_info.target_uom,
                                         platformRec.platform_handle,
                                         obs_info.s_order)
            if sensor_id is None:
                if db.add_new_sensor(obs_info.target_obs, obs_info.obs_description,
                                       obs_info.target_uom, obs_info.uom_description,
                                       platformRec.platform_handle,
                                       1,
                                       0,
                                       obs_info.s_order,
                                       None,
                                       True) is None:
                    raise Exception(f"Error platform: {platformRec.platform_handle} sensor: obs_info.target_obs"
                                      f"({obs_info.target_uom}) not added")
                else:
                    logger.info(
                        "Platform: %s added sensor: %s(%s)" % (platformRec.platform_handle,
                                                               obs_info.target_obs,
                                                                obs_info.target_uom))

            m_type = db.m_type_exists(obs_info.target_obs, obs_info.target_uom)
            obs_info.m_type_id = m_type
            sensor_id = db.sensor_exists(obs_info.target_obs,
                                         obs_info.target_uom,
                                         platformRec.platform_handle,
                                         obs_info.s_order)
            obs_info.sensor_id = sensor_id


        except Exception as e:
            raise e

def check_platform(organization_rec: organization,
                           platform_rec: platform,
                           observation_list: ObsMap,
                           db: xenia_alchemy) -> platform:
    row_entry_date = datetime.now()
    organization_rec.row_entry_date = row_entry_date
    #Make sure the organization exists, if it doesn't we add it.
    org_id = check_organization(organization_rec, db)
    platform_rec.row_entry_date = row_entry_date
    platform_rec.organization_id = org_id
    #Check if the platform exists, if it doesn't we add it and the observations associated with it.
    build_platform(platform_rec, observation_list, db)


