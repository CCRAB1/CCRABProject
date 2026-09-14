import os
import logging
import pendulum
from typing import Any, List, Dict
from pathlib import Path

from airflow.sdk import dag, task, Variable
import pandas as pd
from datetime import datetime, timedelta, tzinfo
import pytz
from packages.django_setup import setup_django, close_django_connections

logger = logging.getLogger(__name__)
logger.setLevel(logging.NOTSET)

#remote_debug = os.getenv("AIRFLOW_REMOTE_DEBUG", "False")
remote_debug = "False"
if remote_debug == "True":
    import pydevd_pycharm

    logger.info("Attaching debugger")
    pydevd_pycharm.settrace(
        os.getenv("PYDEVD_HOST", "host.docker.internal"),
        port=int(os.getenv("PYDEVD_PORT", "5678")),
        stdout_to_server=True,
        stderr_to_server=True,
        suspend=os.getenv("PYDEVD_SUSPEND", "False").lower() in {"1", "true", "yes"},
    )

default_args = {
    'owner': 'airflow',
    'email': ['ChiefDan@gmail.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'start_date': pendulum.datetime(2026, 1, 1, tz="UTC")
}

@dag(
    dag_id="check_data_flow",
    schedule="*/30 * * * *",
    max_active_runs=1,
    catchup=False,
    tags=["alerts","ccrab"],
    default_args=default_args,
)
def check_data_flow():
    @task()
    def most_current_record(**context) -> Dict[str, Any]:
        unique_run_id = context['run_id']
        logger.info("Query most current records for platforms.")
        now_time = datetime.now(tz=pytz.UTC)
        base_directory = (Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / Variable.get("PURPLE_AIR_WORKING_DIRECTORY")
                          / Variable.get("DATA_FLOW_CHECK"))
        logger.info(f"Base directory: {base_directory}")
        # Make sure out destination directory exists.
        base_directory.mkdir(parents=True, exist_ok=True)

        setup_django()
        from django.db import transaction
        from django.db.models import OuterRef, Subquery, F
        from platforms_app.models import Multi_obs, Platform, Platform_status

        # Correlate each Platform row with its newest non-null observation date.
        # The (platform_handle, m_date) index supports this descending lookup.
        latest_observation = (
            Multi_obs.objects
            .filter(
                platform_handle=OuterRef("platform_handle"),
                m_date__isnull=False,
            )
            .order_by("-m_date")
            .values("m_date")[:1]
        )

        platforms = (
            Platform.objects
            .filter(active=1)
            .annotate(latest_m_date=Subquery(latest_observation))
            .values(
                "row_id",
                "platform_handle",
                "short_name",
                "latest_m_date",
            )
            .order_by("platform_handle")
        )
        df = pd.DataFrame.from_records(platforms)
        output_file = base_directory / f"check_data_flow-{now_time.timestamp()}.csv"
        df.to_csv(output_file, index=False)

        # Start with active Platforms and use PlatformSource only as the bridge
        # to the DataSource that owns the freshness-monitoring policy.
        monitored_platforms = (
            Platform.objects
            .filter(
                active=1,
                platformsource__data_source_id__active=1,
                platformsource__data_source_id__freshness_monitoring_enabled=True,
            )
            .annotate(
                latest_m_date=Subquery(latest_observation),

                # PlatformSource is used only to reach DataSource.
                data_source_row_id=F("platformsource__data_source_id__row_id"),
                data_source_key=F("platformsource__data_source_id__key"),
                stale_after=F("platformsource__data_source_id__stale_after"),
                never_reported_after=F(
                    "platformsource__data_source_id__never_reported_after"
                ),
                repeat_alert_after=F(
                    "platformsource__data_source_id__repeat_alert_after"
                ),
                send_recovery_alert=F(
                    "platformsource__data_source_id__send_recovery_alert"
                ),
            )
            # Returning dictionaries keeps the task payload small and avoids
            # fetching complete Platform and DataSource model instances.
            .values(
                "row_id",
                "platform_handle",
                "short_name",
                "begin_date",
                "row_entry_date",
                "latest_m_date",
                "data_source_row_id",
                "data_source_key",
                "stale_after",
                "never_reported_after",
                "repeat_alert_after",
                "send_recovery_alert",
            )
        )
        # Fetch all existing incidents in one query rather than once per platform.
        platform_ids = []
        for platform_source in monitored_platforms:
            platform_ids.append(platform_source['row_id'])
            logger.info(f"Platform: {platform_source['platform_handle']} is stale, latest_m_date: {platform_source['latest_m_date']}")

        # Lock open incidents while classifying platforms so another task run
        # cannot create or resolve the same incident concurrently.
        with transaction.atomic():
            open_incidents = (
                Platform_status.objects
                .select_for_update()
                .filter(
                    platform_id_id__in=platform_ids,
                    resolved_at__isnull=True,
                )
            )

            # Index incidents by platform for constant-time lookup in the loop.
            incidents_by_platform = {}
            for incident in open_incidents:
                incidents_by_platform[incident.platform_id_id] = incident

            # Accumulate writes so they can be persisted in batches below.
            incidents_to_create = []
            incidents_to_update = []

            for platform_record in monitored_platforms:
                platform_id = platform_record["row_id"]
                latest_m_date = platform_record["latest_m_date"]
                stale_after = platform_record["stale_after"]

                # A source-specific never-reported threshold is optional; when
                # absent, use the normal stale-data threshold.
                never_reported_after = (
                    platform_record["never_reported_after"]
                    or stale_after
                )

                # Preserve the source identity in the incident while incidents
                # remain linked directly to Platform during this implementation.
                data_source_details = {
                    "data_source_id": platform_record["data_source_row_id"],
                    "data_source_key": platform_record["data_source_key"],
                }

                alert_type = None
                threshold = None
                reason = None

                # No timestamp means this active platform has never reported.
                # Its Platform dates establish when the initial grace period began.
                if latest_m_date is None:
                    threshold = never_reported_after

                    monitoring_started_at = (
                        platform_record["begin_date"]
                        or platform_record["row_entry_date"]
                    )

                    grace_period_expired = (
                        monitoring_started_at is None
                        or now_time >= monitoring_started_at + threshold
                    )

                    if grace_period_expired:
                        alert_type = Platform_status.AlertType.NEVER_REPORTED
                        reason = "Active platform has never reported data."

                # Platforms with data become stale once the newest observation
                # falls outside the DataSource's permitted age.
                elif latest_m_date <= now_time - stale_after:
                    threshold = stale_after
                    alert_type = Platform_status.AlertType.STALE
                    reason = (
                        f"Latest observation at {latest_m_date.isoformat()} "
                        f"exceeds the allowed age of {threshold}."
                    )

                incident = incidents_by_platform.get(platform_id)

                if alert_type is not None:
                    if incident is None:
                        # A notification step can use this newly opened incident
                        # as the signal to send the first alert.
                        incidents_to_create.append(
                            Platform_status(
                                # Assign the integer primary key directly.
                                platform_id_id=platform_id,
                                alert_type=alert_type,
                                status=Platform_status.Status.OPEN,
                                opened_at=now_time,
                                last_observation_at=latest_m_date,
                                stale_after=threshold,
                                author="airflow:check_data_flow",
                                reason=reason,
                                details=data_source_details,
                                row_entry_date=now_time,
                                row_update_date=now_time,
                            )
                        )
                    else:
                        # Refresh the existing incident instead of opening a
                        # duplicate on every scheduled DAG run.
                        incident.alert_type = alert_type
                        incident.last_observation_at = latest_m_date
                        incident.stale_after = threshold
                        incident.reason = reason
                        incident.details = data_source_details
                        incident.row_update_date = now_time
                        incidents_to_update.append(incident)

                elif incident is not None:
                    # A platform that no longer violates its policy has recovered.
                    incident.status = Platform_status.Status.RESOLVED
                    incident.resolved_at = now_time
                    incident.last_observation_at = latest_m_date
                    incident.reason = "Data flow resumed."
                    incident.row_update_date = now_time
                    incidents_to_update.append(incident)

            # Keep write volume constant with respect to platform count: at most
            # one bulk insert and one bulk update are issued per task run.
            if incidents_to_create:
                Platform_status.objects.bulk_create(incidents_to_create)

            if incidents_to_update:
                Platform_status.objects.bulk_update(
                    incidents_to_update,
                    fields=[
                        "alert_type",
                        "status",
                        "resolved_at",
                        "last_observation_at",
                        "stale_after",
                        "reason",
                        "details",
                        "row_update_date",
                    ],
                )
        return {'timestamp': now_time.timestamp(), 'output_file': str(output_file)}

    latest_records = most_current_record()



check_data_flow()
