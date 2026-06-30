import csv
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

REQUIRED_COLUMNS = (
    # Existing target platform lookup; maps to Platform.platform_handle.
    "target_platform_handle",
    # Source system lookup/create key; maps to DataSource.key.
    "data_source_key",
    # Source platform/device/station id; maps to PlatformSource.external_identifier.
    "source_platform_identifier",
    # Source observation name from incoming data.
    # Maps to SourceObservationMap.source_obs.
    "source_obs",
    # Source unit from incoming data; maps to SourceObservationMap.source_uom.
    "source_uom",
    # Target sensor label; maps to Sensor.short_name.
    "target_sensor_short_name",
    # Target observation name; maps to Obs_type.standard_name.
    "target_obs",
    # Target unit name; maps to Uom_type.standard_name.
    "target_uom",
    # Sensor order for this platform/m_type; maps to Sensor.s_order.
    "s_order",
    # Sensor fixed vertical position/depth; maps to Sensor.fixed_z.
    "fixed_z",
    # Active flag for created mappings.
    # Maps to Sensor.active, PlatformSource.active, and SourceObservationMap.active.
    "active",
)

OPTIONAL_COLUMNS = (
    # Source-side disambiguator for repeated source observations.
    # Maps to SourceObservationMap.source_identifier.
    "source_identifier",
    # Target observation description.
    # Maps to Obs_type.definition when creating a new target obs.
    "target_obs_definition",
    # Target unit display label.
    # Maps to Uom_type.display when creating a new target uom.
    "target_uom_display",
    # Target unit description.
    # Maps to Uom_type.definition when creating a new target uom.
    "target_uom_definition",
    # Optional mapping/sensor start date.
    # Maps to Sensor.begin_date, PlatformSource.begin_date,
    # and SourceObservationMap.begin_date.
    "begin_date",
    # Optional mapping/sensor end date.
    # Maps to Sensor.end_date, PlatformSource.end_date,
    # and SourceObservationMap.end_date.
    "end_date",
    # Optional JSON settings object.
    # Maps to PlatformSource.settings and SourceObservationMap.settings.
    "settings_json",
)

GOOGLE_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([^/]+)")


class SensorMapReaderError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedSensorMapRecord:
    row_number: int
    target_platform_handle: str
    data_source_key: str
    source_platform_identifier: str
    source_obs: str
    source_uom: str
    target_sensor_short_name: str
    target_obs: str
    target_uom: str
    s_order: int
    fixed_z: float
    active: int
    source_identifier: str = ""
    target_obs_definition: str = ""
    target_uom_display: str = ""
    target_uom_definition: str = ""
    begin_date: datetime | None = None
    end_date: datetime | None = None
    settings: dict[str, Any] | None = None


class CsvSensorMapReader:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def iter_records(self):
        with self.path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            yield from records_from_csv_text(file_obj.read())


class ExcelSensorMapReader:
    def __init__(self, path: str | Path, sheet_name: str | None = None):
        self.path = Path(path)
        self.sheet_name = sheet_name

    def iter_records(self):
        suffix = self.path.suffix.lower()

        if suffix == ".xlsx":
            yield from self._iter_xlsx_records()
            return

        if suffix == ".xls":
            yield from self._iter_xls_records()
            return

        raise SensorMapReaderError(
            f"Unsupported Excel file extension '{self.path.suffix}'. "
            "Use .xlsx or .xls."
        )

    def _iter_xlsx_records(self):
        try:
            import openpyxl
        except ImportError as exc:
            raise SensorMapReaderError(
                "Reading .xlsx files requires the openpyxl package."
            ) from exc

        workbook = openpyxl.load_workbook(
            self.path,
            read_only=True,
            data_only=True,
        )

        try:
            worksheet = (
                workbook[self.sheet_name] if self.sheet_name else workbook.active
            )
            rows = worksheet.iter_rows(values_only=True)
            header = next(rows, None)

            if header is None:
                return

            fieldnames = normalize_headers(header)
            validate_headers(fieldnames)

            for row_number, values in enumerate(rows, start=2):
                row = dict(zip(fieldnames, values, strict=False))
                if is_blank_row(row):
                    continue

                yield normalize_sensor_map_row(row, row_number)
        finally:
            workbook.close()

    def _iter_xls_records(self):
        try:
            import xlrd
        except ImportError as exc:
            raise SensorMapReaderError(
                "Reading .xls files requires the xlrd package."
            ) from exc

        workbook = xlrd.open_workbook(str(self.path))
        worksheet = (
            workbook.sheet_by_name(self.sheet_name)
            if self.sheet_name
            else workbook.sheet_by_index(0)
        )

        if worksheet.nrows == 0:
            return

        fieldnames = normalize_headers(worksheet.row_values(0))
        validate_headers(fieldnames)

        for row_index in range(1, worksheet.nrows):
            row_number = row_index + 1
            values = worksheet.row_values(row_index)
            row = dict(zip(fieldnames, values, strict=False))

            if is_blank_row(row):
                continue

            yield normalize_sensor_map_row(row, row_number)


