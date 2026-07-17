from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import (Platform, Sample, Sensor, M_type, M_scalar_type, Obs_type, Uom_type, Platform_type,
                     Platform_images,
                     SourceObservationMap, PlatformSource, Multi_obs)



class ObsTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Obs_type
        fields = ('standard_name', 'definition', 'display')

class UomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Uom_type
        fields = ('display', 'standard_name', 'definition', 'display')

class MScalarTypeSerializer(serializers.ModelSerializer):
    obs_type = ObsTypeSerializer(source='obs_type_id', read_only=True)
    uom_type = UomTypeSerializer(source='uom_type_id', read_only=True)

    class Meta:
        model = M_scalar_type
        # include whichever fields you want from M_scalar_type + nested objs
        fields = ('obs_type', 'uom_type')

class MTypeSerializer(serializers.ModelSerializer):
    m_scalar_type = MScalarTypeSerializer(source='m_scalar_type_id', read_only=True)

    class Meta:
        model = M_type
        fields = ('description', 'm_scalar_type')

class SensorAnnotatedSerializer(serializers.ModelSerializer):
    obs_standard_name = serializers.CharField(read_only=True)
    obs_definition = serializers.CharField(read_only=True)
    uom_display = serializers.CharField(read_only=True)
    uom_standard_name = serializers.CharField(read_only=True)
    uom_definition = serializers.CharField(read_only=True)
    active = serializers.IntegerField(read_only=True)

    class Meta:
        model = Sensor
        fields = (
            'short_name',
            's_order',
            'active',
            'obs_standard_name',
            'obs_definition',
            'uom_display',
            'uom_standard_name',
            'uom_definition'
        )


class PlatformTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform_type
        fields = ('type_name', 'description', 'short_name')

class PlatformPicturesSerializer(serializers.ModelSerializer):
    filepath = serializers.FileField(use_url=True)

    class Meta:
        model = Platform_images
        fields = ('row_id', 'name', 'description', 'filepath')

class PlatformSerializer(GeoFeatureModelSerializer):
    sensors = SensorAnnotatedSerializer(many=True, read_only=True)
    type_id = PlatformTypeSerializer(read_only=True)
    #the_geom = serializers.SerializerMethodField()
    images = PlatformPicturesSerializer(source="platform_images_set", many=True, read_only=True)
    class Meta:
        model = Platform
        geo_field = "the_geom"
        fields = ("begin_date", "end_date", "short_name", "long_name", "platform_handle", "description", "active", "fixed_latitude",
                  "fixed_longitude", "type_id", "sensors", "neighborhood", "manufacturer", "serial_number",
                  "firmware_version", "country_name", "city", "neighborhood", "images", "description", "url")
    '''
    def get_the_geom(self, obj):
        if obj.fixed_longitude is None or obj.fixed_latitude is None:
            return None
        return {"type": "Point", "coordinates": [obj.fixed_longitude, obj.fixed_latitude]}
    '''
class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ("row_id", "platform", "timestamp", "value", "obs_type")


def _sensor_scalar_type(sensor):
    if not sensor or not sensor.m_type_id:
        return None
    return sensor.m_type_id.m_scalar_type_id


def _sensor_target_obs(sensor):
    scalar_type = _sensor_scalar_type(sensor)
    if not scalar_type or not scalar_type.obs_type_id:
        return None
    return scalar_type.obs_type_id.standard_name


def _sensor_target_uom(sensor):
    scalar_type = _sensor_scalar_type(sensor)
    if not scalar_type or not scalar_type.uom_type_id:
        return None
    return scalar_type.uom_type_id.standard_name


def _sensor_m_type_id(sensor):
    if not sensor or not sensor.m_type_id:
        return None
    return sensor.m_type_id.row_id


class SourceObservationMapConfigurationSerializer(serializers.ModelSerializer):
    target_obs = serializers.SerializerMethodField()
    target_uom = serializers.SerializerMethodField()
    sensor_id = serializers.SerializerMethodField()
    m_type_id = serializers.SerializerMethodField()
    s_order = serializers.SerializerMethodField()
    target_active = serializers.SerializerMethodField()
    source_active = serializers.SerializerMethodField()

    class Meta:
        model = SourceObservationMap
        fields = (
            "source_obs",
            "source_uom",
            "source_identifier",
            "source_active",
            "target_obs",
            "target_uom",
            "target_active",
            "sensor_id",
            "m_type_id",
            "s_order",
        )

    def get_sensor_id(self, obj):
        return obj.sensor_id.row_id if obj.sensor_id else None

    def get_m_type_id(self, obj):
        return _sensor_m_type_id(obj.sensor_id)

    def get_s_order(self, obj):
        return obj.sensor_id.s_order if obj.sensor_id else None

    def get_target_uom(self, obj):
        return _sensor_target_uom(obj.sensor_id)

    def get_target_obs(self, obj):
        #if obj.sensor_id and obj.sensor_id.short_name:
        #    return obj.sensor_id.short_name
        return _sensor_target_obs(obj.sensor_id)

    def get_target_active(self, obj):
        return obj.sensor_id.active if obj.sensor_id else None

    def get_source_active(self, obj):
        return obj.active


