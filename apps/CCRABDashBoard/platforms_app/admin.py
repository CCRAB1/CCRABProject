from django import forms
from django.contrib import admin
from django.contrib.gis.admin import (
    GISModelAdmin,  # requires GeoDjango; remove if not using
)
from django.http import JsonResponse
from django.urls import path, reverse
from django.utils import timezone

from . import models

ROW_TIMESTAMP_FIELD_NAMES = ("row_entry_date", "row_update_date")

PLATFORMS_ADMIN_MODEL_GROUPS = [
    ("Core", ["Organization", "Platform", "Sensor", "Obs_type", "Uom_type"]),
    ("Data Sources", ["DataSource", "PlatformSource", "SourceObservationMap"]),
    ("Status", ["Platform_status", "Sensor_status"]),
    ("Samples", ["Sample", "Sample_answer", "Sample_attachment"]),
    ("Lookups", ["Platform_type", "Platform_metadata", "Platform_images"]),
]
_default_get_app_list = admin.site.get_app_list


def model_has_field(model_or_instance, field_name):
    meta = getattr(model_or_instance, "_meta", None)
    if meta is None:
        return False

    for field in meta.fields:
        if field.name == field_name:
            return True

    return False


def timestamp_readonly_fields(model, readonly_fields):
    fields = list(readonly_fields)

    for field_name in ROW_TIMESTAMP_FIELD_NAMES:
        if model_has_field(model, field_name) and field_name not in fields:
            fields.append(field_name)

    return tuple(fields)


def stamp_row_dates(instance, is_change, now=None):
    if now is None:
        now = timezone.now()

    if model_has_field(instance, "row_entry_date") and not is_change:
        if not instance.row_entry_date:
            instance.row_entry_date = now

    if model_has_field(instance, "row_update_date"):
        instance.row_update_date = now


class RowTimestampAdminMixin:
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        return timestamp_readonly_fields(self.model, readonly_fields)

    def save_model(self, request, obj, form, change):
        stamp_row_dates(obj, is_change=change)
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for deleted_object in formset.deleted_objects:
            deleted_object.delete()

        for instance in instances:
            stamp_row_dates(instance, is_change=instance.pk is not None)
            instance.save()

        formset.save_m2m()


class RowTimestampInlineMixin:
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        return timestamp_readonly_fields(self.model, readonly_fields)


class TimestampedModelAdmin(RowTimestampAdminMixin, admin.ModelAdmin):
    pass


class TimestampedGISModelAdmin(RowTimestampAdminMixin, GISModelAdmin):
    pass


class TimestampedTabularInline(RowTimestampInlineMixin, admin.TabularInline):
    pass


def platform_source_platform_label(platform_source):
    platform = platform_source.platform_id
    if platform is None:
        return f"Platform ID unavailable ({platform_source.pk})"

    platform_name = platform.short_name or platform.platform_handle or platform.long_name
    if platform_name:
        return f"{platform.pk} - {platform_name}"

    return str(platform.pk)


def selected_platform_id_for_source(platform_source_id):
    if not platform_source_id:
        return None

    try:
        platform_source_pk = int(platform_source_id)
    except (TypeError, ValueError):
        return None

    return (
        models.PlatformSource.objects.filter(pk=platform_source_pk)
        .values_list("platform_id", flat=True)
        .first()
    )


def sensors_for_platform_source(platform_source_id):
    platform_id = selected_platform_id_for_source(platform_source_id)
    if not platform_id:
        return models.Sensor.objects.none()

    return models.Sensor.objects.filter(platform_id=platform_id).order_by(
        "short_name",
        "row_id",
    )


def remove_add_related_option(form_field):
    if form_field is None:
        return

    if hasattr(form_field.widget, "can_add_related"):
        form_field.widget.can_add_related = False


def set_widget_attr(form_field, name, value):
    form_field.widget.attrs[name] = value

    if hasattr(form_field.widget, "widget"):
        form_field.widget.widget.attrs[name] = value


def observation_type_label(obs_type):
    return obs_type.standard_name or f"Observation type {obs_type.pk}"


def uom_type_label(uom_type):
    label = uom_type.standard_name or f"UOM type {uom_type.pk}"

    if uom_type.display and uom_type.display != label:
        label = f"{label} ({uom_type.display})"

    return label


def m_type_description(obs_type, uom_type):
    return f"{observation_type_label(obs_type)} / {uom_type_label(uom_type)}"


