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
        unique_run_id = context['run_id']
        logger.info("Query most current records for platforms.")
        now_time = datetime.now(tz=pytz.UTC)
        base_directory = (Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / Variable.get("PURPLE_AIR_WORKiNG_DIRECTORY")
                          / Variable.get("DATA_FLOW_CHECK"))
        logger.info(f"Base directory: {base_directory}")
        # Make sure out destination directory exists.
        base_directory.mkdir(parents=True, exist_ok=True)

        setup_django()
        from django.db.models import OuterRef, Subquery
        from platforms_app.models import Multi_obs, Platform

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

        return {'timestamp': now_time.timestamp(), 'output_file': str(output_file)}

    latest_records = most_current_record()



check_data_flow()