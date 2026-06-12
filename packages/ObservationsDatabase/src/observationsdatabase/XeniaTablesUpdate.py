import logging.config

from geoalchemy2 import Geometry
from sqlalchemy import CHAR, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

logger = logging.getLogger(__name__)

Base = declarative_base()


class organization(Base):
    __tablename__ = 'organization'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    short_name = Column(String(50))
    active = Column(Integer)
    long_name = Column(String(200))
    description = Column(String(1000))
    url = Column(String(200))
    opendap_url = Column(String(200))
    email_tech = Column(String(150))


class collection_type(Base):
    __tablename__ = 'collection_type'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    type_name = Column(String)
    description = Column(String)


class collection_run(Base):
    __tablename__ = 'collection'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    type_id = Column(Integer, ForeignKey(collection_type.row_id))
    short_name = Column(String)
    long_name = Column(String)
    description = Column(String)
    fixed_date = Column(DateTime)
    min_date = Column(DateTime)
    max_date = Column(DateTime)
    fixed_lon = Column(Float)
    min_lon = Column(Float)
    max_lon = Column(Float)
    fixed_lat = Column(Float)
    min_lat = Column(Float)
    max_lat = Column(Float)
    fixed_z = Column(Float)
    min_z = Column(Float)
    max_z = Column(Float)


class platform_type(Base):
    __tablename__ = 'platform_type'
    row_id = Column(Integer, primary_key=True)
    type_name = Column(String(50))
    description = Column(String(1000))
    short_name = Column(String(50))

    def __init__(self, typeName, description, shortName):
        super().__init__()
        self.type_name = typeName
        self.description = description
        self.short_name = shortName

class platform_metadata(Base):
    __tablename__ = 'platform_metadata'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime(timezone=False))
    row_update_date = Column(DateTime(timezone=False))

    # Country
    country_code = Column(CHAR(2), nullable=False)   # ISO 3166-1 alpha-2
    country_name = Column(String(100))               # optional

    # Administrative levels
    admin_area_level_1 = Column(String(150))         # state/province/region
    admin_area_level_2 = Column(String(150))         # county/district
    admin_area_level_3 = Column(String(150))         # optional sub-division

    # City & Locality
    city = Column(String(150))
    neighborhood = Column(String(150))               # optional
    street_address = Column(String(255))             # e.g., "123 Main St"
    postal_code = Column(String(20))

    timezone = Column(String(50))

class platform(Base):
    __tablename__ = 'platform'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    organization_id = Column(Integer, ForeignKey(organization.row_id))
    type_id = Column(Integer, ForeignKey(platform_type.row_id))
    short_name = Column(String(50))
    platform_handle = Column(String(100))
    fixed_longitude = Column(Float)
    fixed_latitude = Column(Float)
    active = Column(Integer)
    begin_date = Column(DateTime(timezone=False))
    end_date = Column(DateTime(timezone=False))
    project_id = Column(Integer)
    app_catalog_id = Column(Integer)
    long_name = Column(String(200))
    description = Column(String(1000))
    url = Column(String(200))
    metadata_id = Column(Integer, ForeignKey(platform_metadata.row_id))
    # the_geom         = GeometryColumn(Point(2))
    the_geom = Column(Geometry('Point'))

    organization = relationship(organization)
    sensors = relationship("sensor", order_by="sensor.row_id", backref="platform")
    platform_type = relationship(platform_type)
    metadata_info = relationship(platform_metadata)

class uom_type(Base):
    __tablename__ = 'uom_type'
    row_id = Column(Integer, primary_key=True)
    standard_name = Column(String(50))
    definition = Column(String(1000))
    display = Column(String(50))


class obs_type(Base):
    __tablename__ = 'obs_type'
    row_id = Column(Integer, primary_key=True)
    standard_name = Column(String(50))
    definition = Column(String(1000))


class m_scalar_type(Base):
    __tablename__ = 'm_scalar_type'
    row_id = Column(Integer, primary_key=True)
    obs_type_id = Column(Integer, ForeignKey(obs_type.row_id))
    uom_type_id = Column(Integer, ForeignKey(uom_type.row_id))

    obs_type = relationship(obs_type)
    uom_type = relationship(uom_type)


class m_type(Base):
    __tablename__ = 'm_type'
    row_id = Column(Integer, primary_key=True)
    num_types = Column(Integer)
    description = Column(String(1000))
    m_scalar_type_id = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_2 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_3 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_4 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_5 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_6 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_7 = Column(Integer, ForeignKey(m_scalar_type.row_id))
    m_scalar_type_id_8 = Column(Integer, ForeignKey(m_scalar_type.row_id))

    # We have to declare the primaryjoin statement since we have multiple ForeignKeys that point
    # to the same relationship.
    scalar_type = relationship(m_scalar_type, primaryjoin=(m_scalar_type_id == m_scalar_type.row_id))


