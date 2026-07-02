import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q
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
PLATFORM_SOURCE_PLATFORM_UNIQUE_CONSTRAINT_NAME = "unique_platform_source_platform_id"


class SensorMapImportError(ValueError):
    pass


@dataclass(frozen=True)
class SensorResolution:
    sensor: Sensor
    created: bool


@dataclass(frozen=True)
class SourceObservationMapResolution:
    source_observation_map: SourceObservationMap
    created: bool
    updated: bool


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
        with transaction.atomic():
            result = self._process_in_transaction(record)

            if self.dry_run:
                transaction.set_rollback(True)

            return result

    def _process_in_transaction(
        self,
        record: NormalizedSensorMapRecord,
    ) -> SensorMapImportResult:
        now = timezone.now()
        platform = self.resolve_platform(record)
        obs_type = self.resolve_obs_type(record)
        uom_type = self.resolve_uom_type(record)
        m_type = resolve_m_type(obs_type, uom_type)
        sensor_resolution = self.resolve_sensor(record, platform, m_type, now)
        data_source = self.resolve_data_source(record, now)
        platform_source = self.resolve_platform_source(
            record,
            platform,
            data_source,
            now,
        )
        source_map_resolution = self.resolve_source_observation_map(
            record,
            platform_source,
            sensor_resolution.sensor,
            now,
        )
        status = result_status(sensor_resolution, source_map_resolution)

        return SensorMapImportResult(
            status=status,
            message=import_result_message(
                record,
                sensor_resolution,
                source_map_resolution,
            ),
            row_number=record.row_number,
            sensor_id=sensor_resolution.sensor.pk,
            platform_source_id=platform_source.pk,
            source_observation_map_id=(
                source_map_resolution.source_observation_map.pk
            ),
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

    def resolve_sensor(
        self,
        record: NormalizedSensorMapRecord,
        platform: Platform,
        m_type: M_type,
        now,
    ) -> SensorResolution:
        try:
            with transaction.atomic():
                sensor = Sensor.objects.create(
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
                sensor = (
                    Sensor.objects.filter(
                        platform_id=platform,
                        m_type_id=m_type,
                        s_order=record.s_order,
                    )
                    .order_by("row_id")
                    .first()
                )

                if sensor is None:
                    raise SensorMapImportError(
                        "Could not resolve existing sensor after duplicate "
                        f"constraint for row {record.row_number}."
                    ) from exc

                logger.info(
                    "Reusing existing sensor %s for row %s.",
                    sensor.pk,
                    record.row_number,
                )
                return SensorResolution(sensor=sensor, created=False)

            raise

        return SensorResolution(sensor=sensor, created=True)

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
        platform_source = (
            PlatformSource.objects.filter(
                platform_id=platform,
                data_source_id=data_source,
                external_identifier=record.source_platform_identifier,
            )
            .order_by("row_id")
            .first()
        )
        created = False

        if platform_source is None:
            try:
                with transaction.atomic():
                    platform_source = PlatformSource.objects.create(
                        row_entry_date=now,
                        row_update_date=now,
                        platform_id=platform,
                        data_source_id=data_source,
                        external_identifier=record.source_platform_identifier,
                        active=record.active,
                        begin_date=record.begin_date,
                        end_date=record.end_date,
                        settings=record.settings,
                    )
                    created = True
            except IntegrityError as exc:
                if is_duplicate_platform_source_error(exc):
                    platform_source = (
                        PlatformSource.objects.filter(platform_id=platform)
                        .order_by("row_id")
                        .first()
                    )

                    if platform_source is None:
                        raise SensorMapImportError(
                            "Could not resolve existing platform source after "
                            "duplicate constraint for row "
                            f"{record.row_number}."
                        ) from exc

                    logger.info(
                        "Reusing existing platform source %s for row %s.",
                        platform_source.pk,
                        record.row_number,
                    )
                else:
                    raise

        if not created:
            update_fields = []
            update_model_field(
                platform_source,
                update_fields,
                "active",
                record.active,
            )
            update_optional_dates(platform_source, record, update_fields)
            fill_blank_platform_source_identity(
                platform_source,
                update_fields,
                record,
                data_source,
            )

            if record.settings is not None:
                update_model_field(
                    platform_source,
                    update_fields,
                    "settings",
                    record.settings,
                )

            if update_fields:
                platform_source.row_update_date = now
                update_fields.append("row_update_date")
                platform_source.save(update_fields=update_fields)

        return platform_source

    def resolve_source_observation_map(
        self,
        record: NormalizedSensorMapRecord,
        platform_source: PlatformSource,
        sensor: Sensor,
        now,
    ) -> SourceObservationMapResolution:
        source_observation_map = find_source_observation_map(
            record,
            platform_source,
        )
        created = False

        if source_observation_map is None:
            source_observation_map = SourceObservationMap.objects.create(
                row_entry_date=now,
                row_update_date=now,
                platform_source_id=platform_source,
                sensor_id=sensor,
                source_obs=record.source_obs,
                source_uom=record.source_uom,
                source_identifier=record.source_identifier,
                active=record.active,
                begin_date=record.begin_date,
                end_date=record.end_date,
                settings=record.settings,
            )
            created = True

        if not created:
            update_fields = []
            update_model_field(
                source_observation_map,
                update_fields,
                "sensor_id",
                sensor,
            )
            update_model_field(
                source_observation_map,
                update_fields,
                "source_uom",
                record.source_uom,
            )
            update_model_field(
                source_observation_map,
                update_fields,
                "active",
                record.active,
            )
            update_optional_dates(source_observation_map, record, update_fields)

            if record.settings is not None:
                update_model_field(
                    source_observation_map,
                    update_fields,
                    "settings",
                    record.settings,
                )

            if update_fields:
                source_observation_map.row_update_date = now
                update_fields.append("row_update_date")
                source_observation_map.save(update_fields=update_fields)

            return SourceObservationMapResolution(
                source_observation_map=source_observation_map,
                created=False,
                updated=bool(update_fields),
            )

        return SourceObservationMapResolution(
            source_observation_map=source_observation_map,
            created=True,
            updated=False,
        )


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


def result_status(
    sensor_resolution: SensorResolution,
    source_map_resolution: SourceObservationMapResolution,
) -> str:
    if (
        sensor_resolution.created
        or source_map_resolution.created
        or source_map_resolution.updated
    ):
        return "imported"

    return "skipped"


def import_result_message(
    record: NormalizedSensorMapRecord,
    sensor_resolution: SensorResolution,
    source_map_resolution: SourceObservationMapResolution,
) -> str:
    sensor_action = "created sensor"

    if not sensor_resolution.created:
        sensor_action = "reused existing sensor"

    if source_map_resolution.created:
        map_action = "created source observation map"
    elif source_map_resolution.updated:
        map_action = "updated source observation map"
    else:
        map_action = "source observation map already existed"

    verb = "Imported"

    if not (
        sensor_resolution.created
        or source_map_resolution.created
        or source_map_resolution.updated
    ):
        verb = "Skipping"

    return (
        f"{verb} row {record.row_number}: {sensor_action} "
        f"{sensor_resolution.sensor.pk} and {map_action} "
        f"{source_map_resolution.source_observation_map.pk} "
        f"for platform {record.target_platform_handle}"
    )


def update_optional_dates(
    model_instance,
    record: NormalizedSensorMapRecord,
    update_fields=None,
):
    if record.begin_date is not None:
        update_model_field(
            model_instance,
            update_fields,
            "begin_date",
            record.begin_date,
        )

    if record.end_date is not None:
        update_model_field(
            model_instance,
            update_fields,
            "end_date",
            record.end_date,
        )


def update_model_field(model_instance, update_fields, field_name, value):
    if getattr(model_instance, field_name) == value:
        return

    setattr(model_instance, field_name, value)

    if update_fields is not None:
        update_fields.append(field_name)


def fill_blank_platform_source_identity(
    platform_source: PlatformSource,
    update_fields,
    record: NormalizedSensorMapRecord,
    data_source: DataSource,
):
    if platform_source.data_source_id_id is None:
        update_model_field(
            platform_source,
            update_fields,
            "data_source_id",
            data_source,
        )

    if not platform_source.external_identifier:
        update_model_field(
            platform_source,
            update_fields,
            "external_identifier",
            record.source_platform_identifier,
        )


def find_source_observation_map(
    record: NormalizedSensorMapRecord,
    platform_source: PlatformSource,
) -> SourceObservationMap | None:
    queryset = SourceObservationMap.objects.filter(
        platform_source_id=platform_source,
        source_obs=record.source_obs,
    )

    if record.source_identifier:
        exact_identifier_match = (
            queryset.filter(source_identifier=record.source_identifier)
            .order_by("row_id")
            .first()
        )

        if exact_identifier_match is not None:
            return exact_identifier_match
    else:
        blank_identifier_match = (
            queryset.filter(
                Q(source_identifier__isnull=True) | Q(source_identifier="")
            )
            .order_by("row_id")
            .first()
        )

        if blank_identifier_match is not None:
            return blank_identifier_match

    uom_match = (
        queryset.filter(source_uom=record.source_uom)
        .order_by("row_id")
        .first()
    )

    if uom_match is not None:
        return uom_match

    candidates = list(queryset.order_by("row_id")[:2])

    if len(candidates) == 1:
        return candidates[0]

    return None


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


def is_duplicate_platform_source_error(exc: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(getattr(exc, "__cause__", None), "diag", None),
        "constraint_name",
        None,
    )

    if constraint_name == PLATFORM_SOURCE_PLATFORM_UNIQUE_CONSTRAINT_NAME:
        return True

    message = str(exc)

    if PLATFORM_SOURCE_PLATFORM_UNIQUE_CONSTRAINT_NAME in message:
        return True

    return "platform_source" in message and "platform_id" in message
