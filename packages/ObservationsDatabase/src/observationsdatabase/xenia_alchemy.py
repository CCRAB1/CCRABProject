"""

"""
import logging
from datetime import datetime

from sqlalchemy import MetaData, create_engine, exc, func
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from typing import Any, Dict, Optional, Type
from .xenia_obs_map import ObsMap


from .XeniaTables import (
    m_scalar_type,
    m_type,
    multi_obs,
    obs_type,
    organization,
    platform,
    platform_status,
    platform_type,
    sensor,
    sensor_status,
    uom_type,
)

logger = logging.getLogger(__name__
                           )

def build_pg_connection_string(username: str, password: str, host: str, database: str, port: int=5432) -> URL:
    connection_string = URL.create(
        "postgresql",
        username=username,
        password=password,
        host=host,
        database=database,
        port=port
    )
    return connection_string


class xenia_alchemy(object):
    def __init__(self):
        self.dbEngine = None
        self.metadata = None
        self.session = None
        self.connection = None
        self.logger = logger

    def connect_db(self, connection_string, print_sql = False):

      try:
          # Connect to the database
          self.dbEngine = create_engine(connection_string, echo=print_sql)

          # metadata object is used to keep information such as datatypes for our table's columns.
          self.metadata = MetaData()
          self.metadata.bind = self.dbEngine

          session = sessionmaker(bind=self.dbEngine)
          self.session = session()

          self.connection = self.dbEngine.connect()

          return True
      except exc.OperationalError as e:
          raise e
      except Exception as e:
          raise

    def disconnect(self):
        self.session.close()
        self.connection.close()
        self.dbEngine.dispose()

    def _get_or_create(self, model: Type,
                       unique_fields: Dict[str, Any],
                       defaults: Optional[Dict[str, Any]] = None):
        obj = self.session.query(model).filter_by(**unique_fields).one_or_none()
        if obj:
            return obj
        params = {**unique_fields}
        if defaults:
            params.update(defaults)
        obj = model(**params)
        self.session.add(obj)
        self.session.flush()
        return obj

    def ensure_platform_and_obs(self, platform_meta: {}, observation_list: []):
        unique = {'platform_handle': platform_meta.get('platform_handle')} if 'platform_handle' in platform_meta else {'name': platform_meta['name']}
        defaults = {k:v for k,v in platform_meta.items() if k not in unique}
        platform_rec =  self._get_or_create(platform, unique, defaults)

        return

    def build_minimal_platform(self, platform_metadata: {}, observation_list: ObsMap):
        platform_handle = platform_metadata['platform_handle']
        name_parts = platform_handle.split('.')
        org_id = self.organization_exists(name_parts[0])
        row_entry_date = datetime.now()
        if org_id is None:
            self.logger.error(f"Organization: {name_parts[0]} does not exist, create it first.")
            #self.logger.debug(f"Adding organization name: {name_parts[0]}")
            #org_id = self.add_organization(row_entry_date, name_parts[0])

        if self.platform_exists(platform_handle) is None:
            self.logger.debug(f"Adding platform handle: {platform_handle}")
            plat_rec = platform(row_entry_date=row_entry_date,
                                organization_id=org_id,
                                platform_handle=platform_handle,
                                short_name=platform_metadata['short_name'],
                                long_name=platform_metadata['long_name'],
                                active=1,
                                fixed_latitude=platform_metadata['latitude'],
                                fixed_longitude=platform_metadata['longitude'])
            self.add_rec(plat_rec, True)
        for obs_info in observation_list:

            self.logger.debug(
                "Platform: %s adding sensor: %s(%s)" % (platform_handle, obs_info.target_obs, obs_info.target_uom))
            try:
                if self.add_new_sensor(obs_info.target_obs, obs_info.obs_description,
                                       obs_info.target_uom, obs_info.uom_description,
                                       platform_handle,
                                       1,
                                       0,
                                       obs_info.s_order,
                                       None,
                                       True) is None:
                    self.logger.error(f"Error platform: {platform_handle} sensor: {obs_info['target_obs']}"
                                      f"({obs_info['target_uom']}) not added")
            except Exception as e:
                self.logger.exception(e)

    """
    Function: platformExists  
    """


    def platform_exists(self, platform_handle):
        try:
            plat_rec = self.session.query(platform.row_id) \
                .filter(platform.platform_handle == platform_handle) \
                .one()
            return plat_rec.row_id
        except NoResultFound as e:
            self.logger.debug(e)
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return None


    """
    Function: addPlatform
    Purpose: Adds a new platform into the platform table.
    Parameters: 
      platformInfo is a dictionary keyed on the column names of the table. The only required key/values are:
        organization_id is the associated organization id.
        platform_handle is the handle for the platform.
      Optional columns are:
        type_id         
        short_name      
        fixed_longitude 
        fixed_latitude  
        active          
        begin_date      
        end_date        
        project_id      
        app_catalog_id  
        long_name       
        description     
        url             
        metadata_id     
    Returns:
      The row_id if it exists, -1 if it does not exists, or None if an error occurred. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def new_platform(self, row_entry_date, platform_handle, fixed_longitude, fixed_latitude, active=1, url="", description=""):
        platform_rec = None
        platform_handle_parts = platform_handle.split('.')
        # Check to make sure the organization exists:
        org_id = self.organization_exists(platform_handle_parts[0])
        if org_id is None:
            self.logger.debug("Organization: %s does not exist. Adding." % (platform_handle_parts[0]))
            org_id = self.add_organization(row_entry_date, platform_handle_parts[0])
            if org_id is None:
                self.logger.error("Could not add organization, cannot continue adding platform.")
                return None
        """    
        #Get platform type id.
        platTypeId = self.platformTypeExists(platformHandleParts[2])
        if(platTypeId is None):
          if(self.logger):
            self.logger.error("Platform type: %s does not exist." % (platformHandleParts[2]))
        """
        try:
            platform_rec = platform(row_entry_date=row_entry_date,
                                   organization_id=org_id,
                                   short_name=platform_handle_parts[1],
                                   platform_handle=platform_handle,
                                   fixed_longitude=fixed_longitude,
                                   fixed_latitude=fixed_latitude,
                                   active=active,
                                   url=url,
                                   description=description)

            self.add_rec(platform_rec, True)
            self.logger.debug("Platform: %s(%d) added to database." % (platform_rec.platform_handle, platform_rec.row_id))
        except Exception as e:
            self.logger.exception(e)

        return platform_rec.row_id


    """
    Function: addOrganization
    """


    def add_organization(self, row_entry_date, organization_name, active=1, long_name="", description="", url=""):
        org_rec = organization(row_entry_date=row_entry_date,
                              short_name=organization_name,
                              active=active,
                              long_name=long_name,
                              description=description,
                              url=url)
        row_id = self.add_rec(org_rec, True)
        return row_id


    """
    Function: organizationExists
    """


    def organization_exists(self, organization_name):
        try:
            org_rec = self.session.query(organization.row_id) \
                .filter(func.lower(organization.short_name) == func.lower(organization_name)) \
                .one()
            return org_rec.row_id
        except NoResultFound as e:
              self.logger.debug(e)
        except exc.InvalidRequestError as e:
              self.logger.exception(e)
        return None


    """
    Function: sensorExists
    Purpose: Checks to see if the passed in obsName on the platform.
    Parameters: 
      obsName is the sensor(observation) we are testing for.
      platform is the platform on which we search for the obsName.
      sOrder, if provided specifies the specific sensor if there are multiples of the same on a platform.
    Returns:
      The sensor id(row_id) if it exists, -1 if it does not exists, or None if an error occurred. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def sensor_exists(self, obs_name, uom, platform_handle, s_order=1):
        try:

            rec = self.session.query(sensor.row_id) \
                .join(platform, platform.row_id == sensor.platform_id) \
                .join(m_type, m_type.row_id == sensor.m_type_id) \
                .join(m_scalar_type, m_scalar_type.row_id == m_type.m_scalar_type_id) \
                .join(obs_type, obs_type.row_id == m_scalar_type.obs_type_id) \
                .join(uom_type, uom_type.row_id == m_scalar_type.uom_type_id) \
                .filter(sensor.s_order == s_order) \
                .filter(platform.platform_handle == platform_handle) \
                .filter(obs_type.standard_name == obs_name) \
                .filter(uom_type.standard_name == uom).one()
            return rec.row_id
        except NoResultFound as e:
            self.logger.debug(e)
        except exc.InvalidRequestError as e:
            self.logger.exception(e)

        return None


    def new_sensor(self, row_entry_date, obs_name, uom, platform_id, active=1, fixed_z=0, s_order=1, m_type_id=None,
                   add_obs_and_uom=False):
        self.logger.debug(f"Adding sensor: {obs_name}({uom}) sOrder: {s_order} on platform: {platform_id}")
        sensor_id = None
        if m_type_id is None:
            m_type_id = self.m_type_exists(obs_name, uom)
            if m_type_id is None:
                # If we want to add the obs type and uom type, we have to add them to add to tables: obs_type, uom_type, m_scalar_type
                # before we can add the m_type.
                if add_obs_and_uom:
                    # Does obs_type exist? If not, we attempt to add.
                    obs_id = self.obs_type_exists(obs_name)
                    if obs_id is None:
                        # Add the obs to the obs_type table.
                        obs_id = self.add_obs_type(obs_name)
                        # Cannot continue if we were unable to add.
                        if obs_id is None:
                            return None

                    # Does the uom type exist? If not, we attempt to add.
                    uom_id = self.uom_type_exists(uom)
                    if uom_id is None:
                        uom_id = self.add_uom_type(uom)
                        # Cannot continue if we were unable to add.
                        if uom_id is None:
                            return None

                    # Does the scalar_id exist?
                    m_scalar_id = self.scalar_type_exists(obs_id, uom_id)
                    if m_scalar_id is None:
                        m_scalar_id = self.add_scalar_type(obs_id, uom_id)
                        if m_scalar_id is None:
                            return None

                    # Now we can add the m_type
                    m_type_id = self.add_m_type(m_scalar_id)
                    if m_type_id is None:
                        return None
                else:
                    self.logger.error(
                        f"m_type does not exist, cannot add sensor: {obs_name}({uom}) platform: {platform_id}")
                    return None

            sensor_rec = sensor(row_entry_date=row_entry_date,
                               platform_id=platform_id,
                               m_type_id=m_type_id,
                               short_name=obs_name,
                               fixed_z=fixed_z,
                               active=active,
                               s_order=s_order)
            sensor_id = self.add_rec(sensor_rec, True)
            if sensor_id is None:
                  self.logger.error(f"Unable to add sensor: {obs_name}({uom}).")
            else:
                  self.logger.debug(
                      f"Added sensor: {obs_name}({uom}) sOrder: {s_order} on platform: {platform_id}")
        return sensor_id


    """
    Function: mTypeExists
    Purpose: Checks to see if the passed in obsName with the given units of measurement exists in the m_type table.
    Parameters: 
      obsName is the sensor(observation) we are testing for.
    Returns:
      The m_type id(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def m_type_exists(self, obs_name, uom):
        try:
            rec = self.session.query(m_type.row_id) \
                .join(m_scalar_type, m_scalar_type.row_id == m_type.m_scalar_type_id) \
                .join(obs_type, obs_type.row_id == m_scalar_type.obs_type_id) \
                .join(uom_type, uom_type.row_id == m_scalar_type.uom_type_id) \
                .filter(obs_type.standard_name == obs_name) \
                .filter(uom_type.standard_name == uom).one()
            return rec.row_id
        except NoResultFound:
            self.logger.debug(f"m_type {obs_name}({uom}) does not exist.")
        except exc.InvalidRequestError as e:
            self.logger.exception(e)

        return None


    """
    Function: addMType
    Purpose: Adds a new m_type into the m_type table. This function is not
    "user friendly" since it requires knowledge of the obs type id and uom type id. Most likely you wouldn't call this directly
    but would be using the addSensor function to do it automagically.
    Parameters: 
      scalarID is the row_id of the scalar_type to add.
    Returns:
      The m_type_id(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def add_m_type(self, scalar_id, description=""):
        row_id = None
        # At the moment the row_id columns are not autoincrement, so we need to get the max value first.
        try:
            next_row_id = self.session.query(func.max(m_type.row_id)).one()[0]
            if next_row_id is None:
                next_row_id = 0
            next_row_id += 1
        except Exception as e:
            self.logger.exception(e)
        else:
            m_type_rec = m_type(row_id=next_row_id, num_types=1, m_scalar_type_id=scalar_id, description=description)
            row_id = self.add_rec(m_type_rec, True)
            if row_id is None:
                self.logger.error("Unable to add scalarID: %d to m_type table." % (scalar_id))
            else:
                self.logger.debug("Added scalarID: %d to m_type table." % (scalar_id))
        return row_id


    """
    Function: obsTypeExists
    Purpose: Checks to see if the passed in obsName exists in the obs_type table.
    Parameters: 
      obsName is the sensor(observation) we are testing for.
    Returns:
      The obs_type(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def obs_type_exists(self, obs_name):
        row_id = None
        try:
            rec = self.session.query(obs_type.row_id) \
                .filter(obs_type.standard_name == obs_name) \
                .one()
            row_id = rec.row_id
        except NoResultFound:
            self.logger.debug("Observation: %s does not exist in obs_type table." % (obs_name))
        except exc.InvalidRequestError as e:
            self.logger.exception(e)

        return row_id


    """
    Function: addObsType
    Purpose: Adds the given obsName into the obs_type table.
      obsName is the sensor(observation) we are adding.
    Returns:
      The obs_type(row_id) if it is successfully created, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def add_obs_type(self, obs_name):
        row_id = None
        # At the moment the row_id columns are not autoincrement, so we need to get the max value first.
        try:
            nextrow_id = self.session.query(func.max(obs_type.row_id)).one()[0]
            if nextrow_id is None:
                nextrow_id = 0
            nextrow_id += 1
        except Exception as e:
            if (self.logger):
                self.logger.exception(e)
        else:
            obs_type_rec = obs_type(row_id=nextrow_id, standard_name=obs_name)
            row_id = self.add_rec(obs_type_rec, True)
            if row_id is None:
                self.logger.error("Unable to add obs: %s to obs_type table." % (obs_name))
            else:
                self.logger.debug("Added obs: %s to obs_type table." % (obs_name))
        return row_id


    """
    Function: uomTypeExists
    Purpose: Checks to see if the passed in uomName exists in the uom_type table.
    Parameters: 
      uomName is the unit of measurement  we are testing for.
    Returns:
      The uom_type(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def uom_type_exists(self, uom_name):
        row_id = None
        try:
            rec = self.session.query(uom_type.row_id) \
                .filter(uom_type.standard_name == uom_name) \
                .one()
            row_id = rec.row_id
        except NoResultFound:
            self.logger.debug("UOM: %s does not exist in obs_type table." % (uom_name))
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return row_id


    """
    Function: addUOMType
    Purpose: Adds the given obsName into the obs_type table.
      obsName is the sensor(observation) we are adding.
    Returns:
      The uom_type(row_id) if it is successfully created, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def add_uom_type(self, uom_name):
        row_id = None
        # At the moment the row_id columns are not autoincrement, so we need to get the max value first.
        try:
            nextrow_id = self.session.query(func.max(uom_type.row_id)).one()[0]
            if nextrow_id is None:
                nextrow_id = 0
            nextrow_id += 1
        except Exception as e:
            if (self.logger):
                self.logger.exception(e)
        else:
            uom_type_rec = uom_type(row_id=nextrow_id, standard_name=uom_name)
            row_id = self.add_rec(uom_type_rec, True)
            if row_id is None:
                self.logger.error("Unable to add uom: %s to uom_type table." % (uom_name))
            else:
                self.logger.debug("Added uom: %s to obs_type table." % (uom_name))
        return row_id


    """
    Function: existsScalarType
    Purpose: Checks to see if the passed in obsTypeID and uomTypeID exists in the scalar_type table. This function is not
    "user friendly" since it requires knowledge of the obs type id and uom type id. Most likely you wouldn't call this directly
    but would be using the addSensor function to do it automagically.
    Parameters: 
      obsTypeID is the row_id of the observation from the obs_type table to check.
      uomTypeID is the row_id of the unit of measure from the uom_type table to check.
    Returns:
      The m_scalar_type_id(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def scalar_type_exists(self, obs_type_id, uom_type_id):
        row_id = None
        try:
            rec = self.session.query(m_scalar_type.row_id) \
                .filter(m_scalar_type.obs_type_id == obs_type_id) \
                .filter(m_scalar_type.uom_type_id == uom_type_id) \
                .one()
            row_id = rec.row_id
        except NoResultFound:
            self.logger.debug(
                "Scalar type for obs_type_id: %d uom_type_id: %d does not exist in m_scalar_type table." % (
                    obs_type_id, uom_type_id))
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return row_id


    """
    Function: addScalarType
    Purpose: Adds a new scalar type into the scalar_type table. This function is not
    "user friendly" since it requires knowledge of the obs type id and uom type id. Most likely you wouldn't call this directly
    but would be using the addSensor function to do it automagically.
    Parameters: 
      obsTypeID is the row_id of the observation from the obs_type table to add.
      uomTypeID is the row_id of the unit of measure from the uom_type table.
    Returns:
      The m_scalar_type_id(row_id) if it exists, -1 if it does not exists, or None if an error occured. If there was an error
      lastErrorMsg can be checked for the error message.
    """


    def add_scalar_type(self, obs_type_id, uom_type_id):
        row_id = None
        # At the moment the row_id columns are not autoincrement, so we need to get the max value first.
        try:
            nextrow_id = self.session.query(func.max(m_scalar_type.row_id)).one()[0]
            if nextrow_id is None:
                nextrow_id = 0
            nextrow_id += 1
        except Exception as e:
            self.logger.exception(e)
        else:
            scalar_rec = m_scalar_type(row_id=nextrow_id, obs_type_id=obs_type_id, uom_type_id=uom_type_id)
            row_id = self.add_rec(scalar_rec, True)
            if row_id is None:
                self.logger.error(
                    "Unable to add m_scalar_type: obs_type_id: %d  uom_type_id: %d to m_scalar_type table." % (
                        obs_type_id, uom_type_id))
            else:
                self.logger.debug("Added m_scalar_type: obs_type_id: %d  uom_type_id: %d to m_scalar_type table." % (
                    obs_type_id, uom_type_id))
        return row_id


    def get_current_platform_status(self, platform_handle):
        try:
            rec = self.session.query(sensor_status.status) \
                .filter(platform_status.platform_handle == platform_handle).one()
            return rec.status
        except NoResultFound as e:
            self.logger.debug(e)
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return None


    def get_current_sensor_status(self, obs_name, platform_handle):
        try:
            rec = self.session.query(platform_status.status) \
                .filter(platform.platform_handle == platform_handle) \
                .filter(sensor_status.sensor_name == obs_name).one()
            return rec.status
        except NoResultFound as e:
            self.logger.debug(e)
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return None


    def platform_type_exists(self, platform_type):
        try:
            plat_rec = self.session.query(platform_type.row_id) \
                .filter(platform_type.type_name == platform_type) \
                .one()
            return plat_rec.row_id
        except NoResultFound as e:
            self.logger.debug(e)
        except exc.InvalidRequestError as e:
            self.logger.exception(e)
        return None


    def add_platform_type(self, type_name, description="", commit=False):
        plat_type = None
        try:
            plat_type = platform_type(type_name, description)
            self.session.add(plat_type)
            if commit:
                self.session.commit()
        # Trying to add record that already exists.
        except exc.IntegrityError as e:
            self.session.rollback()
            self.logger.exception(e)
        return plat_type


    def add_rec(self, rec, commit=False):
        try:
            self.session.add(rec)
            if commit:
                self.session.commit()
            return rec.row_id
        # Trying to add record that already exists.
        except exc.IntegrityError as e:
            self.session.rollback()
            raise e


    def add_or_update_record(self, rec, update_if_exists=True, commit=False):
        row_id = None
        try:
            self.session.add(rec)
            if (commit):
                self.session.commit()
            row_id = rec.row_id

        # Trying to add record that already exists.
        except exc.IntegrityError:
            self.session.rollback()
            if update_if_exists:
                self.logger.info("Record already exists, updating it.")
                try:
                    # Pull the record from the DB
                    current_rec = self.session.query(multi_obs) \
                        .where(multi_obs.m_date == rec.m_date) \
                        .where(multi_obs.platform_handle == rec.platform_handle) \
                        .one()
                    current_rec.m_value = rec.m_value
                    self.session.commit()
                    row_id = current_rec.row_id

                except Exception as e:
                    self.session.rollback()
                    self.logger.exception(e)
            else:
                self.logger.warning("Record already exists.")
        return row_id


    def add_platform(self, platform_rec, commit=False):
        return self.add_rec(platform_rec, commit)


    def add_sensor(self, sensor_rec, commit=False):
        return self.add_rec(sensor_rec, commit)

    def add_new_sensor(self, obs_name, obs_description,
                       uom, uom_description,
                       platform_handle,
                       active=1,
                       fixed_z=0,
                       s_order=1,
                       m_type_id=None,
                       add_obs_and_uom=False):
        # If the sensor already exists, we're done.
        id = self.sensor_exists(obs_name, uom, platform_handle, s_order)
        if id is not None:
            return id

        row_entry_date = datetime.now()
        # If the mTypeID is passed in, we already have a complete set of obs ids, uoms, scalar types.
        if m_type_id is None:
            obs_type_id = self.obs_type_exists(obs_name)
            if obs_type_id is None:
                if add_obs_and_uom:
                    obs_type_id = self.add_obs_type(obs_name)
                    # Error occured so return.
                    if obs_type_id is None:
                        raise Exception("Unable to add obs_type: %s" % (obs_name))
                # If we do not want to add a missing observation type, we must error out.
                else:
                    raise Exception("obs_type: %s does not exist. Must be added to obs_type table." % (obs_name))
            elif obs_type_id is None:
                raise Exception("obs_type.standard_name: %s does not exist." % (obs_name))

            # Now let's check if our UOM exists.
            uom_type_id = self.uom_type_exists(uom)
            if uom_type_id is None:
                if add_obs_and_uom:
                    uom_type_id = self.add_uom_type(uom)
                    # Error occured so return.
                    if uom_type_id is None:
                        raise Exception("Unable to add uom_type: %s" % (uom))
                # If we do not want to add a missing uom type, we must error out.
                else:
                    raise Exception("uom_type: %s does not exist. Must be added to uom_type table." % (uom))
            elif uom_type_id is None:
                raise Exception("uom_type.standard_name: %s does not exist." % (uom))

            # Now check the scalar type.
            scalar_id = self.scalar_type_exists(obs_type_id, uom_type_id)
            if scalar_id is None:
                scalar_id = self.add_scalar_type(obs_type_id, uom_type_id)
                # Error occured so return.
                if scalar_id is None:
                    raise Exception("Unable to add scalar_type with obs_type_id: %d and uom_type_id: %d" % (
                        scalar_id, uom_type_id))
            elif scalar_id is None:
                return None

            # Now we need to add a new m_type
            m_type_id = self.m_type_exists(obs_name, uom)
            if m_type_id is None:
                m_type_id = self.add_m_type(scalar_id)
                # Error occured so return.
                if m_type_id is None:
                    raise Exception("Unable to add m_type with scalar_type_id: %d" % (scalar_id))
            elif m_type_id is None:
                return None

        # Now we can finally add the sensor to the sensor table.
        platform_id = self.platform_exists(platform_handle)
        if platform_id is not None:
            sensor_rec = sensor(row_entry_date=row_entry_date,
                                platform_id=platform_id,
                                m_type_id=m_type_id,
                                short_name=obs_name,
                                fixed_z=fixed_z,
                                active=active,
                                s_order=s_order)
            sensor_id = self.add_rec(sensor_rec, True)
            if sensor_id is not None:
                self.logger.debug("Added sensor: %s(%s) sOrder: %d on platform: %d" % (obs_name, uom, s_order, platform_id))
                return sensor_id
            else:
                raise Exception("Unable to add sensor: %s(%s)." % (obs_name, uom))


        else:
            raise Exception("Platform: %s does not exist. Cannot add sensor." % (platform_handle))
    '''
    def calcAvgWindSpeedAndDir(self, platName, wind_speed_obsname, wind_speed_uom, wind_dir_obsname, wind_dir_uom,
                               start_date, end_date):
        wind_components = []
        dir_components = []
        vect_obj = vectorMagDir()
        spd_avg = dir_avg = scalar_spd_avg = vectordir_avg = None
        # Get the wind speed and direction so we can correctly average the data.
        # Get the sensor ID for the obs we are interested in so we can use it to query the data.
        # windSpdId = xeniaSQLite.sensorExists(self, wind_speed_obsname, wind_speed_uom, platName)
        # windDirId = xeniaSQLite.sensorExists(self, wind_dir_obsname, wind_dir_uom, platName)
        m_wind_speed_id = self.sensorExists(wind_speed_obsname, wind_speed_uom, platName)
        m_wind_dir_id = self.sensorExists(wind_dir_obsname, wind_dir_uom, platName)
        if m_wind_speed_id is not None and \
                m_wind_dir_id is not None:

            try:
                wnd_spd_recs = self.session.query(multi_obs) \
                    .filter(multi_obs.sensor_id == m_wind_speed_id) \
                    .filter(multi_obs.m_date >= start_date) \
                    .filter(multi_obs.m_date < end_date) \
                    .order_by(multi_obs.m_date) \
                    .all()
                wnd_dir_recs = self.session.query(multi_obs) \
                    .filter(multi_obs.sensor_id == m_wind_dir_id) \
                    .filter(multi_obs.m_date >= start_date) \
                    .filter(multi_obs.m_date < end_date) \
                    .order_by(multi_obs.m_date) \
                    .all()
            except Exception as e:
                self.logger.exception(e)
            else:
                scalar_spd = None
                spd_cnt = 0
                for spd_row in wnd_spd_recs:
                    if scalar_spd is None:
                        scalar_spd = 0
                    scalar_spd += spd_row.m_value
                    spd_cnt += 1
                    for dir_row in wnd_dir_recs:
                        if spd_row.m_date == dir_row.m_date:
                            self.logger.debug("Calculating vector for Speed(%s): %f Dir(%s): %f" % (
                            spd_row.m_date, spd_row.m_value, dir_row.m_date, dir_row.m_value))
                            # Vector using both speed and direction.
                            wind_components.append(vect_obj.calcVector(spd_row.m_value, dir_row.m_value))
                            # VEctor with speed as constant(1), and direction.
                            dir_components.append(vect_obj.calcVector(1, dir_row.m_value))
                            break
                # Get our average on the east and north components of the wind vector.
                spd_avg = None
                dir_avg = None
                scalar_spd_avg = None
                vectordir_avg = None

                # If we have the direction only components, this is unity speed with wind direction, calc the averages.
                if len(dir_components):
                    east_comp_avg = 0
                    north_comp_avg = 0
                    scalar_spd_avg = scalar_spd / spd_cnt

                    for vectorTuple in dir_components:
                        east_comp_avg += vectorTuple[0]
                        north_comp_avg += vectorTuple[1]

                    east_comp_avg = east_comp_avg / len(dir_components)
                    north_comp_avg = north_comp_avg / len(dir_components)
                    spd_avg, vectordir_avg = vect_obj.calcMagAndDir(east_comp_avg, north_comp_avg)
                    self.logger.debug(
                        "Platform: %s Scalar Speed Avg: %f Vector Dir Avg: %f" % (platName, scalar_spd_avg, vectordir_avg))

                # 2013-11-21 DWR Add check to verify we have components. Also reset the east_comp_avg and north_comp_avg to 0
                # before doing calcs.
                # If we have speed and direction vectors, calc the averages.
                if len(wind_components):
                    east_comp_avg = 0
                    north_comp_avg = 0
                    for vectorTuple in wind_components:
                        east_comp_avg += vectorTuple[0]
                        north_comp_avg += vectorTuple[1]

                    east_comp_avg = east_comp_avg / len(wind_components)
                    north_comp_avg = north_comp_avg / len(wind_components)
                    # Calculate average with speed and direction components.
                    spd_avg, dir_avg = vect_obj.calcMagAndDir(east_comp_avg, north_comp_avg)
                    self.logger.debug("Platform: %s Vector Speed Avg: %f Vector Dir Avg: %f" % (platName, spd_avg, dir_avg))

        else:
            self.logger("Wind speed or wind direction id is not valid.")
        return (spd_avg, dir_avg), (scalar_spd_avg, vectordir_avg)
    '''

if __name__ == '__main__':
    xeniaDB = xenia_alchemy()
