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


def zip_directory_relative(source_dir: Path, output_zippath: Path, remove_source_after_zip: bool = True):
    # Convert input to a resolved, absolute Path object
    source_path = source_dir.resolve()

    with zipfile.ZipFile(output_zippath, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # rglob("*") recursively finds all files and subfolders
        for item in source_path.rglob('*'):
            if item.is_file():
                # Extract the path relative to the root source directory
                relative_path = item.relative_to(source_path)

                # Write to zip: item is the disk location, relative_path is the internal ZIP path
                zipf.write(item, arcname=relative_path)
    #Now that the files are zipped, let's remove them from the source directory
    if remove_source_after_zip:
        for item in sorted(source_path.rglob('*'), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                # item.rmdir() only works if the directory is empty
                item.rmdir()

def add_to_archive_zip(source_file: Path, destination_zip: Path) -> None:
    logger = logging.getLogger()

    logger.info(f"Adding file {source_file} to zip {destination_zip}")
    file_mode = 'a'
    if not destination_zip.exists():
        logger.info(f"Archive zip file {destination_zip} doesn't exist, so we're creating it.")
        file_mode = 'w'
    with zipfile.ZipFile(destination_zip, file_mode) as zip_file:
        zip_file.write(source_file,
                       arcname=source_file.name,
                       compress_type=zipfile.ZIP_DEFLATED)
        #Now let's remove the run zip.
        logger.info(f"Removing run zip file: {source_file} since it is now archived.")
        os.remove(source_file)

    return