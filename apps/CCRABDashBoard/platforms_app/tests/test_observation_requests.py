from datetime import datetime, timezone

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import serializers

from platforms_app.models import (
    M_scalar_type,
    M_type,
    Multi_obs,
    Obs_type,
    Platform,
    PlatformSensorDisplay,
    Sensor,
    Uom_type,
)
from platforms_app.serializers import ObservationsRequestSerializer


class ObservationParameterTests(SimpleTestCase):
    def test_parses_orders_and_preserves_distinct_channels(self):
        serializer = ObservationsRequestSerializer()

        self.assertEqual(
            serializer.validate_observations(
                " pm2_5 1,pm2_5 2, pm2_5   01,air_temperature 0 "
            ),
            [("pm2_5", 1), ("pm2_5", 2), ("air_temperature", 0)],
        )

    def test_rejects_missing_or_invalid_orders_and_empty_lists(self):
        serializer = ObservationsRequestSerializer()
        for value in ("pm2_5", "pm2_5 one", "pm2_5 1.5", ", ,", "pm2_5 1,air_temperature"):
            with self.subTest(value=value):
                with self.assertRaises(serializers.ValidationError):
                    serializer.validate_observations(value)


class ObservationRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.platform = Platform.objects.create(
            platform_handle="test.platform",
            fixed_longitude=-80.0,
            fixed_latitude=32.0,
        )
        cls.sensors = {}
        timestamp = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        for name, units in (("pm2_5", "ug/m3"), ("air_temperature", "C")):
            observation = Obs_type.objects.create(standard_name=name)
            uom = Uom_type.objects.create(standard_name=units, display=units)
            scalar_type = M_scalar_type.objects.create(
                obs_type_id=observation,
                uom_type_id=uom,
            )
            measurement_type = M_type.objects.create(m_scalar_type_id=scalar_type)
            for order in (1, 2):
                sensor = Sensor.objects.create(
                    platform_id=cls.platform,
                    m_type_id=measurement_type,
                    s_order=order,
                )
                cls.sensors[(name, order)] = sensor
                PlatformSensorDisplay.objects.create(
                    platform_id=cls.platform,
                    sensor_id=sensor,
                    display=True,
                )
                Multi_obs.objects.create(
                    platform_handle=cls.platform.platform_handle,
                    sensor_id=sensor,
                    m_type_id=measurement_type,
                    m_date=timestamp,
                    m_value=order,
                )

        other_platform = Platform.objects.create(platform_handle="test.other")
        sensor = Sensor.objects.create(
            platform_id=other_platform,
            m_type_id=cls.sensors[("pm2_5", 1)].m_type_id,
            s_order=3,
        )
        PlatformSensorDisplay.objects.create(
            platform_id=other_platform,
            sensor_id=sensor,
            display=True,
        )

    def request_params(self, observations):
        return {
            "platform_handle": self.platform.platform_handle,
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": "2026-01-02T00:00:00Z",
            "observations": observations,
        }

    def test_returns_only_requested_pairs_in_geojson_timeseries(self):
        response = self.client.get(
            reverse("platform_data_request"),
            self.request_params("pm2_5 1,air_temperature 2"),
        )

        self.assertEqual(response.status_code, 200)
        feature = response.json()
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["coordinates"], [-80.0, 32.0])
        document = feature["properties"]["timeseries"]
        columns = document["header"]["columns"]
        values = {}
        for index, column in columns.items():
            values[column["id"]] = document["data"][0]["f"][index]["v"]
        self.assertEqual(values, {"pm2_5 1": 1, "air_temperature 2": 2})

    def test_returns_both_channels_for_the_same_observation(self):
        response = self.client.get(
            reverse("platform_data_request"),
            self.request_params("pm2_5 1,pm2_5 2"),
        )

        self.assertEqual(response.status_code, 200)
        columns = response.json()["properties"]["timeseries"]["header"]["columns"]
        identifiers = set()
        for column in columns.values():
            identifiers.add(column["id"])
        self.assertEqual(identifiers, {"pm2_5 1", "pm2_5 2"})

    def test_rejects_pair_available_only_on_another_platform(self):
        response = self.client.get(
            reverse("platform_data_request"),
            self.request_params("pm2_5 3"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("pm2_5 3", response.json()["observations"][0])

    def test_rejects_hidden_channel_even_when_other_channel_is_available(self):
        PlatformSensorDisplay.objects.filter(
            sensor_id=self.sensors[("pm2_5", 2)],
        ).update(display=False)

        response = self.client.get(
            reverse("platform_data_request"),
            self.request_params("pm2_5 1,pm2_5 2"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("pm2_5 2", response.json()["observations"][0])

    def test_rejects_entry_without_order(self):
        response = self.client.get(
            reverse("platform_data_request"),
            self.request_params("pm2_5"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("observations", response.json())