class GoogleSheetSensorMapReader:
    def __init__(
        self,
        *,
        sheet_id: str | None = None,
        url: str | None = None,
        worksheet: str | None = None,
        gid: str | None = None,
        timeout_seconds: int = 30,
    ):
        self.sheet_id = sheet_id
        self.url = url
        self.worksheet = worksheet
        self.gid = gid
        self.timeout_seconds = timeout_seconds

    def iter_records(self):
        try:
            response = requests.get(
                self.export_url,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SensorMapReaderError(
                f"Could not read Google Sheet CSV export: {exc}"
            ) from exc

        yield from records_from_csv_text(response.text)

    @property
    def export_url(self):
        if self.url and ("format=csv" in self.url or "output=csv" in self.url):
            return self.url

        sheet_id = self.sheet_id or sheet_id_from_url(self.url)

        if not sheet_id:
            raise SensorMapReaderError(
                "Google Sheet imports require --sheet-id or --google-sheet-url."
            )

        if self.worksheet:
            worksheet = quote(self.worksheet)
            return (
                f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
                f"?tqx=out:csv&sheet={worksheet}"
            )

        query = {"format": "csv"}

        gid = self.gid or gid_from_url(self.url)

        if gid:
            query["gid"] = gid

        return (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?"
            f"{urlencode(query)}"
        )


def records_from_csv_text(csv_text: str):
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = normalize_headers(reader.fieldnames or ())
    validate_headers(fieldnames)
    reader.fieldnames = fieldnames

    for row_number, row in enumerate(reader, start=2):
        if is_blank_row(row):
            continue

        yield normalize_sensor_map_row(row, row_number)


def normalize_sensor_map_row(
    row: dict[str, Any],
    row_number: int,
) -> NormalizedSensorMapRecord:
    cleaned = {key: clean_string(value) for key, value in row.items() if key}
    missing_values = [
        column for column in REQUIRED_COLUMNS if not cleaned.get(column)
    ]

    if missing_values:
        raise SensorMapReaderError(
            f"Row {row_number} is missing required values: "
            f"{', '.join(missing_values)}"
        )

    return NormalizedSensorMapRecord(
        row_number=row_number,
        target_platform_handle=cleaned["target_platform_handle"],
        data_source_key=cleaned["data_source_key"],
        source_platform_identifier=cleaned["source_platform_identifier"],
        source_obs=cleaned["source_obs"],
        source_uom=cleaned["source_uom"],
        target_sensor_short_name=cleaned["target_sensor_short_name"],
        target_obs=cleaned["target_obs"],
        target_uom=cleaned["target_uom"],
        s_order=parse_int(cleaned["s_order"], "s_order", row_number),
        fixed_z=parse_float(cleaned["fixed_z"], "fixed_z", row_number),
        active=parse_active(cleaned["active"], row_number),
        source_identifier=cleaned.get("source_identifier", ""),
        target_obs_definition=cleaned.get("target_obs_definition", ""),
        target_uom_display=cleaned.get("target_uom_display", ""),
        target_uom_definition=cleaned.get("target_uom_definition", ""),
        begin_date=parse_optional_datetime(
            row.get("begin_date"),
            "begin_date",
            row_number,
        ),
        end_date=parse_optional_datetime(row.get("end_date"), "end_date", row_number),
        settings=parse_optional_json(row.get("settings_json"), row_number),
    )


def normalize_headers(headers) -> list[str]:
    return [clean_string(header).lower() for header in headers]


def validate_headers(fieldnames: list[str]):
    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in fieldnames
    ]

    if missing_columns:
        raise SensorMapReaderError(
            "Missing required columns: " + ", ".join(missing_columns)
        )