def scalar_type_for_sensor(sensor):
    if not sensor:
        return None

    try:
        m_type = sensor.m_type_id
    except models.M_type.DoesNotExist:
        return None

    if not m_type:
        return None

    try:
        return m_type.m_scalar_type_id
    except models.M_scalar_type.DoesNotExist:
        return None


def obs_type_for_scalar_type(scalar_type):
    if scalar_type is None or not scalar_type.obs_type_id_id:
        return None

    try:
        return scalar_type.obs_type_id
    except models.Obs_type.DoesNotExist:
        return None


def uom_type_for_scalar_type(scalar_type):
    if scalar_type is None or not scalar_type.uom_type_id_id:
        return None

    try:
        return scalar_type.uom_type_id
    except models.Uom_type.DoesNotExist:
        return None


def resolve_m_type_for_sensor_fields(obs_type, uom_type):
    scalar_type = (
        models.M_scalar_type.objects.filter(
            obs_type_id=obs_type,
            uom_type_id=uom_type,
        )
        .order_by("row_id")
        .first()
    )

    if scalar_type is None:
        scalar_type = models.M_scalar_type.objects.create(
            obs_type_id=obs_type,
            uom_type_id=uom_type,
        )

    m_type = (
        models.M_type.objects.filter(
            m_scalar_type_id=scalar_type,
            m_scalar_type_id_2__isnull=True,
            m_scalar_type_id_3__isnull=True,
            m_scalar_type_id_4__isnull=True,
            m_scalar_type_id_5__isnull=True,
            m_scalar_type_id_6__isnull=True,
            m_scalar_type_id_7__isnull=True,
            m_scalar_type_id_8__isnull=True,
        )
        .order_by("row_id")
        .first()
    )

    if m_type is not None:
        return m_type

    return models.M_type.objects.create(
        num_types=1,
        description=m_type_description(obs_type, uom_type),
        m_scalar_type_id=scalar_type,
    )


