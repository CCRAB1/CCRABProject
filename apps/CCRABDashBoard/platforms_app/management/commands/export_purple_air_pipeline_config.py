import json
from pathlib import Path
import json
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch
from django.db.models import F

from platforms_app.models import (
    Organization,
    Platform,
    Sensor,
    M_type,
    M_scalar_type,
    Obs_type,
    Uom_type,
    DataSource,
    PlatformSource,
    SourceObservationMap,
)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Export PurpleAir Airflow config from database tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Path to write purple_air_config.json",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print generated config instead of writing it.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])

        try:
            config = {
                "organizations": {}
            }

            observation_qs = (
                SourceObservationMap.objects
                .select_related(
                    "sensor_id",
                    "sensor_id__m_type_id",
                    "sensor_id__m_type_id__m_scalar_type_id",
                    "sensor_id__m_type_id__m_scalar_type_id__obs_type_id",
                    "sensor_id__m_type_id__m_scalar_type_id__uom_type_id",
                )
                .filter(active=1)
                .order_by("sensor_id__s_order", "source_obs")
            )

            platform_sources = (
                PlatformSource.objects
                .select_related(
                    "data_source_id",
                    "platform_id",
                    "platform_id__organization_id",
                )
                .prefetch_related(
                    Prefetch(
                        "sourceobservationmap_set",
                        queryset=observation_qs,
                        to_attr="observation_maps",
                    )
                )
                .filter(
                    data_source_id__key="purple_air",
                    data_source_id__active=1,
                    active=1,
                    platform_id__active=1,
                )
                .order_by(
                    "platform_id__organization_id__row_id",
                    "platform_id__platform_handle",
                )
            )
            current_org_id = None
            for platform_source in platform_sources:
                platform = platform_source.platform_id
                organization = platform.organization_id
                # We want to separate organizations.
                if current_org_id != organization.row_id:
                    current_org_id = organization.row_id
                    config["organizations"][current_org_id] = {}

                config["organizations"][current_org_id] = {
                        "short_name": organization.short_name,
                        "long_name": organization.long_name,
                        "platforms": []
                    }

                observations = []
                for obs_map in platform_source.observation_maps:
                    sensor = obs_map.sensor_id
                    scalar_type = sensor.m_type_id.m_scalar_type_id

                    platforms = config["organizations"][current_org_id]["platforms"]
                    #BUild the source obs/uom to database obs and uom. We add the sensor_id and
                    #m_type_id to aid in saving the records so we don't have to do the lookups on
                    #the data processing end.
                    observations.append({
                        "source_obs": obs_map.source_obs,
                        "source_uom": obs_map.source_uom,
                        "target_obs": scalar_type.obs_type_id.standard_name,
                        "target_uom": scalar_type.uom_type_id.standard_name,
                        "sensor_id": sensor.row_id,
                        "m_type_id": sensor.m_type_id.row_id,
                        "s_order": sensor.s_order,
                    })
                    platform.append(observations)

            if options["dry_run"]:
                self.stdout.write(json.dumps(config, indent=2))
                return

            output_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {output_path}"))

        except Exception as exc:
            logger.exception(exc)
            raise CommandError(str(exc)) from exc