class sensor(Base):
    __tablename__ = 'sensor'
    row_id = Column(Integer, primary_key=True, autoincrement=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    platform_id = Column(Integer, ForeignKey(platform.row_id))
    type_id = Column(Integer)
    short_name = Column(String(50))
    m_type_id = Column(Integer, ForeignKey(m_type.row_id))
    fixed_z = Column(Float)
    active = Column(Integer)
    begin_date = Column(DateTime(timezone=False))
    end_date = Column(DateTime(timezone=False))
    s_order = Column(Integer)
    url = Column(String(200))
    metadata_id = Column(Integer)
    report_interval = Column(Integer)

    # platform = relationship(platform, backref=backref("sensors"))
    m_type = relationship(m_type)


class multi_obs(Base):
    __tablename__ = 'multi_obs'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime)
    row_update_date = Column(DateTime)
    platform_handle = Column(String(100))
    sensor_id = Column(Integer, ForeignKey(sensor.row_id))
    m_type_id = Column(Integer, ForeignKey(m_type.row_id))
    m_date = Column(DateTime(timezone=False))
    m_lon = Column(Float)
    m_lat = Column(Float)
    m_z = Column(Float)
    m_value = Column(Float)
    m_value_2 = Column(Float)
    m_value_3 = Column(Float)
    m_value_4 = Column(Float)
    m_value_5 = Column(Float)
    m_value_6 = Column(Float)
    m_value_7 = Column(Float)
    m_value_8 = Column(Float)
    qc_metadata_id = Column(Integer)
    qc_level = Column(Integer)
    qc_flag = Column(String(100))
    qc_metadata_id_2 = Column(Integer)
    qc_level_2 = Column(Integer)
    qc_flag_2 = Column(String(100))
    metadata_id = Column(Integer)
    d_label_theta = Column(Integer)
    d_top_of_hour = Column(Integer)
    d_report_hour = Column(DateTime(timezone=False))
    # the_geom         = GeometryColumn(Point(2))
    the_geom = Column(Geometry('Point'))

    m_type = relationship(m_type)
    sensor = relationship(sensor)

    def __init__(self,
                 row_id=None,
                 row_entry_date=None,
                 row_update_date=None,
                 platform_handle=None,
                 sensor_id=None,
                 m_type_id=None,
                 m_date=None,
                 m_lon=None,
                 m_lat=None,
                 m_z=None,
                 m_value=None,
                 m_value_2=None,
                 m_value_3=None,
                 m_value_4=None,
                 m_value_5=None,
                 m_value_6=None,
                 m_value_7=None,
                 m_value_8=None,
                 qc_metadata_id=None,
                 qc_level=None,
                 qc_flag=None,
                 qc_metadata_id_2=None,
                 qc_level_2=None,
                 qc_flag_2=None,
                 metadata_id=None,
                 d_label_theta=None,
                 d_top_of_hour=None,
                 d_report_hour=None
                 ):
        super().__init__()
        self.row_id = row_id
        self.row_entry_date = row_entry_date
        self.row_update_date = row_update_date
        self.platform_handle = platform_handle
        self.sensor_id = sensor_id
        self.m_type_id = m_type_id
        self.m_date = m_date
        self.m_lon = m_lon
        self.m_lat = m_lat
        self.m_z = m_z
        self.m_value = m_value
        self.m_value_2 = m_value_2
        self.m_value_3 = m_value_3
        self.m_value_4 = m_value_4
        self.m_value_5 = m_value_5
        self.m_value_6 = m_value_6
        self.m_value_7 = m_value_7
        self.m_value_8 = m_value_8
        self.qc_metadata_id = qc_metadata_id
        self.qc_level = qc_level
        self.qc_flag = qc_flag
        self.qc_metadata_id_2 = qc_metadata_id_2
        self.qc_level_2 = qc_level_2
        self.qc_flag_2 = qc_flag_2
        self.metadata_id = metadata_id
        self.d_label_theta = d_label_theta
        self.d_top_of_hour = d_top_of_hour
        self.d_report_hour = d_report_hour


class platform_status(Base):
    __tablename__ = 'platform_status'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime(timezone=False))
    begin_date = Column(DateTime(timezone=False))
    expected_end_date = Column(DateTime(timezone=False))
    end_date = Column(DateTime(timezone=False))
    row_update_date = Column(DateTime(timezone=False))
    platform_handle = Column(String(50))
    author = Column(String(100))
    reason = Column(String(500))
    status = Column(Integer)
    platform_id = Column(Integer, ForeignKey(platform.row_id))

    platform = relationship(platform)


class sensor_status(Base):
    __tablename__ = 'sensor_status'
    row_id = Column(Integer, primary_key=True)
    sensor_id = Column(Integer, ForeignKey(sensor.row_id))
    sensor_name = Column(String(50))
    platform_id = Column(Integer, ForeignKey(platform.row_id))
    row_entry_date = Column(DateTime(timezone=False))
    begin_date = Column(DateTime(timezone=False))
    end_date = Column(DateTime(timezone=False))
    expected_end_date = Column(DateTime(timezone=False))
    row_update_date = Column(DateTime(timezone=False))
    author = Column(String(100))
    reason = Column(String(500))
    status = Column(Integer)

    platform = relationship(platform)
    sensor = relationship(sensor)


