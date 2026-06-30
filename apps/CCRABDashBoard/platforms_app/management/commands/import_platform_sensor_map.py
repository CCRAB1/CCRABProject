import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from ._sensor_map_import_processor import (
    SensorMapImportError,
    SensorMapImportProcessor,
    SensorMapImportSummary,
)
from ._sensor_map_import_readers import (
    CsvSensorMapReader,
    ExcelSensorMapReader,
    GoogleSheetSensorMapReader,
    SensorMapReaderError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import platform sensor source mappings from CSV, Excel, or Google Sheets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-type",
            choices=("auto", "csv", "excel", "google-sheet"),
            default="auto",
            help="Input type. Defaults to auto-detecting local files by extension.",
        )
        parser.add_argument(
            "--file",
            help="Local CSV, .xlsx, or .xls file to import.",
        )
        parser.add_argument(
            "--sheet",
            help=(
                "Excel sheet name, or Google Sheet worksheet title for public "
                "sheets."
            ),
        )
        parser.add_argument(
            "--sheet-id",
            help="Google Sheet ID for google-sheet imports.",
        )
        parser.add_argument(
            "--gid",
            help="Google Sheet gid for google-sheet imports.",
        )
        parser.add_argument(
            "--google-sheet-url",
            help="Google Sheet URL or CSV export URL for google-sheet imports.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and process rows inside rolled-back transactions.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Stop on the first invalid or failed row.",
        )

    def handle(self, *args, **options):
        try:
            reader = build_reader(options)
            processor = SensorMapImportProcessor(dry_run=options["dry_run"])
            summary = SensorMapImportSummary()

            for record in reader.iter_records():
                try:
                    result = processor.process(record)
                except SensorMapImportError as exc:
                    summary.failed += 1
                    self.stderr.write(str(exc))

                    if options["strict"]:
                        raise CommandError(str(exc)) from exc

                    continue
                except IntegrityError as exc:
                    summary.failed += 1
                    message = (
                        f"Row {record.row_number}: database integrity error: {exc}"
                    )
                    logger.exception(message)
                    self.stderr.write(message)

                    if options["strict"]:
                        raise CommandError(message) from exc

                    continue

                summary.add_result(result)

                if result.skipped:
                    self.stdout.write(result.message)

            self.stdout.write(
                self.style.SUCCESS(
                    "Import complete"
                    f"{' (dry run)' if options['dry_run'] else ''}: "
                    f"imported={summary.imported}, "
                    f"skipped={summary.skipped}, "
                    f"failed={summary.failed}"
                )
            )
        except SensorMapReaderError as exc:
            raise CommandError(str(exc)) from exc


def build_reader(options):
    input_type = options["input_type"]
    file_path = options.get("file")

    if input_type == "auto":
        input_type = infer_input_type(file_path)

    if input_type == "csv":
        if not file_path:
            raise SensorMapReaderError("CSV imports require --file.")

        return CsvSensorMapReader(file_path)

    if input_type == "excel":
        if not file_path:
            raise SensorMapReaderError("Excel imports require --file.")

        return ExcelSensorMapReader(file_path, sheet_name=options.get("sheet"))

    if input_type == "google-sheet":
        return GoogleSheetSensorMapReader(
            sheet_id=options.get("sheet_id"),
            url=options.get("google_sheet_url"),
            worksheet=options.get("sheet"),
            gid=options.get("gid"),
        )

    raise SensorMapReaderError(f"Unsupported input type: {input_type}")


def infer_input_type(file_path):
    if not file_path:
        raise SensorMapReaderError(
            "--input-type auto requires --file. Use --input-type google-sheet "
            "for Google Sheet imports."
        )

    suffix = Path(file_path).suffix.lower()

    if suffix == ".csv":
        return "csv"

    if suffix in {".xlsx", ".xls"}:
        return "excel"

    raise SensorMapReaderError(
        f"Could not infer input type from extension '{suffix}'. "
        "Pass --input-type explicitly."
    )
