from datetime import timedelta

from django.contrib.gis.db import models as gis_models  # remove if not using GeoDjango
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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
    freshness_monitoring_enabled = models.BooleanField(default=False)
    stale_after = models.DurationField(
        null=True,
        blank=True,
        help_text=(
            "Maximum age of the latest observation before a platform is "
            "considered stale."
        ),
    )
    never_reported_after = models.DurationField(
        null=True,
        blank=True,
        help_text=(
            "Time allowed before alerting for a platform that has never "
            "reported. Uses stale_after when left blank."
        ),
    )
    repeat_alert_after = models.DurationField(
        null=True,
        blank=True,
        help_text=(
            "Time between repeat notifications for an unresolved incident. "
            "Leave blank to notify only when the incident opens."
        ),
    )
    send_recovery_alert = models.BooleanField(default=True)

    class Meta:
        db_table = '"platforms"."data_source"'
        managed = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(freshness_monitoring_enabled=False)
                    | models.Q(stale_after__isnull=False)
                ),
                name="ck_data_source_monitoring_stale_after",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(stale_after__isnull=True)
                    | models.Q(stale_after__gt=timedelta(0))
                ),
                name="ck_data_source_stale_after_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(never_reported_after__isnull=True)
                    | models.Q(never_reported_after__gt=timedelta(0))
                ),
                name="ck_data_source_never_reported_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(repeat_alert_after__isnull=True)
                    | models.Q(repeat_alert_after__gt=timedelta(0))
                ),
                name="ck_data_source_repeat_alert_positive",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.freshness_monitoring_enabled and self.stale_after is None:
            errors["stale_after"] = (
                "A stale threshold is required when freshness monitoring is enabled."
            )

        duration_fields = (
            "stale_after",
            "never_reported_after",
            "repeat_alert_after",
        )
        for field_name in duration_fields:
            duration = getattr(self, field_name)
            if duration is not None and duration <= timedelta(0):
                errors[field_name] = "Duration must be greater than zero."

        if errors:
            raise ValidationError(errors)

    @property
    def effective_never_reported_after(self):
        return self.never_reported_after or self.stale_after

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
        #unique_together = (
        #    ('platform_id', 'data_source_id', 'external_identifier'),
        #)
        constraints = [
            models.UniqueConstraint(
                fields=["platform_id"],
                name='unique_platform_source_platform_id',
            ),
        ]

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
        return self.description or f"m_type {getattr(self, 'row_id', self.pk)}"

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
        constraints = [
            models.UniqueConstraint(
                fields=["platform_id", "m_type_id", "s_order"],
                name='uq_sensor_platform_m_type_s_order',
            ),
        ]

    def __str__(self):
        sensor_label = (
            f"{getattr(self, 'short_name', self.pk)}-"
            f"{getattr(self, 's_order', '1')}"
        )
        if not self.platform_id_id:
            return sensor_label

        platform_label = (
            self.platform_id.short_name
            or self.platform_id.platform_handle
            or self.platform_id.pk
        )
        return f"{platform_label}: {sensor_label}"


class DataSourceSensor(models.Model):
    """The default display policy for a sensor type from a data source."""

    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    data_source_id = models.ForeignKey(
        'DataSource',
        on_delete=models.CASCADE,
        db_column='data_source_id',
    )
    m_type_id = models.ForeignKey(
        'M_type',
        on_delete=models.CASCADE,
        db_column='m_type_id',
    )

    class Meta:
        db_table = '"platforms"."data_source_sensor"'
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=['data_source_id', 'm_type_id'],
                name='uq_data_source_sensor',
            ),
        ]

    def __str__(self):
        return f"{self.data_source_id} / {self.m_type_id}"

    def clean(self):
        super().clean()
        if not self.data_source_id_id or not self.m_type_id_id:
            return

        if not Sensor.objects.filter(
            platform_id__platformsource__data_source_id=self.data_source_id_id,
            m_type_id=self.m_type_id_id,
        ).exists():
            raise ValidationError(
                {
                    "m_type_id": (
                        "The sensor type must be used by a platform served by "
                        "the selected data source."
                    )
                }
            )


class PlatformSensorDisplay(models.Model):
    """An individual platform sensor override of its data-source default."""

    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_id = models.ForeignKey(
        'Platform',
        on_delete=models.CASCADE,
        db_column='platform_id',
    )
    sensor_id = models.ForeignKey(
        'Sensor',
        on_delete=models.CASCADE,
        db_column='sensor_id',
    )
    display = models.BooleanField(
        help_text="Overrides the DataSource default for this sensor.",
    )

    class Meta:
        db_table = '"platforms"."platform_sensor_display"'
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=['platform_id', 'sensor_id'],
                name='uq_platform_sensor_display',
            ),
        ]

    def __str__(self):
        state = "show" if self.display else "hide"
        return f"{self.platform_id} / {self.sensor_id}: {state}"

    def clean(self):
        super().clean()
        if not self.platform_id_id or not self.sensor_id_id:
            return

        if self.sensor_id.platform_id_id != self.platform_id_id:
            raise ValidationError(
                {"sensor_id": "The sensor must belong to the selected platform."}
            )


def served_sensor_queryset():
    """Apply DataSource defaults and per-Platform overrides to sensors."""
    data_source_default = DataSourceSensor.objects.filter(
        data_source_id=models.OuterRef(
            "platform_id__platformsource__data_source_id"
        ),
        m_type_id=models.OuterRef("m_type_id"),
    )
    platform_override = PlatformSensorDisplay.objects.filter(
        platform_id=models.OuterRef("platform_id"),
        sensor_id=models.OuterRef("pk"),
    )

    return Sensor.objects.annotate(
        data_source_display=models.Exists(data_source_default),
        platform_override=models.Exists(platform_override),
        platform_show_override=models.Exists(
            platform_override.filter(display=True)
        ),
    ).filter(
        models.Q(platform_show_override=True)
        | models.Q(platform_override=False, data_source_display=True)
    )


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
            models.Index(
                fields=['platform_handle', 'm_date'],
                include=['sensor_id', 'm_value', 'm_lon', 'm_lat'],
                name='i_multi_obs_platform_date',
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
    class AlertType(models.TextChoices):
        NEVER_REPORTED = "never_reported", "Never reported"
        STALE = "stale", "Stale data"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    row_id = models.AutoField(primary_key=True)
    row_entry_date = models.DateTimeField(null=True, blank=True)
    row_update_date = models.DateTimeField(null=True, blank=True)
    platform_id = models.ForeignKey(
        'Platform',
        on_delete=models.CASCADE,
        db_column='platform_id',
    )
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_observation_at = models.DateTimeField(null=True, blank=True)
    stale_after = models.DurationField(
        help_text="Snapshot of the threshold that triggered this incident.",
    )
    last_notified_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    author = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=500, null=True, blank=True)
    details = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = '"platforms"."platform_status"'
        managed = True
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stale_after__gt=timedelta(0)),
                name="ck_platform_status_stale_after_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="resolved",
                        resolved_at__isnull=False,
                    )
                    | models.Q(
                        status__in=["open", "acknowledged"],
                        resolved_at__isnull=True,
                    )
                ),
                name="ck_platform_status_resolution",
            ),
            models.UniqueConstraint(
                fields=["platform_id"],
                condition=models.Q(resolved_at__isnull=True),
                name="uq_open_platform_freshness_incident",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "opened_at"],
                name="i_platform_status_opened",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_alert_type_display()} for "
            f"{self.platform_id}: {self.get_status_display()}"
        )

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