class SensorAdminForm(forms.ModelForm):
    obs_type_id = forms.ModelChoiceField(
        label="Observation type",
        queryset=models.Obs_type.objects.order_by("standard_name", "row_id"),
        required=True,
    )
    uom_type_id = forms.ModelChoiceField(
        label="Unit of measure",
        queryset=models.Uom_type.objects.order_by(
            "standard_name",
            "display",
            "row_id",
        ),
        required=True,
    )

    class Meta:
        model = models.Sensor
        exclude = ("m_type_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["obs_type_id"].label_from_instance = observation_type_label
        self.fields["uom_type_id"].label_from_instance = uom_type_label
        self.set_observation_unit_initial_values()

    def set_observation_unit_initial_values(self):
        scalar_type = scalar_type_for_sensor(self.instance)
        if scalar_type is None:
            return

        if scalar_type.obs_type_id_id:
            self.fields["obs_type_id"].initial = scalar_type.obs_type_id

        if scalar_type.uom_type_id_id:
            self.fields["uom_type_id"].initial = scalar_type.uom_type_id

    def save(self, commit=True):
        sensor = super().save(commit=False)
        sensor.m_type_id = resolve_m_type_for_sensor_fields(
            self.cleaned_data["obs_type_id"],
            self.cleaned_data["uom_type_id"],
        )

        if commit:
            sensor.save()
            self.save_m2m()

        return sensor


class SensorObservationTypeListFilter(admin.SimpleListFilter):
    title = "Observation type"
    parameter_name = "obs_type_id"

    def lookups(self, request, model_admin):
        lookups = []
        obs_types = models.Obs_type.objects.order_by("standard_name", "row_id")

        for obs_type in obs_types:
            lookups.append((str(obs_type.pk), observation_type_label(obs_type)))

        return lookups

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        return queryset.filter(
            m_type_id__m_scalar_type_id__obs_type_id=self.value(),
        )


class SensorUomTypeListFilter(admin.SimpleListFilter):
    title = "Unit of measure"
    parameter_name = "uom_type_id"

    def lookups(self, request, model_admin):
        lookups = []
        uom_types = models.Uom_type.objects.order_by(
            "standard_name",
            "display",
            "row_id",
        )

        for uom_type in uom_types:
            lookups.append((str(uom_type.pk), uom_type_label(uom_type)))

        return lookups

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        return queryset.filter(
            m_type_id__m_scalar_type_id__uom_type_id=self.value(),
        )


class SourceObservationMapAdminForm(forms.ModelForm):
    class Meta:
        model = models.SourceObservationMap
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure_platform_source_field()
        self.configure_sensor_field()

    def configure_platform_source_field(self):
        platform_source_field = self.fields.get("platform_source_id")
        if not platform_source_field:
            return

        platform_source_field.label = "Platform ID"
        platform_source_field.queryset = platform_source_field.queryset.select_related(
            "platform_id"
        )
        platform_source_field.label_from_instance = platform_source_platform_label
        set_widget_attr(
            platform_source_field,
            "data-sensor-options-url",
            reverse("admin:platforms_app_sourceobservationmap_sensor_options"),
        )

    def configure_sensor_field(self):
        sensor_field = self.fields.get("sensor_id")
        if not sensor_field:
            return

        sensor_field.queryset = sensors_for_platform_source(
            self.selected_platform_source_id()
        )
        remove_add_related_option(sensor_field)

    def selected_platform_source_id(self):
        field_name = self.add_prefix("platform_source_id")
        if self.data:
            submitted_value = self.data.get(field_name)
            if submitted_value:
                return submitted_value

        initial_value = self.initial.get("platform_source_id")
        if initial_value:
            return getattr(initial_value, "pk", initial_value)

        if self.instance and self.instance.pk:
            return self.instance.platform_source_id_id

        return None

    class Media:
        js = ("platforms_app/js/source_observation_map_admin.js",)


# -----------------------
# Inlines for FK relations
# -----------------------

class PlatformInline(TimestampedTabularInline):
    model = models.Platform
    fk_name = "organization_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'type_id', 'short_name', 'platform_handle')
    extra = 0
    show_change_link = True

class SampleInline(TimestampedTabularInline):
    model = models.Sample
    fk_name = "organization_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'name', 'description', 'sample_date')
    extra = 0
    show_change_link = True

class M_scalar_typeInline(TimestampedTabularInline):
    model = models.M_scalar_type
    fk_name = "obs_type_id"
    fields = ('row_id', 'uom_type_id')
    extra = 0
    show_change_link = True

class M_scalar_typeInline2(TimestampedTabularInline):
    model = models.M_scalar_type
    fk_name = "uom_type_id"
    fields = ('row_id', 'obs_type_id')
    extra = 0
    show_change_link = True

class M_typeInline(TimestampedTabularInline):
    model = models.M_type
    fk_name = "m_scalar_type_id"
    fields = ('row_id', 'num_types', 'description', 'm_scalar_type_id_2', 'm_scalar_type_id_3', 'm_scalar_type_id_4')
    extra = 0
    show_change_link = True

class SensorInline(TimestampedTabularInline):
    model = models.Sensor
    form = SensorAdminForm
    fk_name = "platform_id"
    fields = (
        'row_id',
        'row_entry_date',
        'row_update_date',
        'type_id',
        'short_name',
        'obs_type_id',
        'uom_type_id',
        'fixed_z',
        's_order',
    )
    extra = 0
    show_change_link = True

class PlatformSourceInline(TimestampedTabularInline):
    model = models.PlatformSource
    fk_name = "platform_id"
    fields = (
        'row_id',
        'data_source_id',
        'external_identifier',
        'active',
        'begin_date',
        'end_date',
        'row_entry_date',
        'row_update_date',
    )
    readonly_fields = ('row_id', 'row_entry_date', 'row_update_date')
    extra = 0
    show_change_link = True

class DataSourcePlatformSourceInline(TimestampedTabularInline):
    model = models.PlatformSource
    fk_name = "data_source_id"
    fields = (
        'row_id',
        'platform_id',
        'external_identifier',
        'active',
        'begin_date',
        'end_date',
        'row_entry_date',
        'row_update_date',
    )
    readonly_fields = ('row_id', 'row_entry_date', 'row_update_date')
    extra = 0
    show_change_link = True

class SourceObservationMapInline(TimestampedTabularInline):
    model = models.SourceObservationMap
    fk_name = "platform_source_id"
    fields = (
        'row_id',
        'sensor_id',
        'source_obs',
        'source_uom',
        'source_identifier',
        'active',
        'begin_date',
        'end_date',
        'row_entry_date',
        'row_update_date',
    )
    readonly_fields = ('row_id', 'row_entry_date', 'row_update_date')
    extra = 0
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sensor_id":
            platform_source_id = request.resolver_match.kwargs.get("object_id")
            kwargs["queryset"] = sensors_for_platform_source(platform_source_id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = super().formfield_for_dbfield(db_field, request, **kwargs)

        if db_field.name == "sensor_id":
            remove_add_related_option(form_field)

        return form_field

class SensorSourceObservationMapInline(TimestampedTabularInline):
    model = models.SourceObservationMap
    fk_name = "sensor_id"
    fields = (
        'row_id',
        'platform_source_id',
        'source_obs',
        'source_uom',
        'source_identifier',
        'active',
        'begin_date',
        'end_date',
        'row_entry_date',
        'row_update_date',
    )
    readonly_fields = ('row_id', 'row_entry_date', 'row_update_date')
    extra = 0
    show_change_link = True

class Platform_statusInline(TimestampedTabularInline):
    model = models.Platform_status
    fk_name = "platform_id"
    fields = ('row_id', 'row_entry_date', 'begin_date', 'expected_end_date', 'end_date', 'row_update_date')
    extra = 0
    show_change_link = True

class Platform_imagesInline(TimestampedTabularInline):
    model = models.Platform_status
    fk_name = "platform_id"
    fields = ('row_id', 'row_entry_date', 'name', 'description', 'filepath')
    extra = 0
    show_change_link = True


class Sensor_statusInline(TimestampedTabularInline):
    model = models.Sensor_status
    fk_name = "platform_id"
    fields = ('row_id', 'sensor_id', 'sensor_name', 'row_entry_date', 'begin_date', 'end_date')
    extra = 0
    show_change_link = True

class SensorInline2(TimestampedTabularInline):
    model = models.Sensor
    fk_name = "m_type_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'platform_id', 'type_id', 'short_name')
    extra = 0
    show_change_link = True

class Multi_obsInline(TimestampedTabularInline):
    model = models.Multi_obs
    fk_name = "m_type_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'platform_handle', 'sensor_id', 'm_date')
    extra = 0
    show_change_link = True

class Multi_obsInline2(TimestampedTabularInline):
    model = models.Multi_obs
    fk_name = "sensor_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'platform_handle', 'm_type_id', 'm_date')
    extra = 0
    show_change_link = True

class Sensor_statusInline2(TimestampedTabularInline):
    model = models.Sensor_status
    fk_name = "sensor_id"
    fields = ('row_id', 'sensor_name', 'platform_id', 'row_entry_date', 'begin_date', 'end_date')
    extra = 0
    show_change_link = True

class Sample_answerInline(TimestampedTabularInline):
    model = models.Sample_answer
    fk_name = "sample_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'form_question_id', 'form_id', 'form_version')
    extra = 0
    show_change_link = True

class Sample_attachmentInline(TimestampedTabularInline):
    model = models.Sample_attachment
    fk_name = "sample_id"
    fields = ('row_id', 'row_entry_date', 'row_update_date', 'filename', 'mime_type', 'caption')
    extra = 0
    show_change_link = True

@admin.register(models.Organization)
class OrganizationAdmin(TimestampedModelAdmin):
    fields = ('short_name', 'long_name', 'description', 'active', 'url')
    list_display = ('row_id', 'short_name', 'active', 'row_entry_date', 'row_update_date', 'long_name')
    search_fields = ('short_name', 'long_name', 'url')
    list_filter = ('active',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [PlatformInline, SampleInline]

@admin.register(models.Collection_type)
class Collection_typeAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'type_name', 'row_entry_date', 'row_update_date', 'description')
    search_fields = ('type_name',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Collection_run)
class Collection_runAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'short_name', 'row_entry_date', 'row_update_date', 'type_id', 'long_name')
    search_fields = ('short_name', 'long_name')
    list_filter = ('type_id',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Platform_type)
class Platform_typeAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'short_name', 'type_name', 'description')
    search_fields = ('type_name', 'short_name')

