import logging
import os
import pendulum
from airflow.sdk import dag, task, Variable
from typing import Dict, Any
from string import Template
from pathlib import Path
import json
from datetime import datetime
from datautilities.data_models.sampling_data_record import AttachmentModel, AnswerModel, SampleModel
from datautilities.data_models.sample_model_converters_class import Converters
from observationsdatabase.xenia_alchemy import xenia_alchemy, build_pg_connection_string
from sqlalchemy import exc
import requests
from ioos_qc.config import QcConfig
from ioos_qc.streams import PandasStream
from ioos_qc.results import CollectedResult, collect_results
import pandas as pd
from observationsdatabase.xenia_alchemy import xenia_alchemy
from observationsdatabase.XeniaTables import sample, sample_answer, sample_attachment

#logging.basicConfig(level=logging.DEBUG)
#requests_log = logging.getLogger("requests")
#requests_log.setLevel(logging.DEBUG)
REMOTE_DEBUG = False#Variable.get("REMOTE_DEBUG", default=False)

if REMOTE_DEBUG:
    import pydevd_pycharm

    pydevd_pycharm.settrace('localhost', port=5678, stdout_to_server=True, stderr_to_server=True)


logger = logging.getLogger(__name__)
logger.setLevel(logging.NOTSET)

def load_dag_config(config_name: str) -> Dict[str, Any]:
    """Load DAG-specific configuration from JSON file."""
    try:
        dag_dir = Path(__file__).parent
        config_path = dag_dir / 'configs' / f'{config_name}.json'

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            config = json.load(f)

        logger.info(f"Loaded config from {config_path}")
        return config

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise




