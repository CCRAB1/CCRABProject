from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from platforms_app import models
from platforms_app.admin import SensorAdminForm, SensorInline, stamp_row_dates


class SensorAdminFormTests(SimpleTestCase):
    def test_stamp_row_dates_sets_entry_and_update_dates_on_create(self):
        now = timezone.now()
        sensor = models.Sensor(short_name="Temp")

        stamp_row_dates(sensor, is_change=False, now=now)

        self.assertEqual(sensor.row_entry_date, now)
        self.assertEqual(sensor.row_update_date, now)

    def test_stamp_row_dates_preserves_entry_date_and_updates_update_date(self):
        entry_date = timezone.datetime(
            2026,
            1,
            1,
            tzinfo=timezone.get_current_timezone(),
        )
        update_date = timezone.datetime(
            2026,
            2,
            1,
            tzinfo=timezone.get_current_timezone(),
        )
        sensor = models.Sensor(
            row_id=50,
            short_name="Temp",
            row_entry_date=entry_date,
        )

        stamp_row_dates(sensor, is_change=True, now=update_date)

        self.assertEqual(sensor.row_entry_date, entry_date)
        self.assertEqual(sensor.row_update_date, update_date)

    def test_platform_sensor_inline_includes_depth_and_order_fields(self):
        self.assertIn("fixed_z", SensorInline.fields)
        self.assertIn("s_order", SensorInline.fields)

    def test_sensor_form_replaces_m_type_with_observation_and_uom_fields(self):
        form = SensorAdminForm()

        self.assertIn("obs_type_id", form.fields)
        self.assertIn("uom_type_id", form.fields)
        self.assertNotIn("m_type_id", form.fields)

    def test_sensor_form_initializes_observation_and_uom_from_existing_m_type(self):
        obs_type = models.Obs_type(row_id=10, standard_name="air_temperature")
        uom_type = models.Uom_type(row_id=20, standard_name="celsius", display="C")
        scalar_type = models.M_scalar_type(
            row_id=30,
            obs_type_id=obs_type,
            uom_type_id=uom_type,
        )
        m_type = models.M_type(row_id=40, m_scalar_type_id=scalar_type)
        sensor = models.Sensor(row_id=50, short_name="Temp", m_type_id=m_type)

        form = SensorAdminForm(instance=sensor)

        self.assertIs(form.fields["obs_type_id"].initial, obs_type)
        self.assertIs(form.fields["uom_type_id"].initial, uom_type)

    def test_sensor_form_save_assigns_resolved_m_type(self):
        obs_type = models.Obs_type(row_id=10, standard_name="air_temperature")
        uom_type = models.Uom_type(row_id=20, standard_name="celsius", display="C")
        resolved_m_type = models.M_type(row_id=40)
        form = SensorAdminForm(instance=models.Sensor(short_name="Temp"))
        form.cleaned_data = {
            "obs_type_id": obs_type,
            "uom_type_id": uom_type,
        }

        with patch(
            "platforms_app.admin.resolve_m_type_for_sensor_fields",
            return_value=resolved_m_type,
        ):
            sensor = form.save(commit=False)

        self.assertIs(sensor.m_type_id, resolved_m_type)
