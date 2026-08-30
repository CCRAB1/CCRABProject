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
from urllib.parse import urlparse
from math import floor as math_floor
import pandas as pd
from datetime import datetime, timedelta, tzinfo
import pytz
from django.db import IntegrityError, transaction
from datautilities.purple_air_api.PurpleAPIWrapper import (
    PurpleAirClient,
)
from datautilities.epa.epa_calculations import apply_epa_correction
from packages.django_setup import setup_django, close_django_connections
from datautilities.ccrab_api.client import CCRABRestClient, CCRABAuthenticationError
from observationsdatabase.xenia_obs_map import Organization, Platform
from packages.archiving import archive_file, zip_files
from ioos_qc.config import QcConfig
from ioos_qc.streams import PandasStream
from ioos_qc.results import CollectedResult, collect_results
import pandas as pd

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
    dag_id="purple_air_processing",
    schedule="*/30 * * * *",
    max_active_runs=1,
    catchup=False,
    tags=["purpleair","ccrab"],
    default_args=default_args,
)
def purple_air_processing():

    @task()
    def get_configuration() -> str:
        try:

            #maybe_attach_debugger()

            logger.info("Retrieving configuration")
            base_directory = Path(Variable.get("BASE_PROCESSING_DIRECTORY")) / "purple_air" / "config"
            logger.info(f"Base directory: {base_directory}")
            #Make sure out destination directory exists.
            base_directory.mkdir(parents=True, exist_ok=True)
            config_file_path = base_directory / "purple_air_config.json"
            ccrab_base_url = Variable.get("CCRAB_API_URL", None)
            ccrab_api = CCRABRestClient(base_url=ccrab_base_url,
                                        verify=get_requests_verify(ccrab_base_url)
                                        )
            ccrab_user = Variable.get("CCRAB_API_USERNAME", None)
            ccrab_pwd = Variable.get("CCRAB_API_USER_PASSWORD", None)
            #Get the access token to use for the API calls.
            try:
                ccrab_token = ccrab_api.obtain_token(username=ccrab_user, password=ccrab_pwd)
            except CCRABAuthenticationError as e:
                logger.error(
                    f"Unable to authenticate with CCRAB API. Attempting to create a new token."
                )
                ccrab_api.register_user(username=ccrab_user, password=ccrab_pwd)
            organizations_setup = ccrab_api.platform_configuration(data_source='purple_air')
            json.dump(organizations_setup, open(config_file_path, "w"))
        except Exception as e:
            logger.exception(e)
            raise e
        return str(config_file_path)


    @task()
    def decide_mode() -> Dict:
        """
        #### decide_mode task

        Decide whether to run 'rest' or 'local' mode.
        mode can be provided as DAG conf, Airflow Variable, or left None to run 'auto' detection.
        Returns a small config dict with resolved_mode and useful paths.

        **Inputs:** None
        **Outputs:** dict
        """
        # precedence: dagrun.conf -> supplied arg -> Variable -> auto
        #dag_conf_mode =

        base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
        local_path = base_dir / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY")) / Path(Variable.get("RAW_DATA_DIRECTORY"))
        # If user passes a conf via dag run, Airflow will pass it; we handle via Variable for now.
        requested = Variable.get("PURPLE_AIR_CSV_PIPELINE_MODE", "auto").lower()
        assert requested in ("auto", "local", "rest"), "mode must be 'auto', 'local', or 'rest'"

        local_path.mkdir(parents=True, exist_ok=True)

        # auto-detect: if CSV files exist, use local. Otherwise use rest.
        if requested == "auto":
            found = list(local_path.glob("*.csv"))
            resolved_mode = "local" if len(found) > 0 else "rest"
        else:
            resolved_mode = requested

        logger.info(f"mode: {resolved_mode} directory_to_process: {str(local_path)}")

        return {"mode": resolved_mode, "directory_to_process": str(local_path)}

    def list_local_files(local_directory: str) -> Dict[str, Any]:
        """
        #### list_local_files helper

        Search the local_directory for all CSV files in the local directory.
        Input is the local directory, the output is a list of CSV files in that directory.

        **Inputs:** local_directory
        **Outputs:** run manifest
        """
        data_directory = Path(local_directory)
        local_csv_list = list(data_directory.glob("*.csv"))
        if not local_csv_list:
            raise FileNotFoundError(f"No CSV files found in {data_directory}")

        start_dates = []
        end_dates = []
        for file_path in local_csv_list:
            file_name_parts = file_path.stem.split("-")
            try:
                start_dates.append(datetime.strptime(file_name_parts[-2], "%Y%m%dT%H%M%S"))
                end_dates.append(datetime.strptime(file_name_parts[-1], "%Y%m%dT%H%M%S"))
            except (IndexError, ValueError) as exc:
                raise ValueError(
                    f"Unable to determine the processing interval from local file name: {file_path.name}"
                ) from exc

        return {
            "source": "local",
            "saved_data_files": [str(file_path) for file_path in local_csv_list],
            "start_timestamp": min(start_dates).timestamp(),
            "end_timestamp": max(end_dates).timestamp(),
        }

    def fetch_data_task(config_file_name: Path) -> Dict[str, Any]:
        """
        #### fetch_data_task task
        Using the Purple AIr API, this task retrieves the data for the platforms setup in the JSON config.

        **Inputs:** config
        **Outputs:** list[]
        """
        platform_query_times = {}
        saved_data_files = []
        try:
            start_time = time.perf_counter()
            logger.info(f"Starting fetch_data_task with config file: {config_file_name}")

            setup_django()
            from platforms_app.models import Multi_obs

            configuration_data = json.load(open(config_file_name))
            org_list = []
            #Build our org and platform objects.
            for organization in configuration_data['organizations']:
                org_list.append(Organization().from_dict(organization))

            base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
            data_directory = base_dir / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY")) / Path(Variable.get("RAW_DATA_DIRECTORY"))
            data_directory = Path(data_directory)
            data_directory.mkdir(parents=True, exist_ok=True)

            last_retrieved_record_date = Variable.get("last_retrieved_record_date", "1900-01-01 00:00:00")
            purple_air_base_url = Variable.get("PURPLE_AIR_API_BASE_URL", None)
            purple_air_api_key = Variable.get('PURPLE_AIR_API_KEY', None)
            purple_api = PurpleAirClient(api_key=purple_air_api_key, base_url=purple_air_base_url, timeout=30.0)

            platform_count = 0

            end_date = datetime.now()
            end_date = pytz.utc.localize(end_date)
            start_date = end_date - timedelta(hours=1)

            for organization in org_list:
                platform_handles = organization.list_platform_handles()
                platform_count += len(platform_handles)
                #organization = configuration_data['organizations'][organization_id]
                #platform_handles = [platform['platform_handle'] for platform in organization['platforms']]
                for platform_handle in platform_handles:
                    platform = organization.get_platform(platform_handle)
                    external_indentifier = platform.properties['external_identifier']
                    #Let's get the latest date in the database then build our start/end dates for query from there.
                    latest_m_date = (
                        Multi_obs.objects
                        .filter(
                            platform_handle=platform_handle,
                            m_date__isnull=False,
                        )
                        .order_by("-m_date")
                        .values_list("m_date", flat=True)
                        .first()
                    )
                    if latest_m_date is not None:
                        #Add a minute so we don't get the same record twice.'
                        start_date = latest_m_date + timedelta(minutes=1)
                        #If the delta between start and end is more than 30 days, cut it to 30 days.
                        if (end_date - start_date) > timedelta(days=30):
                            start_date = end_date - timedelta(days=30)

                    try:
                        platform_query_times[platform_handle] = {'start_date': start_date.timestamp(),
                                                                 'end_date': end_date.timestamp()}
                        #These are the sensors we want to retrieve from PUrple Air API.
                        fields = [obs['source_obs'] for obs in platform.observations if obs['source_active'] == 1]

                        logger.info(f"Getting sensor history for sensor_index {external_indentifier} Start: {start_date}"
                                    f" End: {end_date} Fields: {fields}")
                        results = purple_api.get_sensor_history(sensor_index=external_indentifier,
                                                                     start_timestamp=start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                                     end_timestamp=end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                                     average=0,
                                                                     fields=fields,
                                                                     return_format="csv",
                                                                     stream=True)
                        file_platform_handle = platform_handle.replace(".", "_")
                        output_file = data_directory / (f"{file_platform_handle}-{external_indentifier}-"
                                                              f"{start_date.strftime('%Y%m%dT%H%M%S')}-"
                                                              f"{end_date.strftime('%Y%m%dT%H%M%S')}.csv")
                        logger.info(f"Writing to {output_file}")
                        try:
                            with open(output_file, "w") as out_file_obj:
                                for row in results:
                                    out_file_obj.write(f"{row}\n")
                                saved_data_files.append(str(output_file))
                        except Exception as e:
                            logger.error(f"Failed to write file: {output_file}")

                            raise e

                    except Exception as e:
                        logger.error(f"Unable to retrieve data for platform: {platform_handle} ({external_indentifier})")
                        logger.exception(e)
                        #raise e
            org_info = purple_api.get_organization()
            logger.info(f"Purple Air API Remaining Points: {org_info['remaining_points']} Consumption Rate: {org_info['consumption_rate']} API Version: {org_info['api_version']}")
            if org_info['remaining_points'] < 500000:
                logger.warning(f"Purple Air API remaining points is low: {org_info['remaining_points']}")
            logger.info(f"Completed fetch_data_task in {time.perf_counter()-start_time} seconds for {platform_count} platforms")

        except Exception as e:
            close_django_connections()
            raise e
        finally:
            close_django_connections()
        return_data = {
            "source": "rest",
            "start_timestamp": start_date.timestamp(),
            "end_timestamp": end_date.timestamp(),
            "saved_data_files": saved_data_files
        }
        return return_data

    @task(multiple_outputs=True)
    def acquire_data(config_file_name: str, run_config: Dict[str, str]) -> Dict[str, Any]:
        """Acquire input files and return one manifest for either supported mode."""
        if run_config["mode"] == "local":
            return list_local_files(run_config["directory_to_process"])

        return fetch_data_task(Path(config_file_name))


    @task()
    def normalize_headers_task(config_file_name: Path, uncorrected_data_files: List[Any]) -> list[Any]:
        """
        #### normalize_headers_task
        Given a list of the data files, this task normalizes the header columns.

        **Inputs:** config, uncorrected_csv_data_files
        **Outputs:** list[]
        """
        try:
            start_time = time.perf_counter()
            logger.info(f"Starting normalize_headers_task with config file: {config_file_name}")
            configuration_data = json.load(open(config_file_name))

            base_directory = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
            header_corrected_directory = base_directory / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY")) / Path(Variable.get("NORMALIZED_HEADER_DIRECTORY"))
            #Let's make sure the directory exists.
            header_corrected_directory.mkdir(parents=True, exist_ok=True)

            corrected_file_list = []
            org_list = []
            #Build our org and platform objects.
            for organization in configuration_data['organizations']:
                org_list.append(Organization().from_dict(organization))


            #The file names are platform_handle-sensor_id-start_date-end_date.csv
            for file in uncorrected_data_files:
                platform_nfo = None
                file_path = Path(file)
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
                corrected_file = header_corrected_directory / f"{file_path.stem}-unsorted-corrected.csv"
                logger.info(f"Reading source file: {file} Writing corrected file: {corrected_file}")
                if platform_nfo:
                    try:
                        platform_file_df = pd.read_csv(file)
                        # The files aren't sorted by date/time from the API. We'll do that here.
                        platform_file_df['DateTimeStamp'] = pd.to_datetime(platform_file_df['time_stamp'],
                                                                         #2026-07-22T13:23:54Z
                                                                         format="%Y-%m-%dT%H:%M:%SZ")
                        platform_file_df.sort_values(by='DateTimeStamp', inplace=True)
                        platform_file_df.drop(columns='DateTimeStamp', inplace=True)
                        #Now we'll normalize the column names.
                        pa_columns = platform_file_df.columns.to_list()
                        normalized_header_name = normalize_header(pa_columns, platform_nfo)
                        #normalized_header_name = [normalize_header(pa_col, platform_nfo) for pa_col in pa_columns]
                        platform_file_df.to_csv(corrected_file, index=False, float_format='%.2f', header=normalized_header_name)

                    except Exception as e:
                        logger.exception(e)
                    else:
                        corrected_file_list.append(str(corrected_file))

                """   
                with open(file, "r") as csv_file_obj:
                    csv_reader = csv.reader(csv_file_obj)
                    with open(corrected_file, "w") as corrected_file_obj:
                        csv_writer = csv.writer(corrected_file_obj)
                        for row_number, row in enumerate(csv_reader):
                            if row_number == 0:
                                corrected_header = normalize_header(row, platform_nfo)
                                csv_writer.writerow(corrected_header)
                            else:
                                csv_writer.writerow(row)
                """
        except Exception as e:
            raise e
        logger.info(f"Completed normalize_headers_task in {time.perf_counter()-start_time} seconds")
        return corrected_file_list

    @task()
    def ancillary_calculations(config_file_name: Path, normalized_header_files: []) -> list[Any]:
        try:
            start_time = time.perf_counter()
            logger.info(f"Starting ancillary_calculations with config file: {config_file_name}")
            configuration_data = json.load(open(config_file_name))

            base_directory = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
            epa_corrected_directory = base_directory / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY")) / Path(Variable.get("EPA_CORRECTED_DIRECTORY"))
            #Let's make sure the directory exists.
            epa_corrected_directory.mkdir(parents=True, exist_ok=True)

            corrected_file_list = []
            organizations_setup = []
            #Build our org and platform objects.
            for organization in configuration_data['organizations']:
                organizations_setup.append(Organization().from_dict(organization))

            for normalized_file in normalized_header_files:
                file_path = Path(normalized_file)
                file_name_parts = file_path.stem.split("-")
                # The platform handle format we need is <org>.<platform name>.<platform type>. When
                # we create the filename, we replace the "." with "_" to avoid any OS/Filesystem issues.
                file_platform_handle = file_name_parts[0].replace("_", ".")
                platform_nfo = None
                for organization in organizations_setup:
                    logger.info(
                        f"Check for platform: {file_platform_handle} in organization: {organization.short_name}")
                    platform_nfo = organization.get_platform(file_platform_handle)
                    if platform_nfo is None:
                        logger.error(f"Platform {file_platform_handle} not found in list.")
                    else:
                        break
                if platform_nfo is not None:
                    if file_path.stem.find("corrected") != -1:
                        corrected_filename = file_path.stem.replace("corrected", "epa_corrected")
                    else:
                        corrected_filename = f"{file_path.stem}-epa_corrected.csv"
                    corrected_file = epa_corrected_directory / f"{corrected_filename}.csv"
                    logger.info(f"Reading source file: {normalized_file} Writing corrected file: {corrected_file}")
                    with open(normalized_file, "r") as csv_file_obj:
                        csv_reader = csv.reader(csv_file_obj)
                        with open(corrected_file, "w") as corrected_file_obj:
                            csv_writer = csv.writer(corrected_file_obj)
                            humidity_a_ndx = humidity_b_ndx = pm25_cf1_a_ndx = pm25_cf1_b_ndx = None
                            window_buffer = []
                            start_window_dt = None
                            end_window_dt = None
                            for row_number, row in enumerate(csv_reader):
                                if row_number == 0:
                                    #Get the column indexes for the pm2.5 cf obs and humidty so we can calc the
                                    #epa aqi. We have to have at least the relative_humidity_1 and pm2.5_cf_1_1.
                                    if "relative_humidity_1" in row and "pm2.5_cf_1_1" in row:
                                        humidity_a_ndx = row.index("relative_humidity_1")
                                        pm25_cf1_a_ndx = row.index("pm2.5_cf_1_1")
                                        if "relative_humidity_2" in row:
                                            humidity_b_ndx = row.index("relative_humidity_2")
                                        if "pm2.5_cf_1_2" in row:
                                            pm25_cf1_b_ndx = row.index("pm2.5_cf_1_2")
                                    else:
                                        logger.error(f"Missing relative_humidity_1 or pm2.5_cf_1_1 in header: {row}")
                                    row.append("pm2.5_EPAc_1")
                                    #Write new header back out.
                                    csv_writer.writerow(row)

                                else:
                                    row_dt = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ")
                                    if start_window_dt is None:
                                        start_window_dt = row_dt
                                        end_window_dt = start_window_dt + timedelta(minutes=15)
                                    if row_dt >= end_window_dt:
                                        if humidity_a_ndx and pm25_cf1_a_ndx:
                                            humidity_b = pm25_cf1_b = None
                                            humidity_a = sum(
                                                float(row[humidity_a_ndx]) for row in window_buffer) / len(
                                                window_buffer)
                                            pm25_cf1_a = sum(
                                                float(row[pm25_cf1_a_ndx]) for row in window_buffer) / len(
                                                window_buffer)
                                            if humidity_b_ndx and pm25_cf1_b_ndx:
                                                humidity_a = sum(
                                                    float(row[humidity_b_ndx]) for row in window_buffer) / len(
                                                    window_buffer)
                                                pm25_cf1_a = sum(
                                                    float(row[pm25_cf1_b_ndx]) for row in window_buffer) / len(
                                                    window_buffer)
                                            epa_corrected = apply_epa_correction(pm25_cf1_a, humidity_a, pm25_cf1_b,
                                                                                 humidity_b)
                                            row.append(f"{epa_corrected:.2f}")
                                        else:
                                            row.append("")

                                        del window_buffer[:]
                                    else:
                                        window_buffer.append(row)
                                    csv_writer.writerow(row)
                        corrected_file_list.append(str(corrected_file))
            logger.info(f"Finished ancillary_calculations in {time.perf_counter()-start_time} seconds")

        except Exception as e:
            raise e
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
    def save_to_database_task(run_label: str, config_file_name: Path, file_list: []):
        #Grab the database connection parameters from the Airflow variables.
        PURPLEAIR_TASK_LOG_INSERTS = Variable.get("PURPLEAIR_TASK_LOG_INSERTS", deserialize_json=True, default=0)
        PURPLEAIR_BULK_INSERT_FILE_SIZE = Variable.get("PURPLEAIR_BULK_INSERT_FILE_SIZE", deserialize_json=True, default=1000000)
        PURPLEAIR_CHUNK_SIZE = Variable.get("PURPLEAIR_CHUNK_SIZE", deserialize_json=True, default=1000)
        try:
            setup_django()

            from platforms_app.models import Multi_obs
            # Build our org and platform objects.
            organizations_setup = load_config_file(config_file_name)

            for file in file_list:
                logger.info(f"Processing file: {file} into the database")
                file_path = Path(file)
                file_name_parts = file_path.stem.split("-")
                # The platform handle format we need is <org>.<platform name>.<platform type>. When
                # we create the filename, we replace the "." with "_" to avoid any OS/Filesystem issues.
                file_platform_handle = file_name_parts[0].replace("_", ".")

                for organization_nfo in organizations_setup:
                    platform_nfo = organization_nfo.get_platform(file_platform_handle)
                    if platform_nfo is not None:
                        break
                #Check the file size, if it exceeds
                if file_path.stat().st_size >= PURPLEAIR_BULK_INSERT_FILE_SIZE:
                    #csv_file: Path, db: xenia_alchemy, platform_nfo: Platform, insert_chunk_size: int
                    bulk_insert_to_database(file_path, platform_nfo, PURPLEAIR_CHUNK_SIZE)
                else:

                    with open(file_path, "r") as csv_file_obj:
                        file_start_time = time.perf_counter()
                        row_entry_date = datetime.now()
                        csv_reader = csv.DictReader(csv_file_obj)
                        duplicate_row_count = 0
                        insert_exception_count = 0

                        for row_ndx, row in enumerate(csv_reader):
                            for obs_info in platform_nfo.obs_map:
                                #We build the name for each column we want which is >target_obs>_<s_order>. The date
                                #column has been renamed m_date during the normalize task.
                                try:
                                    column_name = f"{obs_info.target_obs}_{obs_info.s_order}"
                                    if column_name in row:
                                        if obs_info.target_active == 1:
                                            m_date = row['m_date']
                                            try:
                                                val = None
                                                if len(row[column_name]):
                                                    val = float(row[column_name])
                                            except (ValueError, TypeError) as e:
                                                logger.error(f"Unable to process row: {row}({row_ndx}) Value: {row[column_name]}")
                                                logger.exception(e)
                                            else:
                                                if PURPLEAIR_TASK_LOG_INSERTS:
                                                    #if row_ndx % 1000 == 0:
                                                    logger.info(f"Adding record: {platform_nfo.platform_handle} Date: {m_date}"
                                                                f" Value: {val} Sensor: {obs_info.target_obs}({obs_info.sensor_id}) "
                                                                f"{obs_info.target_uom}({obs_info.m_type_id}) SOrder: {obs_info.s_order}")
                                                try:
                                                    with transaction.atomic():
                                                        obs_rec = Multi_obs.objects.create(row_entry_date=row_entry_date,
                                                                            platform_handle=platform_nfo.platform_handle,
                                                                            m_date=m_date,
                                                                            m_value=val,
                                                                            sensor_id_id=obs_info.sensor_id,
                                                                            m_type_id_id=obs_info.m_type_id,
                                                                            m_lon=platform_nfo.longitude,
                                                                            m_lat=platform_nfo.latitude)
                                                except IntegrityError as e:
                                                    logger.error(f"Record already exists: {e}")
                                                    duplicate_row_count += 1
                                                except Exception as e:
                                                    logger.error(f"Error adding record: {e}")
                                                    logger.exception(e)
                                                    insert_exception_count += 1
                                    else:
                                        logger.info(f"Column: {column_name} not found in row_ndx: {row_ndx}")
                                except Exception as e:
                                    close_django_connections()
                                    raise e
                            logger.info(f"Processed {row_ndx} rows from file: {file} into the database in: "
                                        f"{time.perf_counter()-file_start_time} seconds")

        except Exception as e:
            close_django_connections()
            raise e
        finally:
            close_django_connections()
    @task()
    def ancillary_calculations_post_db_save(config_file_name: Path, start_timestamp: float, end_timestamp: float) -> list[Any]:
        start_proc_time = time.perf_counter()

        #Create the datetime object from the timestamps.
        start_date_time = datetime.fromtimestamp(start_timestamp)
        end_date_time = datetime.fromtimestamp(end_timestamp)

        logger.info(f"Starting ancillary_calculations_post_db_save with config file: {config_file_name} "
                    f"Start: {start_date_time} End: {end_date_time}")
        try:

            base_directory = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
            epa_corrected_directory = base_directory / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY")) / Path(
                Variable.get("EPA_CORRECTED_DIRECTORY"))
            # Let's make sure the directory exists.
            epa_corrected_directory.mkdir(parents=True, exist_ok=True)

            organizations_setup = load_config_file(config_file_name)

            corrected_file_list = []

            setup_django()

            from platforms_app.models import Multi_obs

            #These are the columns we want to calculate the EPA correction. It is a list of
            #tuples that consist of column names and their sensor order. The older Purple Air monitors
            #won't have the sensor order 2 parameters.
            epa_corrected_columns = ["relative_humidity","pm2.5_cf_1"]
            for organization in organizations_setup:
                platform_handles = organization.list_platform_handles()
                for platform_handle in platform_handles:
                    platform = organization.get_platform(platform_handle)

                    # These are the columns ids we want to retrieve from the database.
                    query_obs = [obs for obs in platform.observations
                                       if obs['target_obs'] in epa_corrected_columns]
                    column_name_mapping = dict([(obs['sensor_id'], f"{obs['target_obs']}_{obs['s_order']}") for obs in query_obs])
                    required_type_ids = [obs['m_type_id'] for obs in query_obs]
                    required_sensor_ids = [obs['sensor_id'] for obs in query_obs]
                    try:
                        obs_recs = (
                            Multi_obs.objects
                            .filter(
                                m_date__gte=start_date_time,
                                m_date__lt=end_date_time,
                                m_type_id__in=required_type_ids,
                                sensor_id__in=required_sensor_ids,
                            )
                            .values(
                                "platform_handle",
                                "m_date",
                                "m_value",
                                "sensor_id",
                                "m_type_id",
                            )
                        )
                    except Exception as e:
                        logger.exception(e)
                        raise e
                    if len(obs_recs):
                        df = pd.DataFrame.from_records(obs_recs)
                        df["m_date"] = pd.to_datetime(
                            df["m_date"],
                            utc=True,
                            errors="coerce",
                        )

                        df["m_value"] = pd.to_numeric(
                            df["m_value"],
                            errors="coerce",
                        )

                        # Translate each sensor ID into its output column name.
                        df["measurement_name"] = (
                            df["sensor_id"].map(column_name_mapping)
                        )
                        df["window_start"] = df["m_date"].dt.floor("15min")
                        df["window_end"] = (
                                df["window_start"] + pd.Timedelta(minutes=15)
                        )
                        file_platform_handle = platform_handle.replace('.', '_')
                        #intermediate_director = epa_corrected_directory / Path('initial_query')
                        #intermediate_director.mkdir(parents=True, exist_ok=True)
                        initial_output_file = epa_corrected_directory / (f"{file_platform_handle}-{platform.properties['external_identifier']}-"
                                                              f"{start_date_time.strftime('%Y%m%dT%H%M%S')}-"
                                                              f"{end_date_time.strftime('%Y%m%dT%H%M%S')}-initial-query.csv")
                        try:
                            logger.info(f"Writing to file: {initial_output_file}")
                            df.to_csv(initial_output_file, index=False)
                        except Exception as e:
                            logger.error(f"Error writing to file: {initial_output_file}")
                            logger.exception(e)

                        #Create the means for the columns.
                        interval_sensor_means = (
                            df
                            .groupby(
                                [
                                    "platform_handle",
                                    "window_start",
                                    "window_end",
                                    "measurement_name",
                                ],
                                as_index=False,
                            )
                            .agg(
                                interval_mean=("m_value", "mean"),
                                sample_count=("m_value", "count"),
                            )
                        )
                        interval_values = (
                            interval_sensor_means
                            .pivot(
                                index=[
                                    "platform_handle",
                                    "window_start",
                                    "window_end",
                                ],
                                columns="measurement_name",
                                values="interval_mean",
                            )
                            .reset_index()
                            .rename_axis(columns=None)
                        )
                        interval_counts = (
                            interval_sensor_means
                            .pivot(
                                index=[
                                    "platform_handle",
                                    "window_start",
                                    "window_end",
                                ],
                                columns="measurement_name",
                                values="sample_count",
                            )
                            .add_suffix("_count")
                            .reset_index()
                            .rename_axis(columns=None)
                        )

                        intervals = interval_values.merge(
                            interval_counts,
                            on=[
                                "platform_handle",
                                "window_start",
                                "window_end",
                            ],
                            how="left",
                        )
                        #intermediate_director = epa_corrected_directory / Path('intervals_means')
                        #intermediate_director.mkdir(parents=True, exist_ok=True)
                        intervals_output_file = epa_corrected_directory / (f"{file_platform_handle}-{platform.properties['external_identifier']}-"
                                                              f"{start_date_time.strftime('%Y%m%dT%H%M%S')}-"
                                                              f"{end_date_time.strftime('%Y%m%dT%H%M%S')}-intervals.csv")
                        try:
                            logger.info(f"Writing to file: {intervals_output_file}")
                            intervals.to_csv(intervals_output_file, index=False)
                        except Exception as e:
                            logger.error(f"Error writing to file: {intervals_output_file}")
                            logger.exception(e)

                        intervals["pm2.5_EPAc_1"] = intervals.apply(
                            lambda row: apply_epa_correction(
                                row.get("pm2.5_cf_1_1"),
                                row.get("relative_humidity_1"),
                                row.get("pm2.5_cf_1_2"),
                                row.get("relative_humidity_2")
                            ),
                            axis=1,
                        )
                        intervals["pm2.5_EPAc_1"] = intervals["pm2.5_EPAc_1"].round(1)
                        #We want the m_date to be the window start columns
                        intervals['m_date'] = intervals['window_start']
                        #Now, let's drop columns from the data frame we don't want saved in the file.
                        #relative_humidity_2 and pm2.5_cf_1_2 along with the count columns might not exist, so we set
                        #errors = ignore
                        intervals.drop(columns=['window_start', 'window_end', 'pm2.5_cf_1_1', 'pm2.5_cf_1_2',
                                                'relative_humidity_1', 'relative_humidity_2', 'pm2.5_cf_1_1_count',
                                                'pm2.5_cf_1_2_count', 'relative_humidity_1_count',
                                                'relative_humidity_2_count'], inplace=True, axis=1, errors='ignore')
                        file_platform_handle = platform_handle.replace('.', '_')
                        output_file = epa_corrected_directory / (f"{file_platform_handle}-{platform.properties['external_identifier']}-"
                                                              f"{start_date_time.strftime('%Y%m%dT%H%M%S')}-"
                                                              f"{end_date_time.strftime('%Y%m%dT%H%M%S')}.csv")
                        try:
                            logger.info(f"Writing to file: {output_file}")
                            intervals.to_csv(output_file, index=False)

                            corrected_file_list.append(str(output_file))
                        except Exception as e:
                            logger.error(f"Error writing to file: {output_file}")
                            logger.exception(e)
        except Exception as e:
            raise e

        logger.info(f"Finished ancillary_calculations_post_db_save in {time.perf_counter()-start_proc_time} seconds")

        return corrected_file_list

    @task()
    def archive_task(config_file_name: Path,
                     data_source_files: [],
                     normalized_header_files: [],
                     ancillary_calculations_data_files: []) :
        archive_all_files = Variable.get("ARCHIVE_ALL_FILES_IN_DIRECTORY")
        archive_directory = Path(Variable.get("ARCHIVE_DIRECTORY", default="./")) / Variable.get("PURPLE_AIR_WORKING_DIRECTORY", default="purple_air")
        base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./")) / Path(Variable.get("PURPLE_AIR_WORKING_DIRECTORY"))

        archive_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Starting archive_task with config file.")
        process_run_time = datetime.now()

        raw_data_archive_directory = archive_directory / Variable.get("RAW_DATA_DIRECTORY")
        raw_data_archive_directory.mkdir(parents=True, exist_ok=True)
        files_to_archive = data_source_files
        if archive_all_files:
            data_directory = base_dir / Path(Variable.get("RAW_DATA_DIRECTORY"))
            files_to_archive = data_directory.rglob("*.*")
        archive_and_zip(files_to_archive, raw_data_archive_directory, archive_directory, process_run_time)

        normalized_data_archive_directory = archive_directory / Variable.get("NORMALIZED_HEADER_DIRECTORY")
        normalized_data_archive_directory.mkdir(parents=True, exist_ok=True)
        files_to_archive = normalized_header_files
        if archive_all_files:
            data_directory = base_dir / Path(Variable.get("NORMALIZED_HEADER_DIRECTORY"))
            files_to_archive = data_directory.rglob("*.*")

        archive_and_zip(files_to_archive, normalized_data_archive_directory, archive_directory, process_run_time)
        #Ancillary data has 3 steps of file creation, the queried data, the 15 minute interval creation then
        #finally the ancillary calculations data.
        anicllary_data_archive_directory = archive_directory / Variable.get("EPA_CORRECTED_DIRECTORY")
        anicllary_data_archive_directory.mkdir(parents=True, exist_ok=True)
        files_to_archive = ancillary_calculations_data_files
        if archive_all_files:
            data_directory = base_dir / Path(Variable.get("EPA_CORRECTED_DIRECTORY"))
            files_to_archive = data_directory.rglob("*.*")
        archive_and_zip(files_to_archive, anicllary_data_archive_directory, archive_directory, process_run_time)

        logger.info(f"Completed archiving data files.")
        return

    def archive_and_zip(file_list: [],
                        directory_to_process: Path,
                        archive_directory: Path,
                        process_run_time: datetime) -> None:
        """
        Archive and zip files in the specified directory.

        Args:
            file_list (list): List of files to archive.
            directory_to_process (Path): Directory containing files to archive.
            archive_directory (Path): Directory to store the zipped archive.
            process_run_time (datetime): Timestamp of the processing run.
        """
        logger.info(f"Archiving data files: {directory_to_process}")

        for file in file_list:
            logger.info(f"Archiving file: {file}")
            try:
                archive_file(Path(file), directory_to_process, process_run_time)
            except Exception as e:
                logger.error(f"Unable to archive file: {file}")
        logger.info(f"Zipping directory: {archive_directory}")
        try:
            zip_files(directory_to_process)
        except Exception as e:
            logger.error(f"Unable to zip directory: {archive_directory}")
        return

    def bulk_insert_to_database(csv_file: Path, platform_nfo: Platform, insert_chunk_size: int):
        '''
        WHen importing large csv files, for performace we want to use this bulk insert function.
        :param csv_file:
        :param db:
        :return:
        '''
        csv_buffer = StringIO()
        buffer_count = 0
        total_inserted = 0
        total_skipped = 0

        raw_conn = db.dbEngine.raw_connection()
        with open(csv_file, "r") as csv_file_obj:
            file_start_time = time.perf_counter()
            row_entry_date = datetime.now()
            csv_reader = csv.DictReader(csv_file_obj)
            for row_ndx, row in enumerate(csv_reader):
                for obs_info in platform_nfo.obs_map:
                    # We build the name for each column we want which is >target_obs>_<s_order>. The date
                    # column has been renamed m_date during the normalize task.
                    try:
                        column_name = f"{obs_info.target_obs}_{obs_info.s_order}"
                        m_date = row['m_date']
                        try:
                            val = float(row[column_name])
                        except (ValueError, TypeError) as e:
                            logger.error(f"Unable to process row: {row}({row_ndx}) Value: {row[column_name]}")
                            logger.exception(e)
                        else:
                            # Write to buffer
                            csv_buffer.write(
                                f"{row_entry_date}\t{m_date}\t{val}\t"
                                f"{obs_info.sensor_id}\t{obs_info.m_type_id}\t"
                                f"{platform_nfo.longitude}\t{platform_nfo.latitude}\n"
                            )
                            buffer_count += 1

                            if buffer_count >= insert_chunk_size:
                                cursor = raw_conn.cursor()

                                buffer_count = 0
                                # Create a temp table. Because we might have duplicates, we use POSTGRES ability to handle
                                # decision on CONFLICTS.
                                # Create temporary table matching multi_obs structure (without constraints)
                                cursor.execute("""
                                    CREATE
                                        TEMP TABLE temp_multi_obs (
                                        row_entry_date TIMESTAMP,
                                        m_date TIMESTAMP,
                                        m_value FLOAT,
                                        sensor_id INTEGER,
                                        m_type_id INTEGER,
                                        m_lon FLOAT,
                                        m_lat FLOAT
                                    ) ON COMMIT DROP
                                """)
                                csv_buffer.seek(0)
                                cursor.copy_from(
                                    csv_buffer,
                                    'temp_multi_obs',
                                    sep='\t',
                                    columns=['row_entry_date', 'm_date', 'm_value',
                                             'sensor_id', 'm_type_id', 'm_lon', 'm_lat']
                                )

                                # Insert from temp to main table with duplicate handling
                                # Using the unique constraint: (m_date, m_type_id, sensor_id)
                                cursor.execute("""
                                               INSERT INTO multi_obs (row_entry_date, m_date, m_value,
                                                                      sensor_id, m_type_id, m_lon, m_lat)
                                               SELECT row_entry_date,
                                                      m_date,
                                                      m_value,
                                                      sensor_id,
                                                      m_type_id,
                                                      m_lon,
                                                      m_lat
                                               FROM temp_multi_obs ON CONFLICT (m_date, m_type_id, sensor_id) DO NOTHING
                                               """)

                                rows_inserted = cursor.rowcount
                                total_inserted += rows_inserted
                                total_skipped += (buffer_count - rows_inserted)

                                raw_conn.commit()
                                cursor.close()
                                logger.info(f"Inserted {rows_inserted} rows into temp_multi_obs. "
                                            f"Total skipped: {total_skipped} Total inserted: {total_inserted}")

                    except Exception as e:
                        raise e

            # Process remaining records
            if buffer_count > 0:
                try:
                    cursor = raw_conn.cursor()

                    cursor.execute("""
                                   CREATE
                                   TEMP TABLE temp_multi_obs (
                            row_entry_date TIMESTAMP,
                            m_date TIMESTAMP,
                            m_value FLOAT,
                            sensor_id INTEGER,
                            m_type_id INTEGER,
                            m_lon FLOAT,
                            m_lat FLOAT
                        ) ON COMMIT DROP
                                   """)

                    csv_buffer.seek(0)
                    cursor.copy_from(
                        csv_buffer,
                        'temp_multi_obs',
                        sep='\t',
                        columns=['row_entry_date', 'm_date', 'm_value',
                                 'sensor_id', 'm_type_id', 'm_lon', 'm_lat']
                    )

                    cursor.execute("""
                                   INSERT INTO multi_obs (row_entry_date, m_date, m_value,
                                                          sensor_id, m_type_id, m_lon, m_lat)
                                   SELECT row_entry_date,
                                          m_date,
                                          m_value,
                                          sensor_id,
                                          m_type_id,
                                          m_lon,
                                          m_lat
                                   FROM temp_multi_obs ON CONFLICT (m_date, m_type_id, sensor_id) DO NOTHING
                                   """)
                except Exception as e:
                    raise e
                rows_inserted = cursor.rowcount
                total_inserted += rows_inserted
                total_skipped += (buffer_count - rows_inserted)
                raw_conn.commit()
                cursor.close()
                logger.info(f"Inserted {rows_inserted} rows into temp_multi_obs. "
                            f"Total skipped: {total_skipped} Total inserted: {total_inserted}")

    def normalize_header(row: [], platform_nfo: Platform) -> []:
        corrected_header = []
        for column in row:
            if column == "time_stamp":
                corrected_header.append("m_date")
            else:
                obs_record = platform_nfo.obs_map.get_by_source(column)
                corrected_column = column
                if obs_record is not None:
                    corrected_column = f"{obs_record.target_obs}_{obs_record.s_order}"
                corrected_header.append(corrected_column)
        return corrected_header

    def get_requests_verify(ccrab_url):
        value = os.getenv("CCRAB_API_VERIFY")
        if value is None or value.strip() == "":
            parsed_url = urlparse(ccrab_url)
            if parsed_url.scheme == "https" and parsed_url.hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                return False
            return True

        normalized = value.strip().lower()
        if normalized in {"0", "false", "no", "off"}:
            return False
        if normalized in {"1", "true", "yes", "on"}:
            return True
        return value

    def load_config_file(configuration_file: Path) -> List[Any]:
        configuration_data = json.load(open(configuration_file))
        organizations_setup = []
        # Build our org and platform objects.
        for organization in configuration_data['organizations']:
            organizations_setup.append(Organization().from_dict(organization))

        return organizations_setup

    def round_down_dt(dt, round_to):
        delta = timedelta(minutes=round_to)
        return datetime.min + math_floor((dt - datetime.min) / delta) * delta

    configuration_file_path = get_configuration()

    # Resolve the mode at task runtime, then produce the same manifest shape for
    # either locally supplied files or files fetched from the PurpleAir API.
    run_config = decide_mode()
    run_manifest = acquire_data(configuration_file_path, run_config)
    csv_files_to_process = run_manifest["saved_data_files"]

    #We want to correct the headers from the Purple Air fields to our normalized names.
    normalized_header_data_files = normalize_headers_task(configuration_file_path, csv_files_to_process)

    #Let's now perform any other calculations we need to. We do this after saving to the database because
    #the Purple Air does not return ordered data.
    #ancillary_calculations_data_files = ancillary_calculations(configuration_file_path, normalized_header_data_files)

    #qaqcd_data = qaqc_task(CONFIG, normalized_header_data_files)
    initial_data_save_to_database = save_to_database_task.override(
        task_id="save_initial_data"
    )("initial_data_save", configuration_file_path, normalized_header_data_files)

    ancillary_calculations_data_files = ancillary_calculations_post_db_save(
        configuration_file_path,
        run_manifest["start_timestamp"],
        run_manifest["end_timestamp"],
    )

    ancillary_calculations_data_save_to_database = save_to_database_task.override(
        task_id="save_ancillary_data"
    )("ancillary_calculations_data_save", configuration_file_path, ancillary_calculations_data_files)

    archive = archive_task(configuration_file_path, csv_files_to_process,
                           normalized_header_data_files,
                           ancillary_calculations_data_files)

    # These are control dependencies: neither downstream task consumes the
    # upstream task's return value, so TaskFlow cannot infer them from arguments.
    initial_data_save_to_database >> ancillary_calculations_data_files
    ancillary_calculations_data_save_to_database >> archive

purple_air_processing()