@dag(
    schedule=None,
    start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
    catchup=False,
    tags=["survey123","ccrab"],
)
def survey123_processing():

    # Load at module level
    CONFIG = load_dag_config('survey123_config')

    @task()
    def import_task(config: {}) -> []:
        """
        #### import_task

        This task connects to the ARCGIS endpoint configured in the JSON file using the
          "base_url", "service","layer_id" configuration parameters.

        """
        DATE_FIELDS = ['CreationDate', 'EditDate']
        SAMPLE_DATE_FIELD = 'CreationDate'
        CREATOR_NAME_FIELD = 'enter_your_name'
        BASE_REST_QUERY = Template("$root_url/$service_name/FeatureServer/$layer_id/query")

        base_url = config.get("base_url")
        layer_id = config.get("layer_id")
        service = config.get("service")
        plugin_version = config.get("plugin_version")
        plugin_id = config.get("plugin_id")
        last_retrieved_record_date = config.get("last_retrieved_record_date", "1900-01-01 00:00:00")
        attachment_download_directory = config.get("attachment_directory")
        data_directory = config.get("raw_data_directory", None)

        try:
            saved_data_files = []
            request_url = BASE_REST_QUERY.substitute(root_url=base_url, layer_id=layer_id, service_name=service)

            params = {
                "where": f"EditDate > '{last_retrieved_record_date}'",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "json",
                "resultRecordCount": 1000
            }

            logger.info(f"Querying {request_url}.")
            resp = requests.get(request_url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            features = data.get("features", [])
            fields_info = data.get("fields", [])
            records = []
            task_run_datetime = datetime.now()
            # process each feature here (this replaces create_data_records task)
            for feature_ndx,feature in enumerate(features):
                logger.info(f"Processing feature {feature_ndx}")
                attrs = feature.get("attributes", {})
                geom = feature.get("geometry", {})
                sample_rec = SampleModel(source="survey123_processing_task", timestamp=task_run_datetime)
                sample_rec.plugin_id = plugin_id
                sample_rec.plugin_version = plugin_version
                sample_rec.latitude = geom.get("y")
                sample_rec.longitude = geom.get("x")
                for ndx,field_info in enumerate(fields_info):
                    field = field_info['name']
                    form_entry = AnswerModel(key=field)
                    form_entry.question_text = field_info['alias']

                    #These fields are ESRI record specific, they are not form data.
                    if field != 'objectid' and field != 'globalid':
                        form_entry.answer_order = ndx
                    if field == 'globalid':
                        sample_rec.name = feature['attributes'][field]
                    if field == CREATOR_NAME_FIELD:
                        sample_rec.collector_name = feature['attributes'][field]
                    question_key = field
                    if field in DATE_FIELDS:
                        epoch_time = feature['attributes'][field] / 1000.0
                        if field == SAMPLE_DATE_FIELD:
                            sample_rec.sample_date = datetime.fromtimestamp(epoch_time)
                        form_entry.value_text = datetime.fromtimestamp(epoch_time).strftime("%Y-%m-%dT%H:%M:%SZ")
                    else:
                        if type(feature['attributes'][question_key]) == str:
                            form_entry.value_text = feature['attributes'][question_key]
                        elif (type(feature['attributes'][question_key]) == int or
                              type(feature['attributes'][question_key]) == float):
                            form_entry.value_numeric = feature['attributes'][question_key]
                        else:
                            form_entry.value_text = feature['attributes'][question_key]
                    sample_rec.answers.append(form_entry)
                sample_rec.attributes = attrs


                # If attachments are needed: call attachments REST endpoint for each objectid
                objectid = attrs.get("objectid")
                if objectid:
                    attachments_url = (f"https://services1.arcgis.com/5Gtv38l8677OspKm/ArcGIS/rest/services/"
                                       "survey123_732a27a29cb74de8aa765aa5140631c2_results/FeatureServer/0/"
                                       f"{objectid}/attachments?f=json")
                    ar = requests.get(attachments_url, timeout=30)
                    if ar.ok:
                        al = ar.json().get("attachmentInfos", [])
                        for ndx,att in enumerate(al):
                            download_url = (f"https://services1.arcgis.com/5Gtv38l8677OspKm/ArcGIS/rest/services/"
                                            "survey123_732a27a29cb74de8aa765aa5140631c2_results/FeatureServer/0/"
                                            f"{objectid}/attachments/{att['id']}")
                            # download with requests and save locally
                            logger.info(f"Downloading {download_url}")
                            dl = requests.get(download_url, timeout=60)
                            if dl.ok:
                                try:
                                    dl_filename = Path(att['name'])
                                    out_path = (Path(attachment_download_directory) /
                                                f"{sample_rec.name}-{ndx}{dl_filename.suffix}")
                                    out_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(out_path, "wb") as fh:
                                        logger.info(f"Writing {out_path}")
                                        fh.write(dl.content)

                                    attachment_obj = AttachmentModel(filename=out_path.name)
                                    attachment_obj.storage_type = "local"
                                    attachment_obj.storage_path = attachment_download_directory
                                    sample_rec.attachments.append(attachment_obj)

                                except Exception as e:
                                    raise e
                try:
                    validated_rec = SampleModel.model_validate(sample_rec)

                    data_path = Path(data_directory)
                    data_path.mkdir(parents=True, exist_ok=True)
                    saved_data_files.append(object_save(validated_rec, data_path))

                except Exception as e:
                    logger.exception(e)

            logger.info(f"Number of survey123 records processed: {len(records)}")

            return saved_data_files

        except Exception as e:
            raise e
    @task()
    def qaqc_task(config: {}, saved_data: []) -> []:
        """
        #### qaqc_task task
        This task runs the qaqc process configured in the "qaqc" setup in the JSON config file.

        **Inputs:** saved_data
        **Outputs:** list[dict]
        """
        qaqc_directory = config.get("qaqc_data_directory", None)
        qc_config = config.get("qaqc", None)['config']
        if qaqc_directory is not None:
            qaqc_directory = Path(qaqc_directory)
            qaqc_directory.mkdir(parents=True, exist_ok=True)
        else:
            raise Exception("qaqc directory not specified")

        qc = QcConfig(qc_config)
        qaqcd_files = []
        #The survey data is not flat columnar data that the qartod needs. We get a list of the keys
        #in the config, then we'll build the data frame for the qartod processing. The survey answer data
        #is a list of dictionaries, what we have to do is use the qartod data type config param which is
        #the "key" field in the answer. The data field we use is then the value_numeric.
        answer_keys_to_test = qc.config.keys()
        for data_file in saved_data:
            logger.info(f"Starting qaqc_task on file: {data_file}")
            try:
                test_df = pd.read_csv(data_file)
                #Let's add a qaqc column.
                test_df['qaqc'] = ''

                #Build a dataframe based on these two columns that will contain the data sources we want to qaqc.
                df = test_df[['question_key','value_numeric']].copy()

                # The survey data is not a flat file format, so we have to use the key to get the row we want,
                # then we use the numeric field.
                #The dataframe from the CSV has a column of question_key and value_numeric. We search for the answers
                #we need to QAQC in the answer_keys_to_test and create a new data frame based on those results.
                #We then pivot the dataframe so the answers are the columns and then the value_numeric are the rows.
                s = df[df["question_key"].isin(answer_keys_to_test)].set_index("question_key")["value_numeric"]
                df = s.to_frame().T.reset_index(drop=True)
                # sometimes the columns have a name (from the index); remove it
                df.columns.name = None
                p_df = PandasStream(df)


                runner = list(p_df.run(qc))
                results = collect_results(runner, how="list")

                #Now we need to add the qaqc results back into the original dataframe by searching the row using the
                #question_key and then setting the value in the qaqc column
                for result in results:
                    test_df.loc[test_df['question_key'] == result.stream_id, 'qaqc'] = result.results[0]
                src_path = Path(data_file)
                qaqc_filename = qaqc_directory / f"{src_path.name}-qaqc.csv"
                logger.info(f"Writing qaqc file: {qaqc_filename}")
                test_df.to_csv(qaqc_filename, index=False)

                qaqcd_files.append('qaqc')

            except Exception as e:
                raise e
        return(qaqcd_files)
    @task()
    def save_to_database_task(config: {}, saved_data: []):
        """
        #### save_to_database_task task
        THis task processes the CSV files in the saved_data parameter and saves the data into the database.

        """
        #Grab the database connection parameters from the Airflow variables.
        CCRAB_DB_HOST = Variable.get("CCRAB_DB_HOST", default=None)
        CCRAB_DB_USER = Variable.get("CCRAB_DB_USER", default=None)
        CCRAB_DB_PASSWORD = Variable.get("CCRAB_DB_PASSWORD", default=None)
        CCRAB_DATA_DB = Variable.get("CCRAB_DATA_DB", default=None)

        if None not in (CCRAB_DB_USER, CCRAB_DB_PASSWORD, CCRAB_DB_HOST, CCRAB_DATA_DB):
            #Connect to the database
            xenia_db = xenia_alchemy()
            #build_pg_connection_string(username: str, password: str, host: str, database: str, port: int=5432) -> URL:
            connection_str = build_pg_connection_string(CCRAB_DB_USER,
                                                        CCRAB_DB_PASSWORD,
                                                        CCRAB_DB_HOST,
                                                        CCRAB_DATA_DB,
                                                        5432)
            logger.info(f"Connecting to database: {CCRAB_DATA_DB}")

            xenia_db.connect_db(connection_str)
            saved_data_files = []
            # Let's take the SampleModel and convert it to the database model.
            rec_to_db_rec_converter = Converters(pydantic_sample_cls=SampleModel,
                                                 pydantic_answer_cls=AnswerModel,
                                                 pydantic_attachment_cls=AttachmentModel,
                                                 sa_sample_cls=sample,
                                                 sa_answer_cls=sample_answer,
                                                 sa_attachment_cls=sample_attachment,
                                                 field_map=None)
            for data_file in saved_data:
                try:
                    with (open(data_file, "r") as json_file):
                        json_data = json.load(json_file)
                        # Create the model from json_data
                        sample_rec = SampleModel.model_validate(json_data)
                        logger.info(f"Saving sample record: {sample_rec.name} to database")
                        sample_row, answer_rows, attachment_rows = \
                            rec_to_db_rec_converter.pydantic_to_sqlalchemy_sample(sample_rec)
                        sample_row.answers = answer_rows
                        sample_row.attachments = attachment_rows
                        try:
                            xenia_db.add_rec(sample_row, True)
                        except exc.IntegrityError as e:
                            logger.debug(f"Duplicate record: {sample_rec.name} in database, not committed.")
                except Exception as e:
                    raise e

            logger.info(f"Disconnecting from database: {CCRAB_DATA_DB}")
            xenia_db.disconnect()
        else:
            logger.error("Database airflow variables not set, cannot save data.")
    def object_save(sample_rec: SampleModel, data_directory: Path) -> str:
        logger.info("Starting object_save_task")
        saved_file = None
        if data_directory is not None:
            try:
                saved_file = data_directory / f"{sample_rec.name}.csv"
                sample_rec.export_to_csv(path=saved_file,
                                          include_answers=True,
                                          include_attachments=True)
            except Exception as e:
                logger.error(f"Unable to write survey123 object to {saved_file}")
                raise e
            '''
            json_output_file = save_directory.joinpath(f"{sample_rec.name}.json")
            json_output_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(json_output_file, "w") as out_file:
                    output_json = sample_rec.model_dump_json(indent=2)
                    out_file.write(output_json)
                    logger.info(f"Saved survey123 object to {json_output_file}")
                    saved_file = str(json_output_file)
            except Exception as e:
                logger.error(f"Unable to write json file: {json_output_file} ")
                raise e
            '''
        return str(saved_file)

    saved_data = import_task(CONFIG)
    qaqcd_data = qaqc_task(CONFIG, saved_data)
    #save_to_database_task(qaqcd_data)

survey123_processing()

