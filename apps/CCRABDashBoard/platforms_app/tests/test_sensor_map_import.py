from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from platforms_app import models
from platforms_app.admin import PlatformSourceAdmin, SensorMapUploadForm
from platforms_app.management.commands._sensor_map_import_readers import (
    GoogleSheetSensorMapReader,
    SensorMapReaderError,
    records_from_csv_text,
)


class SensorMapImportReaderTests(SimpleTestCase):
    def test_csv_records_are_normalized(self):
        csv_text = (
            "target_platform_handle,data_source_key,source_platform_identifier,"
            "source_obs,source_uom,target_sensor_short_name,target_obs,target_uom,"
            "s_order,fixed_z,active,source_identifier,settings_json\n"
            " ccrab.test.air , tsi , device-1 , temp , C , temp_sensor , "
            'air_temperature,degC,1,2.5,yes,,{"quality":"raw"}\n'
        )

        records = list(records_from_csv_text(csv_text))

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.row_number, 2)
        self.assertEqual(record.target_platform_handle, "ccrab.test.air")
        self.assertEqual(record.data_source_key, "tsi")
        self.assertEqual(record.source_platform_identifier, "device-1")
        self.assertEqual(record.source_obs, "temp")
        self.assertEqual(record.source_uom, "C")
        self.assertEqual(record.target_sensor_short_name, "temp_sensor")
        self.assertEqual(record.target_obs, "air_temperature")
        self.assertEqual(record.target_uom, "degC")
        self.assertEqual(record.s_order, 1)
        self.assertEqual(record.fixed_z, 2.5)
        self.assertEqual(record.active, 1)
        self.assertEqual(record.source_identifier, "")
        self.assertEqual(record.settings, {"quality": "raw"})

    def test_csv_requires_source_uom_s_order_fixed_z_and_active(self):
        csv_text = (
            "target_platform_handle,data_source_key,source_platform_identifier,"
            "source_obs,target_sensor_short_name,target_obs,target_uom\n"
            "ccrab.test.air,tsi,device-1,temp,temp_sensor,air_temperature,degC\n"
        )

        with self.assertRaisesRegex(
            SensorMapReaderError,
            "source_uom, s_order, fixed_z, active",
        ):
            list(records_from_csv_text(csv_text))

    def test_google_sheet_reader_builds_worksheet_export_url(self):
        reader = GoogleSheetSensorMapReader(
            sheet_id="sheet123",
            worksheet="Sensor Maps",
        )

        self.assertEqual(
            reader.export_url,
            "https://docs.google.com/spreadsheets/d/sheet123/gviz/tq"
            "?tqx=out:csv&sheet=Sensor%20Maps",
        )

    def test_google_sheet_reader_extracts_sheet_id_from_url(self):
        reader = GoogleSheetSensorMapReader(
            url="https://docs.google.com/spreadsheets/d/sheet123/edit#gid=7",
        )

        self.assertEqual(
            reader.export_url,
            "https://docs.google.com/spreadsheets/d/sheet123/export"
            "?format=csv&gid=7",
        )


class SensorMapAdminUploadTests(SimpleTestCase):
    def test_upload_form_requires_file_for_csv(self):
        form = SensorMapUploadForm(data={"input_type": "csv"})

        self.assertFalse(form.is_valid())
        self.assertIn("Upload a file", str(form.errors))

    def test_upload_form_accepts_csv_upload(self):
        import_file = SimpleUploadedFile(
            "sensor_map.csv",
            b"target_platform_handle\n",
            content_type="text/csv",
        )
        form = SensorMapUploadForm(
            data={"input_type": "csv", "dry_run": "on"},
            files={"import_file": import_file},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_upload_form_accepts_google_sheet_url(self):
        form = SensorMapUploadForm(
            data={
                "input_type": "google-sheet",
                "google_sheet_url": (
                    "https://docs.google.com/spreadsheets/d/sheet123/edit#gid=7"
                ),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_platform_source_admin_exposes_import_url(self):
        model_admin = PlatformSourceAdmin(models.PlatformSource, AdminSite())
        url_names = [url_pattern.name for url_pattern in model_admin.get_urls()]

        self.assertIn("platforms_app_platformsource_import_sensor_map", url_names)