def is_blank_row(row: dict[str, Any]) -> bool:
    return all(not clean_string(value) for value in row.values())


def clean_string(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def parse_int(value: Any, field_name: str, row_number: int) -> int:
    try:
        number = float(clean_string(value))
    except ValueError as exc:
        raise SensorMapReaderError(
            f"Row {row_number} has invalid integer for {field_name}: {value}"
        ) from exc

    if not number.is_integer():
        raise SensorMapReaderError(
            f"Row {row_number} has invalid integer for {field_name}: {value}"
        )

    return int(number)


def parse_float(value: Any, field_name: str, row_number: int) -> float:
    try:
        return float(clean_string(value))
    except ValueError as exc:
        raise SensorMapReaderError(
            f"Row {row_number} has invalid number for {field_name}: {value}"
        ) from exc


def parse_active(value: Any, row_number: int) -> int:
    if isinstance(value, bool):
        return int(value)

    normalized_value = clean_string(value).lower()

    if normalized_value in {"1", "1.0", "true", "yes", "y", "active"}:
        return 1

    if normalized_value in {"0", "0.0", "false", "no", "n", "inactive"}:
        return 0

    raise SensorMapReaderError(
        f"Row {row_number} has invalid active value: {value}"
    )


def parse_optional_datetime(
    value: Any,
    field_name: str,
    row_number: int,
) -> datetime | None:
    if value is None or clean_string(value) == "":
        return None

    if isinstance(value, datetime):
        parsed_value = value
    elif isinstance(value, date):
        parsed_value = datetime.combine(value, time.min)
    else:
        string_value = clean_string(value)
        parsed_value = parse_datetime(string_value)

        if parsed_value is None:
            parsed_date = parse_date(string_value)
            if parsed_date is not None:
                parsed_value = datetime.combine(parsed_date, time.min)

        if parsed_value is None:
            raise SensorMapReaderError(
                f"Row {row_number} has invalid {field_name}: {value}"
            )

    if timezone.is_naive(parsed_value):
        return timezone.make_aware(parsed_value, timezone.get_current_timezone())

    return parsed_value


def parse_optional_json(value: Any, row_number: int) -> dict[str, Any] | None:
    if value is None or clean_string(value) == "":
        return None

    if isinstance(value, dict):
        return value

    try:
        parsed_value = json.loads(clean_string(value))
    except json.JSONDecodeError as exc:
        raise SensorMapReaderError(
            f"Row {row_number} has invalid settings_json."
        ) from exc

    if not isinstance(parsed_value, dict):
        raise SensorMapReaderError(
            f"Row {row_number} settings_json must be a JSON object."
        )

    return parsed_value


def sheet_id_from_url(url: str | None) -> str | None:
    if not url:
        return None

    match = GOOGLE_SHEET_ID_RE.search(url)

    if not match:
        return None

    return match.group(1)


def gid_from_url(url: str | None) -> str | None:
    if not url:
        return None

    parsed_url = urlparse(url)
    query_values = parse_qs(parsed_url.query)
    fragment_values = parse_qs(parsed_url.fragment)

    for values in (query_values, fragment_values):
        gid = values.get("gid")

        if gid:
            return gid[0]

    return None
