import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from platforms_app.models import (
    DataSource,
    M_scalar_type,
    M_type,
    Obs_type,
    Platform,
    PlatformSource,
    Sensor,
    SourceObservationMap,
    Uom_type,
)

from ._sensor_map_import_readers import NormalizedSensorMapRecord

logger = logging.getLogger(__name__)

SENSOR_UNIQUE_CONSTRAINT_NAME = "uq_sensor_platform_m_type_s_order"


class SensorMapImportError(ValueError):
    pass


class DuplicateTargetSensorError(SensorMapImportError):
    pass


@dataclass(frozen=True)
class SensorMapImportResult:
    status: str
    message: str
    row_number: int
    sensor_id: int | None = None
    platform_source_id: int | None = None
    source_observation_map_id: int | None = None

    @property
    def imported(self) -> bool:
        return self.status == "imported"

    @property
    def skipped(self) -> bool:
        return self.status == "skipped"


@dataclass
class SensorMapImportSummary:
    imported: int = 0
    skipped: int = 0
    failed: int = 0

    def add_result(self, result: SensorMapImportResult):
        if result.imported:
            self.imported += 1
            return

        if result.skipped:
            self.skipped += 1
            return

        self.failed += 1


class SensorMapImportProcessor:
    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run

    def process(
        self,
        record: NormalizedSensorMapRecord,
    ) -> SensorMapImportResult:
        try:
            with transaction.atomic():
                result = self._process_in_transaction(record)

                if self.dry_run:
                    transaction.set_rollback(True)

                return result
        except DuplicateTargetSensorError as exc:
            logger.info(str(exc))
            return SensorMapImportResult(
                status="skipped",
                message=str(exc),
                row_number=record.row_number,
            )

    def _process_in_transaction(
        self,
        record: NormalizedSensorMapRecord,
    ) -> SensorMapImportResult:
        now = timezone.now()
        platform = self.resolve_platform(record)
        obs_type = self.resolve_obs_type(record)
        uom_type = self.resolve_uom_type(record)
        m_type = resolve_m_type(obs_type, uom_type)
        sensor = self.create_sensor(record, platform, m_type, now)
        data_source = self.resolve_data_source(record, now)
        platform_source = self.resolve_platform_source(
            record,
            platform,
            data_source,
            now,
        )
        source_observation_map = self.resolve_source_observation_map(
            record,
            platform_source,
            sensor,
            now,
        )

        return SensorMapImportResult(
            status="imported",
            message=(
                f"Imported row {record.row_number}: sensor {sensor.pk} "
                f"for platform {record.target_platform_handle}"
            ),
            row_number=record.row_number,
            sensor_id=sensor.pk,
            platform_source_id=platform_source.pk,
            source_observation_map_id=source_observation_map.pk,
        )

    def resolve_platform(self, record: NormalizedSensorMapRecord) -> Platform:
        platform = (
            Platform.objects.filter(platform_handle=record.target_platform_handle)
            .order_by("row_id")
            .first()
        )

        if platform is None:
            raise SensorMapImportError(
                f"Row {record.row_number}: target platform does not exist: "
                f"{record.target_platform_handle}"
            )

        return platform

    def resolve_obs_type(self, record: NormalizedSensorMapRecord) -> Obs_type:
        obs_type = (
            Obs_type.objects.filter(standard_name=record.target_obs)
            .order_by("row_id")
            .first()
        )

        if obs_type is not None:
            return obs_type

        return Obs_type.objects.create(
            standard_name=record.target_obs,
            definition=record.target_obs_definition or None,
        )

    def resolve_uom_type(self, record: NormalizedSensorMapRecord) -> Uom_type:
        uom_type = (
            Uom_type.objects.filter(standard_name=record.target_uom)
            .order_by("row_id")
            .first()
        )

        if uom_type is not None:
            return uom_type

        return Uom_type.objects.create(
            standard_name=record.target_uom,
            definition=record.target_uom_definition or None,
            display=record.target_uom_display or record.target_uom,
        )

    def create_sensor(
        self,
        record: NormalizedSensorMapRecord,
        platform: Platform,
        m_type: M_type,
        now,
    ) -> Sensor:
        try:
            return Sensor.objects.create(
                row_entry_date=now,
                row_update_date=now,
                platform_id=platform,
                short_name=record.target_sensor_short_name,
                m_type_id=m_type,
                fixed_z=record.fixed_z,
                active=record.active,
                begin_date=record.begin_date,
                end_date=record.end_date,
                s_order=record.s_order,
            )
        except IntegrityError as exc:
            if is_duplicate_target_sensor_error(exc):
                raise DuplicateTargetSensorError(
                    "Skipping row "
                    f"{record.row_number}: sensor already exists for platform "
                    f"{record.target_platform_handle}, target_obs "
                    f"{record.target_obs}, target_uom {record.target_uom}, "
                    f"s_order {record.s_order}"
                ) from exc

            raise

    def resolve_data_source(
        self,
        record: NormalizedSensorMapRecord,
        now,
    ) -> DataSource:
        data_source = (
            DataSource.objects.filter(key=record.data_source_key)
            .order_by("row_id")
            .first()
        )

        if data_source is not None:
            return data_source

        return DataSource.objects.create(
            row_entry_date=now,
            row_update_date=now,
            key=record.data_source_key,
            name=record.data_source_key,
            active=record.active,
        )

    def resolve_platform_source(
        self,
        record: NormalizedSensorMapRecord,
        platform: Platform,
        data_source: DataSource,
        now,
    ) -> PlatformSource:
        platform_source, created = PlatformSource.objects.get_or_create(
            platform_id=platform,
            data_source_id=data_source,
            external_identifier=record.source_platform_identifier,
            defaults={
                "row_entry_date": now,
                "row_update_date": now,
                "active": record.active,
                "begin_date": record.begin_date,
                "end_date": record.end_date,
                "settings": record.settings,
            },
        )

        if not created:
            platform_source.active = record.active
            platform_source.row_update_date = now
            update_optional_dates(platform_source, record)

            if record.settings is not None:
                platform_source.settings = record.settings

            platform_source.save(
                update_fields=[
                    "active",
                    "begin_date",
                    "end_date",
                    "settings",
                    "row_update_date",
                ]
            )

        return platform_source

    def resolve_source_observation_map(
        self,
        record: NormalizedSensorMapRecord,
        platform_source: PlatformSource,
        sensor: Sensor,
        now,
    ) -> SourceObservationMap:
        source_observation_map, created = SourceObservationMap.objects.get_or_create(
            platform_source_id=platform_source,
            source_obs=record.source_obs,
            source_identifier=record.source_identifier,
            defaults={
                "row_entry_date": now,
                "row_update_date": now,
                "sensor_id": sensor,
                "source_uom": record.source_uom,
                "active": record.active,
                "begin_date": record.begin_date,
                "end_date": record.end_date,
                "settings": record.settings,
            },
        )

        if not created:
            source_observation_map.sensor_id = sensor
            source_observation_map.source_uom = record.source_uom
            source_observation_map.active = record.active
            source_observation_map.row_update_date = now
            update_optional_dates(source_observation_map, record)

            if record.settings is not None:
                source_observation_map.settings = record.settings

            source_observation_map.save(
                update_fields=[
                    "sensor_id",
                    "source_uom",
                    "active",
                    "begin_date",
                    "end_date",
                    "settings",
                    "row_update_date",
                ]
            )

        return source_observation_map