@admin.register(models.Platform_metadata)
class Platform_metadataAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'row_entry_date', 'row_update_date', 'meta_key', 'meta_value')
    search_fields = ('meta_key',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Platform)
class PlatformAdmin(TimestampedGISModelAdmin):
    list_display = ('row_id', 'short_name', 'platform_handle', 'active', 'begin_date', 'end_date', 'row_entry_date')
    search_fields = ('short_name', 'long_name', 'url')
    list_filter = ('type_id', 'active')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [SensorInline, PlatformSourceInline, Platform_statusInline, Sensor_statusInline]

@admin.register(models.DataSource)
class DataSourceAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'key', 'name', 'plugin_id', 'plugin_version', 'active', 'row_update_date')
    search_fields = ('key', 'name', 'description', 'plugin_id')
    list_filter = ('active', 'plugin_id')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [DataSourcePlatformSourceInline]

@admin.register(models.PlatformSource)
class PlatformSourceAdmin(TimestampedModelAdmin):
    list_display = (
        'row_id',
        'platform_id',
        'data_source_id',
        'external_identifier',
        'active',
        'begin_date',
        'end_date',
    )
    search_fields = (
        'platform_id__short_name',
        'platform_id__long_name',
        'data_source_id__key',
        'data_source_id__name',
        'external_identifier',
    )
    list_filter = ('active', 'data_source_id')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [SourceObservationMapInline]

