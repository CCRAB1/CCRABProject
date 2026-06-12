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
