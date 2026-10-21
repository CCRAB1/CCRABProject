import os
import logging
import pendulum
from airflow.sdk import dag, task, Variable
import subprocess
from pathlib import Path
from datetime import timedelta

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
    dag_id="database_backup",
    schedule="0 0 * * *",
    max_active_runs=1,
    catchup=False,
    tags=["purpleair","ccrab", "backup"],
    default_args=default_args,
)
def database_backup():

    @task(retries=2, retry_delay=timedelta(minutes=5))
    def platforms_backup():
        from airflow.sdk import get_current_context

        logger.info("Starting platforms_backup database backup.")

        database_name = os.environ.get("DATABASE_NAME", default=None)
        database_user = os.environ.get("DATABASE_USER", default=None)
        database_password = os.environ.get("DATABASE_PASSWORD", default=None)
        database_host = os.environ.get("DATABASE_HOST", default=None)
        database_port = os.environ.get("DATABASE_PORT", default=None)

        context = get_current_context()
        timestamp = context["logical_date"].strftime("%Y%m%dT%H%M%S")

        backup_dir = Path(Variable.get("DATABASE_BACKUP_DIRECTORY"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        output_file = backup_dir / f"database_{timestamp}.dump"
        temporary_file = output_file.with_suffix(".dump.partial")
        logger.info(f"Temporary backup file: {temporary_file}")

        try:
            env = os.environ.copy()
            env["PGPASSWORD"] = database_password

            args =  [
                "pg_dump",
                f"--host={database_host}",
                f"--port={database_port}",
                f"--username={database_user}",
                "--no-password",
                "--dbname=ccrabdb",
                "--schema=platforms",
                "--format=custom",
                f"--file={temporary_file}"
             ]
            result = subprocess.run(
                args,
                env=env,
                check=True,
                timeout=3600,  # Stop waiting and terminate after one hour.
            )
        except subprocess.CalledProcessError as exc:
            logger.exception("pg_dump failed with exit code %s", exc.returncode)
            raise
        except subprocess.TimeoutExpired:
            logger.exception("pg_dump exceeded the one-hour timeout")
            raise
        except FileNotFoundError:
            logger.exception("pg_dump executable was not found")
            raise
        else:
            logger.info("pg_dump completed successfully: %s", output_file)

            logger.info(f"pg_dump exited with results {result}")

            logger.info(f"Renaming temp file to : {output_file}")

            temporary_file.replace(output_file)
            return str(output_file)

    platforms_backup()

database_backup()