@admin.register(models.SourceObservationMap)
class SourceObservationMapAdmin(TimestampedModelAdmin):
    form = SourceObservationMapAdminForm
    list_select_related = ('platform_source_id__platform_id', 'sensor_id')
    list_display = (
        'row_id',
        'platform_id',
        'sensor_id',
        'source_obs',
        'source_uom',
        'source_identifier',
        'active',
    )
    search_fields = (
        'platform_source_id__platform_id__short_name',
        'platform_source_id__data_source_id__key',
        'platform_source_id__data_source_id__name',
        'sensor_id__short_name',
        'source_obs',
        'source_uom',
        'source_identifier',
    )
    list_filter = ('active', 'platform_source_id__data_source_id')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        form_field = super().formfield_for_dbfield(db_field, request, **kwargs)

        if db_field.name == "sensor_id":
            remove_add_related_option(form_field)

        return form_field

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "sensor-options/",
                self.admin_site.admin_view(self.sensor_options),
                name="platforms_app_sourceobservationmap_sensor_options",
            ),
        ]
        return custom_urls + urls

    @admin.display(
        description="Platform ID",
        ordering="platform_source_id__platform_id__short_name",
    )
    def platform_id(self, obj):
        platform_source = obj.platform_source_id
        if platform_source is None:
            return None

        platform = platform_source.platform_id
        if platform is None:
            return None

        return platform.short_name or platform.platform_handle or platform.pk

    def sensor_options(self, request):
        sensors = []
        sensor_queryset = sensors_for_platform_source(
            request.GET.get("platform_source_id")
        )

        for sensor in sensor_queryset:
            sensors.append(
                {
                    "value": sensor.pk,
                    "label": str(sensor),
                }
            )

        return JsonResponse({"sensors": sensors})


@admin.register(models.Uom_type)
class Uom_typeAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'standard_name', 'definition', 'display')
    search_fields = ('standard_name',)
    inlines = [M_scalar_typeInline2]

@admin.register(models.Obs_type)
class Obs_typeAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'standard_name', 'definition')
    search_fields = ('standard_name',)
    inlines = [M_scalar_typeInline]

