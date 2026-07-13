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

    class Meta:
        model = Sensor
        fields = (
            'short_name',
            's_order',
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


class SourceObservationMapConfigurationSerializer(serializers.ModelSerializer):
    target_obs = serializers.SerializerMethodField()
    target_uom = serializers.SerializerMethodField()
    sensor_id = serializers.SerializerMethodField()
    m_type_id = serializers.SerializerMethodField()
    s_order = serializers.SerializerMethodField()
    target_active = serializers.IntegerField(source="sensor_id.active", read_only=True)
    source_active = serializers.IntegerField(source="active", read_only=True)

    class Meta:
        model = SourceObservationMap
        fields = (
            "source_obs",
            "source_uom",
            "source_active",
            "target_obs",
            "target_uom",
            "target_active",
            "sensor_id",
            "m_type_id",
            "s_order",
        )

    def get_sensor_id(self, obj):
        return obj.sensor_id.row_id

    def get_m_type_id(self, obj):
        return obj.sensor_id.m_type_id.row_id

    def get_s_order(self, obj):
        return obj.sensor_id.s_order

    def get_target_obs(self, obj):
        scalar_type = obj.sensor_id.m_type_id.m_scalar_type_id
        return scalar_type.obs_type_id.standard_name

    def get_target_uom(self, obj):
        scalar_type = obj.sensor_id.m_type_id.m_scalar_type_id
        return scalar_type.uom_type_id.standard_name


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
    observations = SourceObservationMapConfigurationSerializer(
        source="observation_maps",
        many=True,
        read_only=True,
    )

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