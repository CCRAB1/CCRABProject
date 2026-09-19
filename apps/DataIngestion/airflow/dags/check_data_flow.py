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
            <br>
            <p>The following platforms have not reported within the expected timeframe:</p>
            <table>
                <tr>
                    <th>Platform</th>
                    <th>Last Reported</th>
                </tr>
                % for site_data in site_data_list['opened']:
                <tr>
                    <td>${site_data['short_name']}</td>
                    <td>${site_data['last_reported']}</td>
                </tr>
                % endfor
            </table>
            </br>
            <p>The following platforms have begun reporting again:</p>
            <table>
                <tr>
                    <th>Platform</th>
                    <th>Last Reported</th>
                </tr>
                % for site_data in site_data_list['recovered']:
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
        try:
            unique_run_id = context['run_id']
            logger.info("Query most current records for platforms.")
            now_time = datetime.now(tz=pytz.UTC)
            base_directory = (Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / Variable.get("DATA_FLOW_CHECK"))
            logger.info(f"Base directory: {base_directory}")
            # Make sure out destination directory exists.
            base_directory.mkdir(parents=True, exist_ok=True)

            setup_django()
            from django.db import transaction
            from django.db.models import OuterRef, Subquery, F
            from platforms_app.models import Multi_obs, Platform, Platform_status

            # Build a correlated scalar subquery that returns one timestamp for
            # whichever Platform row is currently being evaluated by an outer
            # query. OuterRef("platform_handle") is replaced with that outer
            # Platform's handle by PostgreSQL. Null dates are excluded explicitly;
            # otherwise a descending PostgreSQL sort can place nulls first. The
            # descending order plus [:1] selects only the newest m_date, and the
            # existing (platform_handle, m_date) index supports this lookup.
            latest_observation = (
                Multi_obs.objects
                .filter(
                    platform_handle=OuterRef("platform_handle"),
                    m_date__isnull=False,
                )
                .order_by("-m_date")
                .values("m_date")[:1]
            )

            # Produce the complete active-platform snapshot used for the CSV.
            # annotate() runs the correlated subquery once per Platform at the
            # database level. values() limits the selected columns and returns
            # dictionaries, which DataFrame.from_records can consume directly.
            # A Platform with no observation is retained with latest_m_date=None.
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

            # Produce the subset of Platforms governed by an enabled freshness
            # policy. The platformsource__data_source_id path performs SQL joins
            # from Platform -> PlatformSource -> DataSource. PlatformSource is
            # used only to identify the DataSource; none of its status, dates, or
            # settings participate in the monitoring decision.
            monitored_platforms = (
                Platform.objects
                .filter(
                    active=1,
                    platformsource__data_source_id__active=1,
                    platformsource__data_source_id__freshness_monitoring_enabled=True,
                )
                # Copy the latest timestamp and the relevant DataSource policy
                # columns onto each Platform result. These F expressions become
                # selected DataSource columns in SQL; they do not issue additional
                # per-platform queries.
                .annotate(
                    latest_m_date=Subquery(latest_observation),

                    # Keep source identity for incident audit details.
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
                # Return dictionaries containing only the fields needed for
                # classification and incident persistence. This avoids constructing
                # complete Platform/DataSource objects and keeps the result compact.
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
            # Extract IDs from the already-evaluated monitored-platform result so
            # all open incidents can be fetched with one platform_id IN (...) query.
            # This avoids an incident query inside the classification loop.
            platform_ids = []
            logger.info(f"{len(monitored_platforms)} platforms have stale data.")
            for platform_source in monitored_platforms:
                platform_ids.append(platform_source['row_id'])
                logger.info(f"Platform: {platform_source['platform_handle']} is stale, latest_m_date: {platform_source['latest_m_date']}")

            # Run incident reads and writes in one transaction. select_for_update()
            # places row-level locks on existing unresolved incidents until the
            # transaction commits, preventing concurrent runs from updating or
            # resolving those same incident rows at the same time.
            with transaction.atomic():
                open_incidents = (
                    Platform_status.objects
                    .select_for_update()
                    .filter(
                        platform_id_id__in=platform_ids,
                        resolved_at__isnull=True,
                    )
                )

                # Convert the incident queryset into a platform_id -> incident map.
                # Classification can then find an existing incident in constant
                # time without issuing another database query.
                incidents_by_platform = {}
                for incident in open_incidents:
                    incidents_by_platform[incident.platform_id_id] = incident

                # Build separate in-memory batches for INSERT and UPDATE. Django
                # will later persist each batch with a single bulk operation.
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

                # Persist all state transitions with at most one bulk INSERT and
                # one bulk UPDATE, regardless of the number of monitored platforms.
                # The partial unique constraint on platform_status also prevents
                # more than one unresolved incident for the same Platform.
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

        setup_django()
        from platforms_app.models import Platform_status
        from django.db.models import DateTimeField, ExpressionWrapper, F, Q
        from django.db.models.functions import Now

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

        def send_email_alert(run_date: datetime, alert_report: str, recipients: []):
            SMTP_USER = os.environ.get("AIRFLOW__SMTP__SMTP_USER")

            send_email(
                to=recipients,
                subject=f"CCRAB Stale or Missing Data Report for {run_date.strftime('%Y-%m-%d %H:%M')}",
                html_content=alert_report
            )
        def get_alerts() -> List[Any]:
            # This relation path reaches the repeat interval configured on the
            # DataSource associated with each incident's Platform. Keeping the
            # path in one variable avoids repeating a long join expression below.
            repeat_interval = (
                "platform_id__platformsource__data_source_id__repeat_alert_after"
            )

            # Query only incidents that are eligible for an email now. Timing is
            # evaluated by PostgreSQL, so Airflow does not need to retrieve every
            # open incident and compare timestamps in Python.
            alert_list = (
                Platform_status.objects
                .filter(
                    # OPEN and ACKNOWLEDGED are both unresolved operational states.
                    # resolved_at is checked as an additional guard and matches the
                    # platform_status database constraint.
                    status__in=[
                        Platform_status.Status.OPEN,
                        Platform_status.Status.ACKNOWLEDGED,
                    ],
                    resolved_at__isnull=True,
                    # Do not alert for inactive Platforms or DataSources, or for a
                    # DataSource whose freshness monitoring has been disabled.
                    platform_id__active=1,
                    platform_id__platformsource__data_source_id__active=1,
                    platform_id__platformsource__data_source_id__freshness_monitoring_enabled=True,
                )
                .annotate(
                    # Include routing and policy values on every returned incident.
                    # recipient_list is already a Python list because the model uses
                    # PostgreSQL ArrayField.
                    data_source_key=F(
                        "platform_id__platformsource__data_source_id__key"
                    ),
                    recipient_list=F("platform_id__platformsource__data_source_id__alert_recipients"),
                    repeat_alert_after=F(repeat_interval),
                    send_recovery_alert=F(
                        "platform_id__platformsource__data_source_id__send_recovery_alert"
                    ),

                    # Calculate the next eligible repeat time in SQL:
                    # last successful notification + configured repeat interval.
                    # If either operand is NULL, next_notification_at is NULL.
                    next_notification_at=ExpressionWrapper(
                        F("last_notified_at") + F(repeat_interval),
                        output_field=DateTimeField(),
                    ),
                )
                .filter(
                    Q(
                        status__in=[
                            Platform_status.Status.OPEN,
                            Platform_status.Status.ACKNOWLEDGED,
                        ],
                        resolved_at__isnull=True,
                    )

                    & (
                        # A NULL last_notified_at identifies an incident that has never
                        # been emailed, so it is immediately eligible for its first alert.
                        Q(last_notified_at__isnull=True)

                        # A previously notified incident is eligible again only when a
                        # repeat interval is configured and its calculated next time has
                        # arrived. The explicit non-null test documents that a blank
                        # repeat_alert_after means "do not send repeat alerts."
                        | Q(
                            repeat_alert_after__isnull=False,
                            next_notification_at__lte=Now(),
                        )
                    )
                        # Resolved incidents needing a recovery notification.
                    | Q(
                        status=Platform_status.Status.RESOLVED,
                        resolved_at__isnull=False,
                        send_recovery_alert=True,
                        last_notified_at__isnull=False,
                        last_notified_at__lt=F("resolved_at"),
                    )

                )
                # Process the most overdue repeat notifications first. Initial
                # alerts have a NULL next_notification_at and are still included by
                # the OR condition above.
                .order_by("next_notification_at")
            )
            logger.info(f"{alert_list.query}")
            return alert_list

        def update_last_notified(alert_id_list: List[int], report_time: datetime):
            # Update the selected incidents after notification processing.
            # Rechecking unresolved state prevents a concurrently resolved incident
            # from being marked as notified after it has recovered.
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
                    # QuerySet.update() generates one SQL UPDATE. F() performs the
                    # increment inside PostgreSQL, avoiding a read/modify/write race
                    # and preserving the correct count across concurrent workers.
                    last_notified_at=report_time,
                    notification_count=F("notification_count") + 1,
                    row_update_date=report_time,
                )
            )
        alert_list = []
        try:
            alert_list = get_alerts()
            logger.info(f"Found {len(alert_list)} active alerts to send alerts for.")
        except Exception as e:
            raise e
        finally:
            report_time = datetime.now(pytz.UTC)
            template_data = {'opened': [], 'recovered': []}
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
                if alert.status == Platform_status.Status.RESOLVED:
                    template_data['recovered'].append({'short_name': alert.platform_id.short_name,
                                                       last_reported: last_reported,})
                else:
                    template_data['opened'].append({'short_name': alert.platform_id.short_name,
                                          'last_reported': last_reported})
                alert_ids.append(alert.row_id)
                send_alerts = True
            #If we're sending alerts, update the last_notified_at field for the open alerts.
            if len(alert_ids):
                logger.info(f"Updating last_notified_at for alert ids: {alert_ids}")
                update_last_notified(alert_ids, report_time)
            close_django_connections()
            if send_alerts:
                logger.info("Sending alerts")
                base_directory = (Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / Variable.get("DATA_FLOW_CHECK"))
                out_filename = base_directory / f"alert_report-{report_time.timestamp()}.html"
                report = write_output_file(out_filename, report_time, template_data)
                send_email_alert(report_time, report, recipients=['ChiefDan@gmail.com'])

        return

    latest_records = most_current_record()
    send_alerts_task = send_alerts()

    latest_records >> send_alerts_task

check_data_flow()
