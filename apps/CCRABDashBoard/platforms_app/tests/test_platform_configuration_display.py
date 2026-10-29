from django.test import TestCase
from django.urls import reverse

from platforms_app.models import (
    M_scalar_type,
    M_type,
    Obs_type,
    Organization,
    Platform,
    PlatformSensorDisplay,
    Sensor,
    Uom_type,
)


class PlatformConfigurationDisplayTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(short_name="test")
        platform = Platform.objects.create(
            organization_id=organization,
            short_name="PA-01",
            platform_handle="test.pa-01",
        )
        uom = Uom_type.objects.create(standard_name="ug_m3", display="ug/m3")
        observation = Obs_type.objects.create(standard_name="pm2_5")
        scalar_type = M_scalar_type.objects.create(
            obs_type_id=observation,
            uom_type_id=uom,
        )
        measurement_type = M_type.objects.create(
            num_types=1,
            description="PM2.5 / ug/m3",
            m_scalar_type_id=scalar_type,
        )
        self.default_sensor = Sensor.objects.create(
            platform_id=platform,
            short_name="PM2.5 A",
            m_type_id=measurement_type,
            s_order=1,
        )
        self.hidden_sensor = Sensor.objects.create(
            platform_id=platform,
            short_name="PM2.5 B",
            m_type_id=measurement_type,
            s_order=2,
        )
        PlatformSensorDisplay.objects.create(
            platform_id=platform,
            sensor_id=self.hidden_sensor,
            display=False,
        )

    def test_sensor_display_uses_override_and_defaults_to_true(self):
        response = self.client.get(
            reverse("platform-configuration-api"),
            {"short_name": "PA-01"},
        )

        self.assertEqual(response.status_code, 200)
        sensors = response.json()["properties"]["sensors"]
        display_by_sensor = {}
        for sensor in sensors:
            display_by_sensor[sensor["short_name"]] = sensor["display"]

        self.assertEqual(
            display_by_sensor,
            {
                "PM2.5 A": True,
                "PM2.5 B": False,
            },
        )