class PlatformSourceConfigurationSerializer(serializers.ModelSerializer):
    platform_handle = serializers.CharField(source="platform_id.platform_handle")
    short_name = serializers.CharField(source="platform_id.short_name")
    longitude = serializers.FloatField(source="platform_id.fixed_longitude")
    latitude = serializers.FloatField(source="platform_id.fixed_latitude")
    country_code = serializers.CharField(source="platform_id.country_code")
    neighborhood = serializers.CharField(source="platform_id.neighborhood")
    """
    properties = {
        "external_identifier": serializers.CharField(source="data_source_id.external_identifier"),
        "platform_metadata": {
            "country_code": serializers.CharField(source="platform_id.country_code"),
            "neighborhood": serializers.CharField(source="platform_id.neighborhood")
        }
    }
    """
    observations = serializers.SerializerMethodField()

    class Meta:
        model = PlatformSource
        fields = (
            "platform_handle",
            "latitude",
            "longitude",
            "short_name",
            "external_identifier",
            "country_code",
            "neighborhood",
            "observations",
            "active"
        )

    def get_observations(self, obj):
        observation_maps = getattr(obj, "observation_maps", [])
        observations = list(
            SourceObservationMapConfigurationSerializer(
                observation_maps,
                many=True,
                context=self.context,
            ).data
        )

        mapped_sensor_ids = {
            obs_map.sensor_id.row_id
            for obs_map in observation_maps
            if obs_map.sensor_id
        }

        platform = obj.platform_id
        if not platform:
            return observations

        sensors = getattr(platform, "sensors", None)
        if sensors is None:
            sensors = (
                platform.sensor_set
                .select_related(
                    "m_type_id",
                    "m_type_id__m_scalar_type_id",
                    "m_type_id__m_scalar_type_id__obs_type_id",
                    "m_type_id__m_scalar_type_id__uom_type_id",
                )
                .order_by("s_order")
            )

        for sensor in sensors:
            if sensor.row_id in mapped_sensor_ids:
                continue

            observations.append({
                "source_obs": None,
                "source_uom": None,
                "source_active": 0,
                "target_obs": _sensor_target_obs(sensor),
                "target_uom": _sensor_target_uom(sensor),
                "target_active": sensor.active,
                "sensor_id": sensor.row_id,
                "m_type_id": _sensor_m_type_id(sensor),
                "s_order": sensor.s_order,
            })

        observations.sort(
            key=lambda observation: (
                observation["s_order"] is None,
                observation["s_order"] or 0,
                observation["source_obs"] or "",
                observation["target_obs"] or "",
            )
        )
        return observations



class ObservationsRequestSerializer(serializers.Serializer):
    platform_handle = serializers.CharField(required=True, allow_blank=False)
    start_date = serializers.DateTimeField(required=True, format=None)
    end_date = serializers.DateTimeField(required=True, format=None)
    observations = serializers.CharField(required=True, allow_blank=False)

    def validate_platform_handle(self, value):
        if not Platform.objects.filter(platform_handle=value).exists():
            raise serializers.ValidationError("Unknown platform_handle.")

        return value

    def validate_observations(self, value):
        observations = [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

        observations = list(dict.fromkeys(observations))

        if not observations:
            raise serializers.ValidationError("At least one observation is required.")


        return observations

    def validate(self, attrs):
        platform_handle = attrs["platform_handle"]
        observations = attrs["observations"]

        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError(
                {"end_date": "end_date must be after start_date."}
            )

        available_observations = set(
            Sensor.objects.filter(
                platform_id__platform_handle=platform_handle,
                m_type_id__m_scalar_type_id__obs_type_id__standard_name__in=observations,
            ).values_list(
                "m_type_id__m_scalar_type_id__obs_type_id__standard_name",
                flat=True,
            )
        )

        missing_observations = [
            observation
            for observation in observations
            if observation not in available_observations
        ]

        if missing_observations:
            raise serializers.ValidationError(
                {
                    "observations": (
                        "Observations not available for this platform: "
                        f"{', '.join(missing_observations)}"
                    )
                }
            )

        return attrs
