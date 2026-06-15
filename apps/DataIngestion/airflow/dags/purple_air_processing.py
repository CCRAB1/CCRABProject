import os
import logging
import pendulum
import csv
import time
from io import StringIO
from airflow.sdk import dag, task, Variable
from airflow.task.trigger_rule import TriggerRule
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from urllib.parse import urlparse

from datetime import datetime, timedelta
from django.db import IntegrityError, transaction
from datautilities.purple_air_api.PurpleAPIWrapper import (
    PurpleAirClient,
)
from packages.django_setup import setup_django
from datautilities.ccrab_api.client import CCRABRestClient, CCRABAuthenticationError
from observationsdatabase.xenia_obs_map import Organization, Platform
from packages.archiving import archive_file, zip_files
from ioos_qc.config import QcConfig
from ioos_qc.streams import PandasStream
from ioos_qc.results import CollectedResult, collect_results
import pandas as pd
from packages.pycharm_debugging import maybe_attach_debugger

logger = logging.getLogger(__name__)
logger.setLevel(logging.NOTSET)

remote_debug = os.getenv("AIRFLOW_REMOTE_DEBUG")
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


@dag(
    dag_id="purple_air_processing",
    schedule=None,
    start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
    catchup=False,
    tags=["purpleair","ccrab"],
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
    def decide_mode(mode: str) -> Dict:
        """
        #### decide_mode task

        Decide whether to run 'rest' or 'local' mode.
        mode can be provided as DAG conf, Airflow Variable, or left None to run 'auto' detection.
        Returns a small config dict with resolved_mode and useful paths.

        **Inputs:** mode
        **Outputs:** dict
        """
        # precedence: dagrun.conf -> supplied arg -> Variable -> auto
        #dag_conf_mode =

        base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
        local_path = base_dir / Path(Variable.get("PURPLE_AIR_WORKiNG_DIRECTORY")) / Path(Variable.get("RAW_DATA_DIRECTORY"))
        # If user passes a conf via dag run, Airflow will pass it; we handle via Variable for now.
        if mode is not None:
            requested = mode.lower()
        else:
            requested = Variable.get("purple_air_csv_pipeline_mode", "auto").lower()

        assert requested in ("auto", "local", "rest"), "mode must be 'auto', 'local', or 'rest'"

        local_path.mkdir(parents=True, exist_ok=True)

        # auto-detect: if CSV files exist, use local. Otherwise use rest.
        if requested == "auto":
            found = list(local_path.glob("*.csv"))
            resolved_mode = "local" if len(found) > 0 else "rest"
        else:
            resolved_mode = requested

        return {"mode": resolved_mode, "directory_to_process": str(local_path)}

    @task.branch()
    def branch_on_mode(mode: str) -> str:
        """
        #### branch_on_mode task
        Branch to task_id "list_local" or "fetch_rest".
        Must return the *task_id* (string) of the next task to run.

        **Inputs:** cfg
        **Outputs:** string
        """
        if mode == "local":
            return "list_local"     # task_id of the local-listing task
        else:
            return "fetch_rest"     # task_id of the REST-fetching task

    @task(task_id="list_local")
    def list_local_files(local_directory: str) -> []:
        """
        #### list_local_files task

        Search the local_directory for all CSV files in the local directory.
        Input is the local directory, the output is a list of CSV files in that directory.

        **Inputs:** local_directory
        **Outputs:** list[dict]
        """
        data_directory = Path(local_directory)
        local_csv_list = list(data_directory.glob("*.csv"))
        return [str(file_path) for file_path in local_csv_list]

    @task(task_id="list_local")
    def list_local_files(local_directory: str) -> []:
        """
        #### list_local_files task

        Search the local_directory for all CSV files in the local directory.
        Input is the local directory, the output is a list of CSV files in that directory.

        **Inputs:** local_directory
        **Outputs:** list[dict]
        """
        data_directory = Path(local_directory)
        local_csv_list = list(data_directory.glob("*.csv"))
        return [str(file_path) for file_path in local_csv_list]

    @task(task_id="fetch_rest")
    def fetch_data_task(config_file_name: Path) -> list[Any]:
        """
        #### fetch_data_task task
        Using the Purple AIr API, this task retrieves the data for the platforms setup in the JSON config.

        **Inputs:** config
        **Outputs:** list[]
        """
        try:
            start_time = time.perf_counter()
            logger.info(f"Starting fetch_data_task with config file: {config_file_name}")
            configuration_data = json.load(open(config_file_name))
            org_list = []
            #Build our org and platform objects.
            for organization in configuration_data['organizations']:
                org_list.append(Organization().from_dict(organization))

            base_dir = Path(Variable.get("BASE_WORKING_DIRECTORY", "./"))
            data_directory = base_dir / Path(Variable.get("PURPLE_AIR_WORKiNG_DIRECTORY")) / Path(Variable.get("RAW_DATA_DIRECTORY"))
            data_directory = Path(data_directory)
            data_directory.mkdir(parents=True, exist_ok=True)

            last_retrieved_record_date = Variable.get("last_retrieved_record_date", "1900-01-01 00:00:00")
            purple_air_base_url = Variable.get("PURPLE_AIR_API_BASE_URL", None)
            purple_air_api_key = Variable.get('PURPLE_AIR_API_KEY', None)
            purple_api = PurpleAirClient(api_key=purple_air_api_key, base_url=purple_air_base_url)

            saved_data_files = []
            platform_count = 0
            for organization in org_list:
                platform_handles = organization.list_platform_handles()
                platform_count += len(platform_handles)
                #organization = configuration_data['organizations'][organization_id]
                #platform_handles = [platform['platform_handle'] for platform in organization['platforms']]
                for platform_handle in platform_handles:
                    platform = organization.get_platform(platform_handle)
                    external_indentifier = platform.properties['external_identifier']
                    end_date = datetime.now()
                    start_date = end_date - timedelta(hours=1)
                    try:
                        #These are the sensors we want to retrieve from PUrple Air API.
                        fields = [obs['source_obs'] for obs in platform.observations]

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
                        raise e
                    break
            logger.info(f"Completed fetch_data_task in {time.perf_counter()-start_time} seconds for {platform_count} platforms")
            return saved_data_files

        except Exception as e:
            raise e

    @task()
    def normalize_headers_task(config_file_name: Path, uncorrected_data_files: []) -> list[Any]:
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
            header_corrected_directory = base_directory / Path(Variable.get("PURPLE_AIR_WORKiNG_DIRECTORY")) / Path(Variable.get("NORMALIZED_HEADER_DIRECTORY"))
            #Let's make sure the directory exists.
            header_corrected_directory.mkdir(parents=True, exist_ok=True)

            corrected_file_list = []
            org_list = []
            #Build our org and platform objects.
            for organization in configuration_data['organizations']:
                org_list.append(Organization().from_dict(organization))


            #The file names are platform_handle-sensor_id-start_date-end_date.csv
            for file in uncorrected_data_files:
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
                corrected_file = header_corrected_directory / f"{file_path.stem}-corrected.csv"
                logger.info(f"Reading source file: {file} Writing corrected file: {corrected_file}")
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
                    corrected_file_list.append(str(corrected_file))
        except Exception as e:
            raise e
        logger.info(f"Completed normalize_headers_task in {time.perf_counter()-start_time} seconds")
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
        #Grab the database connection parameters from the Airflow variables.
        PURPLEAIR_TASK_LOG_INSERTS = Variable.get("PURPLEAIR_TASK_LOG_INSERTS", deserialize_json=True, default=0)
        PURPLEAIR_BULK_INSERT_FILE_SIZE = Variable.get("PURPLEAIR_BULK_INSERT_FILE_SIZE", deserialize_json=True, default=1000000)
        PURPLEAIR_CHUNK_SIZE = Variable.get("PURPLEAIR_CHUNK_SIZE", deserialize_json=True, default=1000)
        try:
            setup_django()

            from platforms_app.models import Multi_obs
            configuration_data = json.load(open(config_file_name))
            organizations_setup = []
            # Build our org and platform objects.
            for organization in configuration_data['organizations']:
                organizations_setup.append(Organization().from_dict(organization))

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
                                    m_date = row['m_date']
                                    try:
                                        val = float(row[column_name])
                                    except (ValueError, TypeError) as e:
                                        logger.error(f"Unable to process row: {row}({row_ndx}) Value: {row[column_name]}")
                                        logger.exception(e)
                                    else:
                                        if PURPLEAIR_TASK_LOG_INSERTS:
                                            if row_ndx % 1000 == 0:
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
                                except Exception as e:
                                    raise e
                    logger.info(f"Processed {row_ndx} rows from file: {file} into the database in: "
                                f"{time.perf_counter()-file_start_time} seconds")

        except Exception as e:
            raise e
    # Merge / join task
    @task(task_id="merge_file_lists", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def merge_file_lists(local_files: Optional[List[str]] = None, rest_files: Optional[List[str]] = None) -> List[str]:
        """
        After branching, only one of local_files/rest_files will be present.
        This merge returns whichever is not None/empty.
        Trigger rule ensures it runs even if one upstream was skipped.
        """
        chosen = local_files or rest_files or []
        # make sure it's a list (not None)
        return chosen

    @task()
    def archive_task(config_file_name: Path, data_source_files: [], normalized_header_files: []) :
        archive_directory = Path(Variable.get("ARCHIVE_DIRECTORY", default="./")) / Variable.get("PURPLE_AIR_WORKiNG_DIRECTORY", default="purple_air")
        archive_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Starting archive_task with config file.")
        logger.info("Archiving source data files.")
        process_run_time = datetime.now()
        raw_data_archive_directory = archive_directory / Variable.get("RAW_DATA_DIRECTORY")
        raw_data_archive_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving raw data files: {raw_data_archive_directory}")

        for file in data_source_files:
            logger.info(f"Archiving file: {file}")
            try:
                archive_file(Path(file), raw_data_archive_directory, process_run_time)
            except Exception as e:
                logger.error(f"Unable to archive file: {file}")
        logger.info(f"Zipping directory: {archive_directory}")
        try:
            zip_files(raw_data_archive_directory)
        except Exception as e:
            logger.error(f"Unable to zip directory: {archive_directory}")

        normalized_data_archive_directory = archive_directory / Variable.get("NORMALIZED_HEADER_DIRECTORY")
        normalized_data_archive_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving normalized data files: {normalized_data_archive_directory}")

        for file in normalized_header_files:
            logger.info(f"Archiving file: {file}")
            try:
                archive_file(Path(file), normalized_data_archive_directory, process_run_time)
            except Exception as e:
                logger.error(f"Unable to archive file: {file}")
        logger.info(f"Zipping directory: {archive_directory}")
        try:
            zip_files(normalized_data_archive_directory)
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

    configuration_file_path = get_configuration()

    #Figure out how we are running. We could be fetching new data from the Purple AIr API, or
    #we could be processing previous files.
    run_config = decide_mode(None)

    branch = branch_on_mode(['mode'])

    configuration_file_path >> run_config >> branch

    #local_file_list = []
    local_file_list = list_local_files(run_config['directory_to_process'])
    remote_file_list = fetch_data_task(configuration_file_path)
    # Wire branch to both candidate tasks. Branch operator expects task ids returned above.
    branch >> local_file_list
    branch >> remote_file_list

    # Merge results (merge task has TriggerRule so it runs even when a branch is skipped)
    csv_files_to_process = merge_file_lists(local_files=local_file_list, rest_files=remote_file_list)

    #We want to correct the headers from the Purple Air fields to our normalized names.
    #We want to correct the headers from the Purple Air fields to our normalized names.
    normalized_header_data_files = normalize_headers_task(configuration_file_path, csv_files_to_process)

    #qaqcd_data = qaqc_task(CONFIG, normalized_header_data_files)
    save_to_database_task(configuration_file_path, normalized_header_data_files)

    archive_task(configuration_file_path, csv_files_to_process, normalized_header_data_files)

purple_air_processing()

