from pathlib import Path
import os
import glob
import logging
import zipfile
from datetime import datetime
import shutil
def archive_file(source_filename: Path, archive_directory: Path, now_time: datetime):
    logger = logging.getLogger()
    try:
        now_time_str = now_time.strftime("%Y%m%d%H%M%S")
        archive_filename = archive_directory / f"{source_filename.stem}-{now_time_str}{source_filename.suffix}"
        logger.info(f"Archiving input file: {str(source_filename)} to {str(archive_filename)}")
        shutil.copy(source_filename, archive_filename)
        source_filename.unlink()
        #os.rename(source_filename, archive_filename)
    except Exception as e:
        raise e

def zip_files(archive_directory: Path):
    logger = logging.getLogger()
    if archive_directory:
        logger.info("Zipping files.")
        archive_list = archive_directory.glob("*.csv")
        zip_list = {}
        compression = zipfile.ZIP_DEFLATED
        for file in archive_list:
            full_filename = archive_directory / file
            file_stat = full_filename.stat().st_mtime
            file_time = datetime.fromtimestamp(file_stat).date()
            date_key = file_time.strftime('%Y-%m-%d')
            if date_key not in zip_list:
                zip_list[date_key] = []

            zip_list[date_key].append(file)

        for date_key in zip_list:
            zip_filename = archive_directory / f"{date_key}.zip"
            mode = 'w'
            if os.path.exists(zip_filename):
                mode = 'a'
            try:
                logger.info(f"Opening zip file: {zip_filename}")
                zip_file_obj = zipfile.ZipFile(zip_filename, mode=mode)
            except Exception as e:
                raise e
            else:
                try:
                    for file_to_zip in zip_list[date_key]:
                        logger.info(f"Zipping file: {file_to_zip}")
                        full_filename = archive_directory / file_to_zip
                        zip_file_obj.write(full_filename, file_to_zip, compress_type=compression)
                        #After zipping, we can delete the .csv.
                        os.remove(full_filename)
                except Exception as e:
                    logger.exception(e)
                zip_file_obj.close()

                logger.info("Finished zipping files.")