'''
@admin.register(models.M_scalar_type)
class M_scalar_typeAdmin(admin.ModelAdmin):
    list_display = ('row_id', 'obs_type_id', 'uom_type_id')
    inlines = [M_typeInline]
'''
'''
@admin.register(models.M_type)
class M_typeAdmin(admin.ModelAdmin):
    list_display = ('row_id', 'num_types', 'description', 'm_scalar_type_id', 'm_scalar_type_id_2', 'm_scalar_type_id_3')
    inlines = [SensorInline2]
'''
@admin.register(models.Sensor)
class SensorAdmin(TimestampedModelAdmin):
    form = SensorAdminForm
    fields = (
        'platform_id',
        'type_id',
        'short_name',
        'obs_type_id',
        'uom_type_id',
        'fixed_z',
        'active',
        'begin_date',
        'end_date',
        's_order',
        'url',
        'metadata_id',
        'report_interval',
        'row_entry_date',
        'row_update_date',
    )
    list_select_related = (
        'platform_id',
        'm_type_id__m_scalar_type_id__obs_type_id',
        'm_type_id__m_scalar_type_id__uom_type_id',
    )
    list_display = (
        'row_id',
        'short_name',
        'platform_id',
        'obs_type',
        'uom_type',
        'active',
        'begin_date',
        'end_date',
        'row_entry_date',
    )
    search_fields = (
        'short_name',
        'url',
        'm_type_id__m_scalar_type_id__obs_type_id__standard_name',
        'm_type_id__m_scalar_type_id__uom_type_id__standard_name',
        'm_type_id__m_scalar_type_id__uom_type_id__display',
    )
    list_filter = (
        'platform_id',
        'type_id',
        SensorObservationTypeListFilter,
        SensorUomTypeListFilter,
        'active',
    )
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [Sensor_statusInline2, SensorSourceObservationMapInline]
    #inlines = [Multi_obsInline2, Sensor_statusInline2]

    @admin.display(
        description="Observation type",
        ordering="m_type_id__m_scalar_type_id__obs_type_id__standard_name",
    )
    def obs_type(self, obj):
        obs_type = obs_type_for_scalar_type(scalar_type_for_sensor(obj))
        if obs_type is None:
            return None

        return observation_type_label(obs_type)

    @admin.display(
        description="Unit of measure",
        ordering="m_type_id__m_scalar_type_id__uom_type_id__standard_name",
    )
    def uom_type(self, obj):
        uom_type = uom_type_for_scalar_type(scalar_type_for_sensor(obj))
        if uom_type is None:
            return None

        return uom_type_label(uom_type)

'''
@admin.register(models.Multi_obs)
class Multi_obsAdmin(GISModelAdmin):
    list_display = ('row_id', 'platform_handle', 'row_entry_date', 'row_update_date', 'sensor_id', 'm_type_id')
    list_filter = ('m_type_id',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
'''
@admin.register(models.Platform_status)
class Platform_statusAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'platform_handle', 'status', 'begin_date', 'end_date', 'row_entry_date')
    list_filter = ('status', 'platform_id')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Sensor_status)
class Sensor_statusAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'status', 'begin_date', 'end_date', 'row_entry_date', 'sensor_id')
    search_fields = ('sensor_name',)
    list_filter = ('platform_id', 'status')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Product_type)
class Product_typeAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'type_name', 'description')
    search_fields = ('type_name',)

@admin.register(models.Timestamp_lkp)
class Timestamp_lkpAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'row_entry_date', 'row_update_date', 'product_id', 'pass_timestamp', 'filepath')
    search_fields = ('filepath',)
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Sample)
class SampleAdmin(TimestampedGISModelAdmin):
    list_display = ('row_id', 'name', 'row_entry_date', 'row_update_date', 'organization_id', 'description')
    search_fields = ('name', 'postal_code', 'country_code')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"
    inlines = [Sample_answerInline, Sample_attachmentInline]

@admin.register(models.Sample_answer)
class Sample_answerAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'row_entry_date', 'row_update_date', 'sample_id', 'form_question_id', 'form_id')
    search_fields = ('form_question_id', 'question_text')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Sample_attachment)
class Sample_attachmentAdmin(TimestampedModelAdmin):
    list_display = ('row_id', 'filename', 'row_entry_date', 'row_update_date', 'sample_id', 'mime_type')
    search_fields = ('filename', 'storage_url')
    readonly_fields = ('row_entry_date', 'row_update_date')
    date_hierarchy = "row_entry_date"

@admin.register(models.Platform_images)
class Platform_imagesAdmin(TimestampedModelAdmin):
    list_display = ('name','description','filepath')
    search_fields = ['name']


def get_app_list(request, app_label=None):
    app_list = _default_get_app_list(request, app_label)

    for app in app_list:
        if app["app_label"] != "platforms_app":
            continue

        remaining_models = list(app["models"])
        model_groups = []

        for group_name, object_names in PLATFORMS_ADMIN_MODEL_GROUPS:
            group_models = []

            for object_name in object_names:
                matched_model = None

                for model in remaining_models:
                    if model["object_name"] == object_name:
                        matched_model = model
                        break

                if matched_model:
                    group_models.append(matched_model)
                    remaining_models.remove(matched_model)

            if group_models:
                model_groups.append({
                    "name": group_name,
                    "models": group_models,
                })

        if remaining_models:
            model_groups.append({
                "name": "Other",
                "models": remaining_models,
            })

        app["model_groups"] = model_groups

    return app_list


admin.site.get_app_list = get_app_list

admin.site.get_app_list = get_app_list
