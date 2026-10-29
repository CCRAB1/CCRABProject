from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from platforms_app.admin import DataSourceDisplayAdminForm, PlatformDisplayAdminForm
from platforms_app.models import (
    DataSource,
    DataSourceSensor,
    M_scalar_type,
    M_type,
    Obs_type,
    Organization,
    Platform,
    PlatformSensorDisplay,
    PlatformSource,
    Sensor,
    Uom_type,
    served_sensor_queryset,
)
from platforms_app.serializers import ObservationsRequestSerializer


class SensorDisplayPolicyTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(short_name="test")
        self.source = DataSource.objects.create(key="source-a", name="Source A")
        self.other_source = DataSource.objects.create(
            key="source-b",
            name="Source B",
        )
        self.platform = Platform.objects.create(
            organization_id=organization,
            short_name="Platform A",
            platform_handle="test.platform-a",
        )
        self.other_platform = Platform.objects.create(
            organization_id=organization,
            short_name="Platform B",
            platform_handle="test.platform-b",
        )
        PlatformSource.objects.create(
            platform_id=self.platform,
            data_source_id=self.source,
        )
        PlatformSource.objects.create(
            platform_id=self.other_platform,
            data_source_id=self.other_source,
        )

        uom = Uom_type.objects.create(standard_name="ug_m3", display="ug/m3")
        pm_obs = Obs_type.objects.create(standard_name="pm2_5")
        temp_obs = Obs_type.objects.create(standard_name="air_temperature")
        pm_scalar = M_scalar_type.objects.create(
            obs_type_id=pm_obs,
            uom_type_id=uom,
        )
        temp_scalar = M_scalar_type.objects.create(
            obs_type_id=temp_obs,
            uom_type_id=uom,
        )
        self.pm_type = M_type.objects.create(
            num_types=1,
            description="PM2.5 / ug/m3",
            m_scalar_type_id=pm_scalar,
        )
        self.temp_type = M_type.objects.create(
            num_types=1,
            description="Temperature / degC",
            m_scalar_type_id=temp_scalar,
        )
        self.pm_sensor = Sensor.objects.create(
            platform_id=self.platform,
            short_name="PM2.5",
            m_type_id=self.pm_type,
            s_order=1,
        )
        self.temp_sensor = Sensor.objects.create(
            platform_id=self.platform,
            short_name="Temperature",
            m_type_id=self.temp_type,
            s_order=1,
        )
        self.other_pm_sensor = Sensor.objects.create(
            platform_id=self.other_platform,
            short_name="PM2.5",
            m_type_id=self.pm_type,
            s_order=1,
        )

    def served_sensor_ids(self):
        return set(served_sensor_queryset().values_list("row_id", flat=True))

    def test_data_source_sensor_type_is_the_coarse_default(self):
        DataSourceSensor.objects.create(
            data_source_id=self.source,
            m_type_id=self.pm_type,
        )

        self.assertEqual(self.served_sensor_ids(), {self.pm_sensor.row_id})

    def test_platform_overrides_can_hide_or_show_individual_sensors(self):
        DataSourceSensor.objects.create(
            data_source_id=self.source,
            m_type_id=self.pm_type,
        )
        PlatformSensorDisplay.objects.create(
            platform_id=self.platform,
            sensor_id=self.pm_sensor,
            display=False,
        )
        PlatformSensorDisplay.objects.create(
            platform_id=self.platform,
            sensor_id=self.temp_sensor,
            display=True,
        )

        self.assertEqual(self.served_sensor_ids(), {self.temp_sensor.row_id})

    def test_policy_models_reject_mismatched_parent_records(self):
        invalid_source_default = DataSourceSensor(
            data_source_id=self.other_source,
            m_type_id=self.temp_type,
        )
        with self.assertRaises(ValidationError):
            invalid_source_default.full_clean()

        invalid_platform_override = PlatformSensorDisplay(
            platform_id=self.other_platform,
            sensor_id=self.temp_sensor,
            display=True,
        )
        with self.assertRaises(ValidationError):
            invalid_platform_override.full_clean()

    def test_observation_validation_uses_effective_display_policy(self):
        DataSourceSensor.objects.create(
            data_source_id=self.source,
            m_type_id=self.pm_type,
        )
        now = timezone.now()
        serializer = ObservationsRequestSerializer(
            data={
                "platform_handle": self.platform.platform_handle,
                "start_date": (now - timedelta(hours=1)).isoformat(),
                "end_date": now.isoformat(),
                "observations": "air_temperature 1",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("observations", serializer.errors)

        PlatformSensorDisplay.objects.create(
            platform_id=self.platform,
            sensor_id=self.temp_sensor,
            display=True,
        )
        serializer = ObservationsRequestSerializer(data=serializer.initial_data)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_data_source_admin_dual_list_synchronizes_defaults(self):
        form = DataSourceDisplayAdminForm(
            instance=self.source,
            data={
                "key": self.source.key,
                "name": self.source.name,
                "display_sensors": [self.pm_type.pk],
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(
            set(
                DataSourceSensor.objects.filter(
                    data_source_id=self.source,
                ).values_list("m_type_id", flat=True)
            ),
            {self.pm_type.pk},
        )

        form = DataSourceDisplayAdminForm(instance=self.source)
        self.assertEqual(
            set(form.fields["display_sensors"].queryset),
            {self.pm_type, self.temp_type},
        )
        self.assertEqual(
            set(form.fields["display_sensors"].initial),
            {self.pm_type.pk},
        )

    def test_platform_admin_dual_list_saves_only_policy_overrides(self):
        DataSourceSensor.objects.create(
            data_source_id=self.source,
            m_type_id=self.pm_type,
        )
        form = PlatformDisplayAdminForm(
            instance=self.platform,
            data={
                "short_name": self.platform.short_name,
                "platform_handle": self.platform.platform_handle,
                "display_sensors": [self.temp_sensor.pk],
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(
            dict(
                PlatformSensorDisplay.objects.filter(
                    platform_id=self.platform,
                ).values_list("sensor_id", "display")
            ),
            {
                self.pm_sensor.pk: False,
                self.temp_sensor.pk: True,
            },
        )

        form = PlatformDisplayAdminForm(instance=self.platform)
        self.assertEqual(
            set(form.fields["display_sensors"].initial),
            {self.temp_sensor.pk},
        )
