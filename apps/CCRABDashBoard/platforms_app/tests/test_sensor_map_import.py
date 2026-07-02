from contextlib import nullcontext
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import SimpleTestCase
from django.utils import timezone

from platforms_app import models
from platforms_app.admin import PlatformSourceAdmin, SensorMapUploadForm
from platforms_app.management.commands._sensor_map_import_processor import (
    SensorMapImportProcessor,
    SensorResolution,
    SourceObservationMapResolution,
)
from platforms_app.management.commands._sensor_map_import_readers import (
    GoogleSheetSensorMapReader,
    NormalizedSensorMapRecord,
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


class SensorMapImportProcessorTests(SimpleTestCase):
    def test_duplicate_sensor_is_reused(self):
        record = sensor_map_record()
        platform = models.Platform(row_id=10, platform_handle="ccrab.test.air")
        m_type = models.M_type(row_id=20)
        existing_sensor = models.Sensor(
            row_id=30,
            platform_id=platform,
            m_type_id=m_type,
            s_order=1,
        )
        processor = SensorMapImportProcessor()

        with (
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.transaction.atomic",
                return_value=nullcontext(),
            ),
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.Sensor.objects"
            ) as sensor_manager,
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.logger.info"
            ) as logger_info,
        ):
            sensor_manager.create.side_effect = IntegrityError(
                "platform_id m_type_id s_order"
            )
            sensor_query = sensor_manager.filter.return_value
            sensor_query.order_by.return_value.first.return_value = existing_sensor

            resolution = processor.resolve_sensor(
                record,
                platform,
                m_type,
                timezone.now(),
            )

        self.assertIs(resolution.sensor, existing_sensor)
        self.assertFalse(resolution.created)
        logger_info.assert_called_once()

    def test_existing_sensor_with_missing_source_map_is_imported(self):
        record = sensor_map_record()
        platform = models.Platform(row_id=10, platform_handle="ccrab.test.air")
        data_source = models.DataSource(row_id=11, key="tsi")
        platform_source = models.PlatformSource(
            row_id=12,
            platform_id=platform,
            data_source_id=data_source,
            external_identifier="device-1",
        )
        sensor = models.Sensor(row_id=30, platform_id=platform, s_order=1)
        source_map = models.SourceObservationMap(
            row_id=40,
            platform_source_id=platform_source,
            sensor_id=sensor,
            source_obs="temp",
            source_uom="C",
        )
        processor = SensorMapImportProcessor()
        processor.resolve_platform = Mock(return_value=platform)
        processor.resolve_obs_type = Mock(return_value=models.Obs_type(row_id=1))
        processor.resolve_uom_type = Mock(return_value=models.Uom_type(row_id=2))
        processor.resolve_sensor = Mock(
            return_value=SensorResolution(sensor=sensor, created=False)
        )
        processor.resolve_data_source = Mock(return_value=data_source)
        processor.resolve_platform_source = Mock(return_value=platform_source)
        processor.resolve_source_observation_map = Mock(
            return_value=SourceObservationMapResolution(
                source_observation_map=source_map,
                created=True,
                updated=False,
            )
        )

        with patch(
            "platforms_app.management.commands."
            "_sensor_map_import_processor.resolve_m_type",
            return_value=models.M_type(row_id=20),
        ):
            result = processor._process_in_transaction(record)

        self.assertTrue(result.imported)
        self.assertEqual(result.sensor_id, sensor.pk)
        self.assertEqual(result.source_observation_map_id, source_map.pk)
        self.assertIn("reused existing sensor", result.message)
        self.assertIn("created source observation map", result.message)

    def test_duplicate_platform_source_is_reused(self):
        record = sensor_map_record()
        platform = models.Platform(row_id=10, platform_handle="ccrab.test.air")
        data_source = models.DataSource(row_id=11, key="tsi")
        existing_platform_source = models.PlatformSource(
            row_id=12,
            platform_id=platform,
            data_source_id=data_source,
            external_identifier="device-1",
            active=1,
        )
        processor = SensorMapImportProcessor()

        with (
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.transaction.atomic",
                return_value=nullcontext(),
            ),
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.PlatformSource.objects"
            ) as platform_source_manager,
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.logger.info"
            ) as logger_info,
        ):
            exact_query = Mock()
            exact_query.order_by.return_value.first.return_value = None
            fallback_query = Mock()
            fallback_query.order_by.return_value.first.return_value = (
                existing_platform_source
            )
            platform_source_manager.filter.side_effect = [
                exact_query,
                fallback_query,
            ]
            platform_source_manager.create.side_effect = IntegrityError(
                "unique_platform_source_platform_id platform_id"
            )

            platform_source = processor.resolve_platform_source(
                record,
                platform,
                data_source,
                timezone.now(),
            )

        self.assertIs(platform_source, existing_platform_source)
        logger_info.assert_called_once()

    def test_existing_source_observation_map_is_reused(self):
        record = sensor_map_record()
        platform_source = models.PlatformSource(row_id=12)
        sensor = models.Sensor(row_id=30)
        source_map = models.SourceObservationMap(
            row_id=40,
            platform_source_id=platform_source,
            sensor_id=sensor,
            source_obs=record.source_obs,
            source_uom=record.source_uom,
            source_identifier=record.source_identifier,
            active=record.active,
        )
        processor = SensorMapImportProcessor()

        with (
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.find_source_observation_map",
                return_value=source_map,
            ) as find_source_map,
            patch(
                "platforms_app.management.commands."
                "_sensor_map_import_processor.SourceObservationMap.objects"
            ) as source_map_manager,
        ):
            resolution = processor.resolve_source_observation_map(
                record,
                platform_source,
                sensor,
                timezone.now(),
            )

        find_source_map.assert_called_once_with(record, platform_source)
        source_map_manager.create.assert_not_called()
        self.assertIs(resolution.source_observation_map, source_map)
        self.assertFalse(resolution.created)
        self.assertFalse(resolution.updated)


def sensor_map_record():
    return NormalizedSensorMapRecord(
        row_number=2,
        target_platform_handle="ccrab.test.air",
        data_source_key="tsi",
        source_platform_identifier="device-1",
        source_obs="temp",
        source_uom="C",
        target_sensor_short_name="temp_sensor",
        target_obs="air_temperature",
        target_uom="degC",
        s_order=1,
        fixed_z=2.5,
        active=1,
    )
