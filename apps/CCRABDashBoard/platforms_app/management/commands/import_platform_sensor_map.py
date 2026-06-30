import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from ._sensor_map_import_processor import (
    SensorMapImportError,
    SensorMapImportProcessor,
    SensorMapImportSummary,
)
from ._sensor_map_import_readers import (
    SensorMapReaderError,
    build_sensor_map_reader,
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
            reader = build_sensor_map_reader(
                input_type=options["input_type"],
                file_path=options.get("file"),
                sheet=options.get("sheet"),
                sheet_id=options.get("sheet_id"),
                gid=options.get("gid"),
                google_sheet_url=options.get("google_sheet_url"),
            )
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
