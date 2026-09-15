import os
import logging
import pendulum
from typing import Any, List, Dict
from pathlib import Path

from airflow.sdk import dag, task, Variable
from airflow.utils.email import send_email
import pandas as pd
from datetime import datetime
import pytz
from packages.django_setup import setup_django, close_django_connections
from mako.template import Template
from mako import exceptions as makoExceptions

from platforms_app.models import Platform_status

logger = logging.getLogger(__name__)
logger.setLevel(logging.NOTSET)


output_template = Template("""
    <html lang='en'>
        <head>
          <meta name='viewport' content='width=device-width, initial-scale=1'>

          <title>CCRAB Stale or Missing Data Report</title>
        </head>
        <body>
            <h1>CCRAB Stale or Missing Data Report</h1>
            <p>This report was generated on ${run_date}</p>
            <table>
                <tr>
                    <th>Platform</th>
                    <th>Last Reported</th>
                </tr>
                % for site_data in site_data_list:
                <tr>
                    <td>${site_data['short_name']}</td>
                    <td>${site_data['last_reported']}</td>
                </tr>
                % endfor
            </table>
        </body>
    </html>
""")



#remote_debug = os.getenv("AIRFLOW_REMOTE_DEBUG", "False")
remote_debug = "True"
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
        try:
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
            for index, row in df.iterrows():
                logger.info(f"{row['platform_handle']} last reported: {row['latest_m_date']}")
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
                alert_recipients=F(
                    "platformsource__data_source_id__alert_recipients"
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
                "alert_recipients",
            )
            )
            # Fetch all existing incidents in one query rather than once per platform.
            platform_ids = []
            logger.info(f"{len(monitored_platforms)} platforms have stale data.")
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

        except Exception as e:
            raise e
        finally:
            close_django_connections()
        return {'timestamp': now_time.timestamp(), 'output_file': str(output_file)}
    @task()
    def send_alerts(**context):
        logger.info("Beginning the send_alerts task")

        def write_output_file(output_file_name: Path, run_date: datetime, site_data_list: []):
            try:
                with open(output_file_name, 'w') as report_out_file:
                    results_report = output_template.render(run_date=run_date.strftime("%Y-%m-%d %H:%M"),
                                                            site_data_list=site_data_list)
                    report_out_file.write(results_report)
                    return results_report
            except TypeError as e:
                logger.exception(makoExceptions.text_error_template().render())
            except (IOError, AttributeError, Exception) as e:
                logger.exception(e)
            return None

        def send_email_alert(run_date: datetime, alert_report: str):
            SMTP_USER = os.environ.get("AIRFLOW__SMTP__SMTP_USER")

            send_email(
                to="ChiefDan@gmail.com",
                subject=f"CCRAB Stale or Missing Data Report for {run_date.strftime('%Y-%m-%d %H:%M')}",
                html_content=alert_report
            )
        def get_alerts() -> List[Any]:
            alert_list = (
                Platform_status.objects
                .filter(
                    status__in=[
                        Platform_status.Status.OPEN,
                        Platform_status.Status.ACKNOWLEDGED,
                    ],
                    resolved_at__isnull=True,
                    #last_notified_at__isnull=False,

                    # Only send repeats for active, monitored sources with a repeat interval.
                    platform_id__active=1,
                    platform_id__platformsource__data_source_id__active=1,
                    platform_id__platformsource__data_source_id__freshness_monitoring_enabled=True,
                    #platform_id__platformsource__data_source_id__repeat_alert_after__isnull=False,
                )
                .annotate(
                    data_source_key=F(
                        "platform_id__platformsource__data_source_id__key"
                    ),
                    repeat_alert_after=F(repeat_interval),
                    next_notification_at=ExpressionWrapper(
                        F("last_notified_at") + F(repeat_interval),
                        output_field=DateTimeField(),
                    ),
                )
                .filter(next_notification_at__lte=Now())
                .order_by("next_notification_at")
            )
            return alert_list

        def update_last_notified(alert_id_list: List[int], report_time: datetime):
            updated_count = (
                Platform_status.objects
                .filter(
                    row_id__in=alert_id_list,
                    resolved_at__isnull=True,
                    status__in=[
                        Platform_status.Status.OPEN,
                        Platform_status.Status.ACKNOWLEDGED,
                    ],
                )
                .update(
                    last_notified_at=report_time,
                    notification_count=F("notification_count") + 1,
                    row_update_date=report_time,
                )
            )

        setup_django()
        from platforms_app.models import Platform_status
        from django.db.models import DateTimeField, ExpressionWrapper, F
        from django.db.models.functions import Now


        repeat_interval = (
            "platform_id__platformsource__data_source_id__repeat_alert_after"
        )
        alert_list = []
        try:
            alert_list = get_alerts()
        except Exception as e:
            raise e
        finally:
            report_time = datetime.now(pytz.UTC)
            template_data = []
            alert_ids = []
            send_alerts = False
            for alert in alert_list:
                logger.info(f"Sending alert for {alert.platform_id.platform_handle}")
                if type(alert.last_observation_at) == datetime:
                    last_reported = alert.last_observation_at.strftime("%Y-%m-%d %H:%M:%S")
                elif alert.last_observation_at is None:
                    last_reported = "Never reported"
                else:
                    last_reported = alert.last_observation_at
                template_data.append({'short_name': alert.platform_id.short_name,
                                      'last_reported': last_reported})
                alert_ids.append(alert.row_id)
                send_alerts = True
            #If we're sending alerts, update the last_notified_at field for the open alerts.
            if len(alert_ids):
                update_last_notified(alert_ids, report_time)
            close_django_connections()
            if send_alerts:
                base_directory = (Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / Variable.get("PURPLE_AIR_WORKING_DIRECTORY")
                                  / Variable.get("DATA_FLOW_CHECK"))
                out_filename = base_directory / f"alert_report-{report_time.timestamp()}.html"
                report = write_output_file(out_filename, report_time, template_data)
                send_email_alert(report_time, report)

        return

    latest_records = most_current_record()
    send_alerts()


check_data_flow()
