import logging.config
import time
from multiprocessing import Event, Process, Queue, current_process

from sqlalchemy import exc

from .database_settings import DatabaseConfiguration
from .xenia_alchemy import xenia_alchemy

logger = logging.getLogger(__name__)


class MultiProcessDataSaver(Process):
    def __init__(self, database_configuration: DatabaseConfiguration, records_before_commit):
        Process.__init__(self)
        self.logger = logger
        self.data_queue = Queue()
        self._stop_event = Event()
        self.database_configuration = database_configuration
        self._database_connection = None
        self._records_before_commit = records_before_commit

    def run(self):
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"{current_process()} data saver started.")
            process_data = True
            db = xenia_alchemy()
            connection_string = self.database_configuration.get_connection_string()
            if (db.connect_db(connection_string, False)):
                logger.info(f"Successfully connect to DB: {self.database_configuration.database_name}")
            else:
                logger.error(f"Unable to connect to DB: {self.database_configuration.database_name}. Terminating process.")
                process_data = False

            if db is not None:
                start_time = time.time()
                rec_count = 0
                while process_data:
                    data_rec = self.data_queue.get()
                    if data_rec is not None:
                        try:
                            db.session.add(data_rec)
                            if (rec_count % self._records_before_commit) == 0:
                                db.session.commit()

                            val = ""
                            if data_rec.m_value is not None:
                                val = "%f" % (data_rec.m_value)
                            logger.debug(
                                f"Adding record Sensor: {data_rec.sensor_id} Datetime: {data_rec.m_date} Value: {val}")

                            if ((rec_count % 10) == 0):
                                try:
                                    logger.debug(f"Approximate record count in DB queue: {self.data_queue.qsize()}")
                                # We get this exception under OSX.
                                except NotImplementedError:
                                    pass

                                rec_count += 1
                        # Trying to add record that already exists.
                        except exc.IntegrityError:
                            logger.error(f"Duplicate sensor id: {data_rec.sensor_id} Datetime: {data_rec.m_date}")
                            db.session.rollback()
                        except Exception as e:
                            db.session.rollback()
                            logger.exception(e)

                    else:
                        process_data = False
                        db.session.commit()

                db.disconnect()
                logger.debug(f"{current_process().name} completed in {time.time() - start_time} seconds.")

        except Exception as e:
            logger.exception(e)
            if db is not None:
                db.disconnect()