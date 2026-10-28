import os
import logging
import pendulum
import csv
import time
from io import StringIO
from airflow.sdk import dag, task, Variable
from typing import Dict, Any, List
from pathlib import Path
import json
import ijson
from datetime import datetime, timedelta
from django.db import IntegrityError, transaction

from datautilities.ccrab_api.client import CCRABAuthenticationError, CCRABRestClient
from datautilities.tsi_api.client import TSIExternalAPIClient, CSV_ACCEPT, JSON_ACCEPT, FLAT_TELEMETRY_FIELDS

from packages.django_setup import setup_django, close_django_connections
from packages.pycharm_debugging import maybe_attach_debugger
from observationsdatabase.xenia_obs_map import Organization, Platform
from ioos_qc.config import QcConfig
from ioos_qc.streams import PandasStream
from ioos_qc.results import CollectedResult, collect_results
import pandas as pd
#REMOTE_DEBUG = Variable.get("REMOTE_DEBUG", default=False)
REMOTE_DEBUG=False
if REMOTE_DEBUG:
    import pydevd_pycharm

    pydevd_pycharm.settrace("host.docker.internal", port=5678, stdout_to_server=True, stderr_to_server=True)


logger = logging.getLogger(__name__)
logger.setLevel(logging.NOTSET)