class product_type(Base):
    __tablename__ = 'product_type'
    row_id = Column(Integer, primary_key=True)
    type_name = Column(String(50))
    description = Column(String(1000))


class timestamp_lkp(Base):
    __tablename__ = 'timestamp_lkp'
    row_id = Column(Integer, primary_key=True)
    row_entry_date = Column(DateTime(timezone=False))
    row_update_date = Column(DateTime(timezone=False))
    product_id = Column(Integer, ForeignKey(product_type.row_id))
    pass_timestamp = Column(DateTime(timezone=False))
    filepath = Column(String(200))




# --- Appended: sample / sample_answer / sample_attachment models ---
# Local imports to avoid touching top-of-file imports; adjust if you prefer them at top.
from sqlalchemy import Column, Integer, DateTime, Float, String, ForeignKey, Text, Boolean, CHAR
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from sqlalchemy.sql import func

# Assumes `Base` and `organization` are already defined in this module.
# If `organization` is in another module, change ForeignKey target accordingly.

class sample(Base):
    __tablename__ = 'sample'
    row_id = Column(Integer, primary_key=True, autoincrement=True)
    row_entry_date = Column(DateTime, server_default=func.now())
    row_update_date = Column(DateTime, onupdate=func.now())

    # Link to organization (matches pattern used by platform.organization_id)
    organization_id = Column(Integer, ForeignKey('organization.row_id'), nullable=True)

    # Basic metadata
    name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)

    # When & where
    sample_date = Column(DateTime(timezone=False), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # PostGIS point; use SRID 4326 (WGS84)
    the_geom = Column(Geometry('POINT', srid=4326), nullable=True)

    # Optional address fields
    street_address = Column(String(255), nullable=True)
    city = Column(String(150), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country_code = Column(CHAR(2), nullable=True)

    # Flexible arbitrary attributes (subjective answers, misc metadata)
    attributes = Column(JSONB, nullable=True)

    # optional relation: who collected it
    collector_id = Column(Integer, nullable=True)

    # relationships
    answers = relationship("sample_answer", backref="sample", cascade="all, delete-orphan", order_by="sample_answer.answer_order")
    attachments = relationship("sample_attachment", backref="sample", cascade="all, delete-orphan")


class sample_answer(Base):
    __tablename__ = 'sample_answer'
    row_id = Column(Integer, primary_key=True, autoincrement=True)
    row_entry_date = Column(DateTime, server_default=func.now())
    row_update_date = Column(DateTime, onupdate=func.now())

    sample_id = Column(Integer, ForeignKey('sample.row_id'), nullable=False)

    # If you implement a Form + FormQuestion system, link here:
    form_question_id = Column(Integer, nullable=True)
    form_id = Column(Integer, nullable=True)
    form_version = Column(String(50), nullable=True)

    # key identifies the question or freeform field name
    key = Column(String(150), nullable=False)

    # store the original question text verbatim (variable length)
    question_text = Column(Text, nullable=True)   # <-- variable-length question text

    # typed columns (one of them will hold data)
    value_text = Column(Text, nullable=True)
    value_numeric = Column(Float, nullable=True)
    value_boolean = Column(Boolean, nullable=True)

    # full flexible payload (e.g., choice id, units, annotator confidence, raw text)
    value_json = Column(JSONB, nullable=True)

    # ordering / metadata
    answer_order = Column(Integer, nullable=False, default=0)
    qc_flag = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)


class sample_attachment(Base):
    __tablename__ = 'sample_attachment'
    row_id = Column(Integer, primary_key=True, autoincrement=True)
    row_entry_date = Column(DateTime, server_default=func.now())
    row_update_date = Column(DateTime, onupdate=func.now())

    # Foreign key back to sample
    sample_id = Column(Integer, ForeignKey('sample.row_id'), nullable=False)

    # File metadata
    filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    caption = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Storage location fields (support local directories or cloud object storage)
    # storage_type examples: 'local', 's3', 'gcs', 'azure_blob'
    storage_type = Column(String(30), nullable=False, server_default='local')

    # For local storage: a full directory path or relative path
    storage_path = Column(String(2000), nullable=True)     # e.g., '/data/uploads/2025/11/15/img123.jpg'

    # For object stores:
    storage_bucket = Column(String(500), nullable=True)     # e.g., 'my-bucket' or 'container'
    storage_object_key = Column(String(2000), nullable=True) # e.g., 'samples/2025/11/img123.jpg'

    # A canonical (optional) URL to fetch the object (could be public URL or a presigned URL)
    storage_url = Column(String(2000), nullable=True)

    # Provider-specific metadata / tags / versions / ETag / signed-url expiry, etc.
    storage_meta = Column(JSONB, nullable=True)

    # human note / uploader id (optional)
    uploaded_by = Column(String(150), nullable=True)