def resolve_m_type(obs_type: Obs_type, uom_type: Uom_type) -> M_type:
    scalar_type = (
        M_scalar_type.objects.filter(
            obs_type_id=obs_type,
            uom_type_id=uom_type,
        )
        .order_by("row_id")
        .first()
    )

    if scalar_type is None:
        scalar_type = M_scalar_type.objects.create(
            obs_type_id=obs_type,
            uom_type_id=uom_type,
        )

    m_type = (
        M_type.objects.filter(
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

    return M_type.objects.create(
        num_types=1,
        description=m_type_description(obs_type, uom_type),
        m_scalar_type_id=scalar_type,
    )


def m_type_description(obs_type: Obs_type, uom_type: Uom_type) -> str:
    obs_label = obs_type.standard_name or f"Observation type {obs_type.pk}"
    uom_label = uom_type.standard_name or f"UOM type {uom_type.pk}"

    if uom_type.display and uom_type.display != uom_label:
        uom_label = f"{uom_label} ({uom_type.display})"

    return f"{obs_label} / {uom_label}"


def update_optional_dates(model_instance, record: NormalizedSensorMapRecord):
    if record.begin_date is not None:
        model_instance.begin_date = record.begin_date

    if record.end_date is not None:
        model_instance.end_date = record.end_date


def is_duplicate_target_sensor_error(exc: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(getattr(exc, "__cause__", None), "diag", None),
        "constraint_name",
        None,
    )

    if constraint_name == SENSOR_UNIQUE_CONSTRAINT_NAME:
        return True

    message = str(exc)

    if SENSOR_UNIQUE_CONSTRAINT_NAME in message:
        return True

    field_names = ("platform_id", "m_type_id", "s_order")
    return all(field_name in message for field_name in field_names)