default_args = {
    "owner": "airflow",
    "email": ["ChiefDan@gmail.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "start_date": pendulum.datetime(2026, 1, 1, tz="UTC"),
}

@dag(
    dag_id="tsi_processing",
    schedule=None,
    max_active_runs=1,
    catchup=False,
    tags=["tsi","ccrab"],
    default_args=default_args,
)
def tsi_processing():


    @task()
    def get_configuration() -> str:
        config_file_path = None
        try:
            maybe_attach_debugger()

            logger.info("Retrieving configuration")
            base_directory = Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / "tsi" / "config"
            base_directory.mkdir(parents=True, exist_ok=True)
            config_file_path = base_directory / "tsi_config.json"
            ccrab_base_url = Variable.get("CCRAB_API_URL", None)
            ccrab_api = CCRABRestClient(base_url=ccrab_base_url)
            ccrab_user = Variable.get("CCRAB_API_USERNAME", None)
            ccrab_pwd = Variable.get("CCRAB_API_USER_PASSWORD", None)
            try:
                ccrab_api.obtain_token(username=ccrab_user, password=ccrab_pwd)
            except CCRABAuthenticationError:
                logger.warning("Unable to authenticate with CCRAB API; registering a token.")
                ccrab_api.register_user(username=ccrab_user, password=ccrab_pwd)
            organizations_setup = ccrab_api.platform_configuration(data_source='tsi_blue_sky')
            with config_file_path.open("w") as config_file:
                json.dump(organizations_setup, config_file)
        except Exception:
            logger.exception("Unable to retrieve TSI platform configuration")
            raise
        return str(config_file_path)

    @task()
    def decide_mode() -> Dict[str, str]:
        """
        #### decide_mode task

        Decide whether to run 'rest' or 'local' mode.
        mode can be provided as DAG conf, Airflow Variable, or left None to run 'auto' detection.
        Returns a small config dict with resolved_mode and useful paths.

        **Inputs:** None
        **Outputs:** dict
        """
        base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
        local_path = base_dir / Path(Variable.get("TSI_RAW_DATA_DIRECTORY", "tsi/unprocessed"))
        requested = Variable.get("TSI_PIPELINE_MODE", "auto").lower()

        assert requested in ("auto", "local", "rest"), "mode must be 'auto', 'local', or 'rest'"

        local_path.mkdir(parents=True, exist_ok=True)

        # TSI fetches are retained as JSON until headers are normalized.
        if requested == "auto":
            found = list(local_path.glob("*.json"))
            resolved_mode = "local" if len(found) > 0 else "rest"
        else:
            resolved_mode = requested

        return {"mode": resolved_mode, "directory_to_process": str(local_path)}

    def list_local_files(local_directory: str) -> Dict[str, Any]:
        """
        #### list_local_files task

        Search the local directory for source JSON files and return a run manifest.

        **Inputs:** local_directory
        **Outputs:** run manifest
        """
        data_directory = Path(local_directory)
        local_files = list(data_directory.glob("*.json"))
        if not local_files:
            raise FileNotFoundError(f"No JSON files found in {data_directory}")

        return {
            "source": "local",
            "saved_data_files": [str(file_path) for file_path in local_files],
            "start_timestamp": min(file_path.stat().st_mtime for file_path in local_files),
            "end_timestamp": max(file_path.stat().st_mtime for file_path in local_files),
        }

    def fetch_data_task(config_file_name: Path) -> Dict[str, Any]:
        """
        #### fetch_data_task task
        Using the TSI API, this task retrieves the data for the platforms setup in the JSON config.

        **Inputs:** config
        **Outputs:** list[]
        """
        configuration_data = json.load(open(config_file_name))
        org_list = []
        #Build our org and platform objects.
        for organization in configuration_data['organizations']:
            org_list.append(Organization().from_dict(organization))

        base_directory = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
        data_directory = base_directory / Variable.get("TSI_RAW_DATA_DIRECTORY", "tsi/unprocessed")
        if data_directory is not None:
            data_directory = Path(data_directory)
            data_directory.mkdir(parents=True, exist_ok=True)

        last_retrieved_record_date = Variable.get("last_retrieved_record_date", "1900-01-01 00:00:00")
        tsi_base_url = Variable.get("TSI_API_BASE_URL", None)
        tsi_client_id = Variable.get('TSI_API_CLIENT_ID', None)
        tsi_api_secret = Variable.get('TSI_API_SECRET', None)
        tsi_api = TSIExternalAPIClient(base_url=tsi_base_url,
                                       client_id=tsi_client_id,
                                       client_secret=tsi_api_secret
                                       )

        saved_data_files = []

        try:
            for organization in org_list:
                platform_handles = organization.list_platform_handles()
                #organization = configuration_data['organizations'][organization_id]
                #platform_handles = [platform['platform_handle'] for platform in organization['platforms']]
                for platform_handle in platform_handles:
                    platform = organization.get_platform(platform_handle)
                    external_indentifier = platform.properties['external_identifier']
                    end_date = datetime.now()
                    start_date = end_date - timedelta(hours=1)
                    try:
                        results = tsi_api.get_flat_telemetry(device_id=external_indentifier,
                                              start_date=start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                              end_date=end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                              telem=FLAT_TELEMETRY_FIELDS)
                        file_platform_handle = platform_handle.replace(".", "_")
                        output_file = data_directory / (f"{file_platform_handle}-{external_indentifier}-"
                                                              f"{start_date.strftime('%Y%m%dT%H%M%S')}-"
                                                              f"{end_date.strftime('%Y%m%dT%H%M%S')}.json")
                        logger.info(f"Writing to {output_file}")
                        try:
                            with open(output_file, "w") as out_file_obj:
                                #out_file_obj.write(results)
                                json.dump(results, out_file_obj)
                                saved_data_files.append(str(output_file))
                                logger.info(f"Finished writing to {output_file}")

                        except Exception as e:
                            logger.error(f"Error writing to {output_file}")
                            logger.exception(e)
                            raise e
                    except Exception as e:
                        logger.error(f"Unable to retrieve data for platform: {platform_handle} ({external_indentifier})")
                        logger.exception(e)
        except Exception:
            logger.exception("Unable to retrieve TSI telemetry")
            raise

        except Exception as e:
            close_django_connections()
            raise e
        finally:
            close_django_connections()
        return_data = {
            "source": "rest",
            "start_timestamp": start_date.timestamp(),
            "end_timestamp": end_date.timestamp(),
            "saved_data_files": saved_data_files,
        }

    @task(multiple_outputs=True)
    def acquire_data(config_file_name: str, run_config: Dict[str, str]) -> Dict[str, Any]:
        """Acquire files and return the same manifest for local and REST modes."""
        if run_config["mode"] == "local":
            return list_local_files(run_config["directory_to_process"])
        return fetch_data_task(Path(config_file_name))

    @task()
    def normalize_headers_task(config_file_name: Path, uncorrected_data_files: []) -> []:
        """
        #### normalize_headers_task
        Given a list of the data files, this task normalizes the header columns.

        **Inputs:** config, uncorrected_data_files
        **Outputs:** list[]
        """
        configuration_data = json.load(open(config_file_name))

        base_directory = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
        header_corrected_directory = base_directory / Variable.get("TSI_HEADER_CORRECTED_DIRECTORY", 'tsi/header_corrected')
        corrected_file_list = []
        #Let's make sure the directory exists.
        header_corrected_directory.mkdir(parents=True, exist_ok=True)

        configuration_data = json.load(open(config_file_name))
        org_list = []
        #Build our org and platform objects.
        for organization in configuration_data['organizations']:
            org_list.append(Organization().from_dict(organization))

        #The file names are platform_handle-device_id-start_date-end_date.csv
        for data_file in uncorrected_data_files:
            file_path = Path(data_file)
            file_name_parts = file_path.stem.split("-")
            # The platform handle format we need is <org>.<platform name>.<platform type>. When
            # we create the filename, we replace the "." with "_" to avoid any OS/Filesystem issues.
            file_platform_handle = file_name_parts[0].replace("_", ".")
            for organization in org_list:
                logger.info(
                    f"Check for platform: {file_platform_handle} in organization: {organization.short_name}")
                platform_nfo = organization.get_platform(file_platform_handle)
                if platform_nfo is None:
                    logger.error(f"Platform {file_platform_handle} not found in list.")
                else:
                    break
            corrected_file = header_corrected_directory / f"{file_path.stem}-corrected.csv"
            logger.info(f"Reading source file: {data_file} Writing corrected file: {corrected_file}")
            try:
                with open(data_file, "r") as file_obj:
                    with open(corrected_file, "w") as corrected_file_obj:
                        csv_writer = csv.writer(corrected_file_obj)

                        for row, rows in enumerate(ijson.items(file_obj, 'item')):
                            if row == 0:
                                corrected_header = normalize_header(rows, platform_nfo)
                                csv_writer.writerow(corrected_header)
                            out_row = [rows[key] for key in rows.keys()]
                            csv_writer.writerow(out_row)
                    corrected_file_list.append(str(corrected_file))
            except Exception as e:
                logger.exception(e)
        return corrected_file_list

    @task()
    def qaqc_task(config: {}, saved_data: []) -> []:
        """
        #### qaqc_task

        Using the saved_data CSV file list, this task performs the QAQC functions configured in the "qaqc" section of
        the JSON configuration file. It will then add the qaqcd flag results into new columns in the dataframe and then
        save the qaqcd CSV files.

        **Inputs:** config, uncorrected_csv_data_files
        **Outputs:** list[]
        """
        qaqc_directory = config.get("qaqc_data_directory", None)
        qc_config = CONFIG.get("qaqc", None)['config']
        if qaqc_directory is not None:
            qaqc_directory = Path(qaqc_directory)
            qaqc_directory.mkdir(parents=True, exist_ok=True)
        else:
            raise Exception("qaqc directory not specified")
        qc = QcConfig(qc_config)
        qaqcd_files = []
        for data_file in saved_data:
            logger.info(f"Starting qaqc_task on file: {data_file}")
            try:
                test_df = pd.read_csv(data_file)

                #The survey data is not a flat file format, so we have to use the key to get the row we want,
                #then we use the numeric field.
                p_df = PandasStream(test_df)
                runner = list(p_df.run(qc))
                results = collect_results(runner, how="list")

                #We want to create a new data frame with our QCQC results.
                for result in results:
                    test_df[f"F_{result.stream_id}"] =result.results

                src_path = Path(data_file)
                qaqc_filename = qaqc_directory / f"{src_path.name}-qaqc.csv"
                logger.info(f"Writing qaqc file: {qaqc_filename}")
                test_df.to_csv(qaqc_filename, index=False)
                #Now we save the QAQCd data records to file.
                qaqcd_files.append(str(qaqc_filename))
            except Exception as e:
                raise e
        return qaqcd_files

    @task()
    def save_to_database_task(config_file_name: Path, file_list: []):
        TSI_LOG_INSERTS = Variable.get("TSI_LOG_INSERTS", deserialize_json=True, default=0)
        BULK_INSERT_FILE_SIZE = Variable.get("TSI_BULK_INSERT_FILE_SIZE", deserialize_json=True, default=1000000)
        CHUNK_SIZE = Variable.get("TSI_CHUNK_SIZE", deserialize_json=True, default=1000)
        try:
            setup_django()

            from platforms_app.models import Multi_obs

            def flush_pending_records():
                nonlocal attempted_records

                if not pending_records:
                    return

                count = len(pending_records)
                with transaction.atomic():
                    Multi_obs.objects.bulk_create(
                        pending_records,
                        batch_size=count,
                        ignore_conflicts=True,
                    )

                attempted_records += count
                pending_records.clear()

            # Build our org and platform objects.
            organizations_setup = load_config_file(config_file_name)

            batch_size = max(1, int(CHUNK_SIZE))

            for file in file_list:
                logger.info(f"Processing file: {file} into the database")
                file_path = Path(file)
                file_name_parts = file_path.stem.split("-")
                # The platform handle format we need is <org>.<platform name>.<platform type>. When
                # we create the filename, we replace the "." with "_" to avoid any OS/Filesystem issues.
                file_platform_handle = file_name_parts[0].replace("_", ".")

                platform_nfo = None
                for organization_nfo in organizations_setup:
                    platform_nfo = organization_nfo.get_platform(file_platform_handle)
                    if platform_nfo is not None:
                        break
                if platform_nfo is not None:
                    with open(file_path, "r") as csv_file_obj:
                        file_start_time = time.perf_counter()
                        row_entry_date = datetime.now()
                        csv_reader = csv.DictReader(csv_file_obj)
                        duplicate_row_count = 0
                        insert_exception_count = 0
                        pending_records = []
                        attempted_records = 0
                        invalid_value_count = 0

                        logged_missed_observations = set()
                        #Build a list of the observations that should be in the file.
                        active_observations = [
                            (f"{obs.target_obs}_{obs.s_order}", obs)
                            for obs in platform_nfo.obs_map
                            if obs.target_active == 1
                        ]
                        for row_ndx, row in enumerate(csv_reader):
                            m_date = row["m_date"]

                            for column_name, obs_info in active_observations:
                                if column_name not in row:
                                    if column_name not in logged_missed_observations:
                                        '''
                                        logger.warning(
                                            "Column %s not found in row %s of %s",
                                            column_name,
                                            row_ndx,
                                            file,
                                        )
                                        '''
                                        logged_missed_observations.add(column_name)

                                    continue

                                try:
                                    raw_value = row[column_name]
                                    val = float(raw_value)
                                except (ValueError, TypeError) as e:
                                    logger.error(f"Unable to process row: {row}({row_ndx}) Value: {row[column_name]}")
                                    logger.exception(e)

                                    continue
                                #Build the records for the bulk insert.
                                #logger.debug(
                                #    f"Adding {row_entry_date} {platform_nfo.platform_handle} {column_name} {m_date} {val}")
                                pending_records.append(
                                    Multi_obs(row_entry_date=row_entry_date,
                                                             platform_handle=platform_nfo.platform_handle,
                                                             m_date=m_date,
                                                             m_value=val,
                                                             sensor_id_id=obs_info.sensor_id,
                                                             m_type_id_id=obs_info.m_type_id,
                                                             m_lon=platform_nfo.longitude,
                                                             m_lat=platform_nfo.latitude)
                                )
                                if len(pending_records) >= batch_size:
                                    flush_pending_records()
                                if row_ndx and row_ndx % 10 == 0:
                                    logger.info(
                                        f"Prepared {row_ndx} CSV rows from {file} in {time.perf_counter() - file_start_time}",
                                    )

                            flush_pending_records()
                        if attempted_records:
                            logger.info(
                                f"Finished {file}: attempted {attempted_records} observations; invalid values {invalid_value_count}; "
                                f"elapsed {time.perf_counter() - file_start_time}",
                            )
                        else:
                            logger.warning(
                                f"No observations found in {file}",
                            )
                else:
                    logger.error(f"Platform {file_platform_handle} not found in list.")
        except Exception as e:
            close_django_connections()
            raise e
        finally:
            close_django_connections()

    def load_config_file(configuration_file: Path) -> List[Any]:
        configuration_data = json.load(open(configuration_file))
        organizations_setup = []
        # Build our org and platform objects.
        for organization in configuration_data['organizations']:
            organizations_setup.append(Organization().from_dict(organization))

        return organizations_setup

    def normalize_header(row: {}, platform_nfo: Platform) -> []:
        corrected_header = []
        for column in list(row.keys()):
            if column.lower() == "timestamp":
                corrected_header.append("m_date")
            else:
                obs_record = platform_nfo.obs_map.get_by_source(column)
                if obs_record is not None:
                    corrected_column = column
                    if obs_record is not None:
                        corrected_column = f"{obs_record.target_obs}_{obs_record.s_order}"
                    corrected_header.append(corrected_column)
                else:
                    corrected_header.append(column)
        return corrected_header


    configuration_file_path = get_configuration()

    # Resolve the mode at task runtime, then produce one manifest regardless of source.
    run_config = decide_mode()
    run_manifest = acquire_data(configuration_file_path, run_config)
    csv_files_to_process = run_manifest["saved_data_files"]

    #We want to correct the headers from the Purple Air fields to our normalized names.
    normalized_header_data_files = normalize_headers_task(configuration_file_path, csv_files_to_process)

    #qaqcd_data = qaqc_task(CONFIG, normalized_header_data_files)
    save_to_database_task(configuration_file_path, normalized_header_data_files)

tsi_processing()
