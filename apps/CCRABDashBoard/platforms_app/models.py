from django.contrib.gis.db import models as gis_models  # remove if not using GeoDjango
from django.db import models


# Auto-generated Django models from XeniaTables.py
def platform_picture_upload_to(instance, filename):
    platform_id = instance.platform_id or "unassigned"
    return f"projects_app/project_pictures/{platform_id}/{filename}"


class Organization(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    short_name = models.CharField(max_length=50, null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    long_name = models.CharField(max_length=200, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    url = models.CharField(max_length=200, null=True, blank=True)
    opendap_url = models.CharField(max_length=200, null=True, blank=True)
    email_tech = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."organization"'
        managed = True

    def __str__(self):
        return f"Organization {getattr(self, 'short_name', self.pk)}"

class Collection_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    type_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."collection_type"'
        managed = True

    def __str__(self):
        return f"collection_type {getattr(self, 'row_id', self.pk)}"

class Collection_run(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    type_id = models.IntegerField(null=True, blank=True)
    short_name = models.CharField(max_length=255, null=True, blank=True)
    long_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    fixed_date = models.DateTimeField(null=True, blank=True)
    min_date = models.DateTimeField(null=True, blank=True)
    max_date = models.DateTimeField(null=True, blank=True)
    fixed_lon = models.FloatField(null=True, blank=True)
    min_lon = models.FloatField(null=True, blank=True)
    max_lon = models.FloatField(null=True, blank=True)
    fixed_lat = models.FloatField(null=True, blank=True)
    min_lat = models.FloatField(null=True, blank=True)
    max_lat = models.FloatField(null=True, blank=True)
    fixed_z = models.FloatField(null=True, blank=True)
    min_z = models.FloatField(null=True, blank=True)
    max_z = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."collection"'
        managed = True

    def __str__(self):
        return f"collection {getattr(self, 'row_id', self.pk)}"

class Platform_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    type_name = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    short_name = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."platform_type"'
        managed = True

    def __str__(self):
        return f"{getattr(self, 'type_name', self.pk)}"

class Platform_metadata(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)

    platform_id = models.ForeignKey('Platform', on_delete=models.CASCADE, db_column='platform_id', null=True, blank=True)
    meta_key =  models.CharField(max_length=100, null=True, blank=True)
    meta_value = models.CharField(max_length=200, null=True, blank=True)




    class Meta:
        db_table = '"platforms"."platform_metadata"'
        managed = True

    def __str__(self):
        return f"Platform Metadata {getattr(self, 'row_id', self.pk)}"

class Platform(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    organization_id = models.ForeignKey('Organization', on_delete=models.CASCADE, db_column='organization_id', null=True, blank=True)
    #type_id = models.IntegerField(null=True, blank=True)
    type_id = models.ForeignKey('Platform_type', on_delete=models.CASCADE, db_column='type_id', null=True, blank=True)
    short_name = models.CharField(max_length=50, null=True, blank=True)
    platform_handle = models.CharField(max_length=100, null=True, blank=True)
    fixed_longitude = models.FloatField(null=True, blank=True)
    fixed_latitude = models.FloatField(null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    project_id = models.IntegerField(null=True, blank=True)
    app_catalog_id = models.IntegerField(null=True, blank=True)
    long_name = models.CharField(max_length=200, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    url = models.CharField(max_length=200, null=True, blank=True)
    the_geom = gis_models.PointField(srid=4326, null=True, blank=True)

    manufacturer = models.CharField(max_length=100, null=True, blank=True)
    serial_number =models.CharField(max_length=200, null=True, blank=True)
    firmware_version = models.CharField(max_length=100, null=True, blank=True)
    # Country
    country_code = models.CharField(max_length=2, null=True, blank=True)   # ISO 3166-1 alpha-2
    country_name = models.CharField(max_length=100, null=True, blank=True)               # optional
    # City & Locality
    city = models.CharField(max_length=150, null=True, blank=True)
    neighborhood = models.CharField(max_length=150, null=True, blank=True)               # optional
    street_address =models.CharField(max_length=255, null=True, blank=True)             # e.g., "123 Main St"
    postal_code = models.CharField(max_length=20, null=True, blank=True)

    timezone = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."platform"'
        managed = True

    def __str__(self):
        return f"Platform {getattr(self, 'short_name', self.pk)}"

class Platform_images(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_id = models.ForeignKey('Platform', on_delete=models.CASCADE, db_column='platform_id', null=False,
                                    blank=False)
    name = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    filepath = models.FileField(upload_to=platform_picture_upload_to, null=False, blank=False)
    #file = models.FileField(upload_to="platform_pictures/", null=True, blank=True)

    class Meta:
        db_table = '"platforms"."platform_images"'
        managed = True

    def __str__(self):
        return self.name

class DataSource(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    plugin_id = models.CharField(max_length=100, null=True, blank=True)
    plugin_version = models.CharField(max_length=50, null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    settings = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."data_source"'
        managed = True

    def __str__(self):
        return self.name or self.key or f"Data Source {self.pk}"

class PlatformSource(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_id = models.ForeignKey(
        'Platform',
        on_delete=models.DO_NOTHING,
        db_column='platform_id',
        null=True,
        blank=True,
    )
    data_source_id = models.ForeignKey(
        'DataSource',
        on_delete=models.DO_NOTHING,
        db_column='data_source_id',
        null=True,
        blank=True,
    )
    external_identifier = models.CharField(max_length=200, null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    settings = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."platform_source"'
        managed = True
        unique_together = (
            ('platform_id', 'data_source_id', 'external_identifier'),
        )

    def __str__(self):
        return f"Platform Source {getattr(self, 'external_identifier', self.pk)}"

class Uom_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    standard_name = models.CharField(max_length=50, null=True, blank=True)
    definition = models.CharField(max_length=1000, null=True, blank=True)
    display = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."uom_type"'
        managed = True

    def __str__(self):
        return f"UOM {getattr(self, 'standard_name', self.pk)}"

class Obs_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    standard_name = models.CharField(max_length=50, null=True, blank=True)
    definition = models.CharField(max_length=1000, null=True, blank=True)
    display = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."obs_type"'
        managed = True

    def __str__(self):
        return f"Observation Type {getattr(self, 'standard_name', self.pk)}"

class M_scalar_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    obs_type_id = models.ForeignKey('Obs_type', on_delete=models.CASCADE, db_column='obs_type_id', null=True, blank=True)
    uom_type_id = models.ForeignKey('Uom_type', on_delete=models.CASCADE, db_column='uom_type_id', null=True, blank=True)
    class Meta:
        db_table = '"platforms"."m_scalar_type"'
        managed = True

    def __str__(self):
        return f"m_scalar_type {getattr(self, 'row_id', self.pk)}"

class M_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    num_types = models.IntegerField(null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)
    m_scalar_type_id = models.ForeignKey('M_scalar_type', on_delete=models.CASCADE, db_column='m_scalar_type_id', null=True, blank=True)
    m_scalar_type_id_2 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_3 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_4 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_5 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_6 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_7 = models.IntegerField(null=True, blank=True)
    m_scalar_type_id_8 = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."m_type"'
        managed = True

    def __str__(self):
        return f"m_type {getattr(self, 'row_id', self.pk)}"

class Sensor(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_id = models.ForeignKey('Platform', on_delete=models.CASCADE, db_column='platform_id', null=True, blank=True)
    type_id = models.IntegerField(null=True, blank=True)
    short_name = models.CharField(max_length=50, null=True, blank=True)
    m_type_id = models.ForeignKey('M_type', on_delete=models.CASCADE, db_column='m_type_id', null=True, blank=True)
    fixed_z = models.FloatField(null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    s_order = models.IntegerField(null=True, blank=True)
    url = models.CharField(max_length=200, null=True, blank=True)
    metadata_id = models.IntegerField(null=True, blank=True)
    report_interval = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."sensor"'
        managed = True

    def __str__(self):
        return f"Sensor {getattr(self, 'short_name', self.pk)}"

class Multi_obs(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_handle = models.CharField(max_length=100, null=True, blank=True)
    sensor_id = models.ForeignKey('Sensor', on_delete=models.CASCADE, db_column='sensor_id')
    m_type_id = models.ForeignKey('M_type', on_delete=models.CASCADE, db_column='m_type_id')
    m_date = models.DateTimeField(null=True, blank=True)
    m_lon = models.FloatField(null=True, blank=True)
    m_lat = models.FloatField(null=True, blank=True)
    m_z = models.FloatField(null=True, blank=True)
    m_value = models.FloatField(null=True, blank=True)
    m_value_2 = models.FloatField(null=True, blank=True)
    m_value_3 = models.FloatField(null=True, blank=True)
    m_value_4 = models.FloatField(null=True, blank=True)
    m_value_5 = models.FloatField(null=True, blank=True)
    m_value_6 = models.FloatField(null=True, blank=True)
    m_value_7 = models.FloatField(null=True, blank=True)
    m_value_8 = models.FloatField(null=True, blank=True)
    qc_metadata_id = models.IntegerField(null=True, blank=True)
    qc_level = models.IntegerField(null=True, blank=True)
    qc_flag = models.CharField(max_length=100, null=True, blank=True)
    qc_metadata_id_2 = models.IntegerField(null=True, blank=True)
    qc_level_2 = models.IntegerField(null=True, blank=True)
    qc_flag_2 = models.CharField(max_length=100, null=True, blank=True)
    metadata_id = models.IntegerField(null=True, blank=True)
    d_label_theta = models.IntegerField(null=True, blank=True)
    d_top_of_hour = models.IntegerField(null=True, blank=True)
    d_report_hour = models.DateTimeField(null=True, blank=True)
    the_geom = gis_models.PointField(srid=4326, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."multi_obs"'
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=['m_date', 'm_type_id', 'sensor_id'],
                name='i_multi_obs',
            ),
        ]
        indexes = [
            models.Index(
                fields=['m_date', 'platform_handle'],
                name='i_multi_obs_date_platform',
            ),
        ]

    def __str__(self):
        return f"multi_obs {getattr(self, 'row_id', self.pk)}"

class SourceObservationMap(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_source_id = models.ForeignKey(
        'PlatformSource',
        on_delete=models.DO_NOTHING,
        db_column='platform_source_id',
        null=True,
        blank=True,
    )
    sensor_id = models.ForeignKey(
        'Sensor',
        on_delete=models.DO_NOTHING,
        db_column='sensor_id',
        null=True,
        blank=True,
    )
    source_obs = models.CharField(max_length=100, null=True, blank=True)
    source_uom = models.CharField(max_length=50, null=True, blank=True)
    source_identifier = models.CharField(max_length=200, null=True, blank=True)
    active = models.IntegerField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    settings = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."source_observation_map"'
        managed = True
        unique_together = (
            ('platform_source_id', 'source_obs', 'source_identifier'),
        )

    def __str__(self):
        return f"Source Observation Map {getattr(self, 'source_obs', self.pk)}"

class Platform_status(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    expected_end_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_handle = models.CharField(max_length=50, null=True, blank=True)
    author = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=500, null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)
    platform_id = models.ForeignKey('Platform', on_delete=models.CASCADE, db_column='platform_id', null=True, blank=True)
    class Meta:
        db_table = '"platforms"."platform_status"'
        managed = True

    def __str__(self):
        return f"platform_status {getattr(self, 'row_id', self.pk)}"

class Sensor_status(models.Model):
    row_id = models.AutoField(primary_key=True)
    sensor_id = models.ForeignKey('Sensor', on_delete=models.CASCADE, db_column='sensor_id', null=True, blank=True)
    sensor_name = models.CharField(max_length=50, null=True, blank=True)
    platform_id = models.ForeignKey('Platform', on_delete=models.CASCADE, db_column='platform_id', null=True, blank=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    begin_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    expected_end_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    author = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=500, null=True, blank=True)
    status = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."sensor_status"'
        managed = True

    def __str__(self):
        return f"sensor_status {getattr(self, 'row_id', self.pk)}"

class Product_type(models.Model):
    row_id = models.AutoField(primary_key=True)
    type_name = models.CharField(max_length=50, null=True, blank=True)
    description = models.CharField(max_length=1000, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."product_type"'
        managed = True

    def __str__(self):
        return f"product_type {getattr(self, 'row_id', self.pk)}"

class Timestamp_lkp(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    product_id = models.IntegerField(null=True, blank=True)
    pass_timestamp = models.DateTimeField(null=True, blank=True)
    filepath = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."timestamp_lkp"'
        managed = True

    def __str__(self):
        return f"timestamp_lkp {getattr(self, 'row_id', self.pk)}"

class Sample(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    organization_id = models.ForeignKey('Organization', on_delete=models.CASCADE, db_column='organization_id', null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    sample_date = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    the_geom = gis_models.PointField(srid=4326, null=True, blank=True)
    street_address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=150, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    attributes = models.JSONField(null=True, blank=True)
    collector_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."sample"'
        managed = True

    def __str__(self):
        return f"Sample {getattr(self, 'name', self.pk)}"

class Sample_answer(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    sample_id = models.ForeignKey('Sample', on_delete=models.CASCADE, db_column='sample_id', null=True, blank=True)
    form_question_id = models.IntegerField(null=True, blank=True)
    form_id = models.IntegerField(null=True, blank=True)
    form_version = models.CharField(max_length=50, null=True, blank=True)
    key = models.CharField(max_length=150, null=True, blank=True)
    question_text = models.TextField(null=True, blank=True)
    value_text = models.TextField(null=True, blank=True)
    value_numeric = models.FloatField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    answer_order = models.IntegerField(null=True, blank=True)
    qc_flag = models.CharField(max_length=50, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."sample_answer"'
        managed = True

    def __str__(self):
        return f"Question {getattr(self, 'question_text', self.pk)}"

class Sample_attachment(models.Model):
    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    sample_id = models.ForeignKey('Sample', on_delete=models.CASCADE, db_column='sample_id', null=True, blank=True)
    filename = models.CharField(max_length=255, null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    caption = models.CharField(max_length=500, null=True, blank=True)
    file_size_bytes = models.IntegerField(null=True, blank=True)
    storage_type = models.CharField(max_length=30, null=True, blank=True)
    storage_path = models.CharField(max_length=2000, null=True, blank=True)
    storage_url = models.CharField(max_length=2000, null=True, blank=True)
    storage_meta = models.JSONField(null=True, blank=True)
    uploaded_by = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = '"platforms"."sample_attachment"'
        managed = True

    def __str__(self):
        return f"Sample Attachment {getattr(self, 'filename', self.pk)}"
