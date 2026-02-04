import os
import pickle
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from vr4mice.actions.keys2tables_base import base
from vr4mice.actions.keys2tables_vr4mice import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice import schema as dj_schema

"""
    Script that populates database according on the input data from files and key2tables hints.
"""
logger = Logger.get_logger()


SKIP_DUPLICATES = True


def get_filenames(ext, path: str = "/tmp") -> dict:
    """
    Get a dictionary of filenames with the specified extensions from the given path.

    Args:
    ext (list): List of file extensions to search for.
    path (str): Path to the directory to search for files. Default is '/tmp'.

    Returns:
    dict: A dictionary with keys as file extensions and values as lists of filenames with the corresponding extension.
    """

    output = dict()
    file_list = sorted(os.listdir(path))

    for file in file_list:
        for e in ext:
            if file.endswith(e):
                if e not in output.keys():
                    output[e] = list()
                output[e].append(file)
                break
    return output


def get_new_file(filename, path: str = "/tmp"):
    """
    Load data from a new file and return it as a dictionary.

    Args:
        filename (str): The name of the file to load.
        path (str, optional): The path to the directory where the file is located.
                              Defaults to '/tmp'.

    Returns:
        Tuple[Dict, str]: A tuple containing two elements:
            - A dictionary containing the loaded data.
            - A string with the name of the file (without extension).
    """
    name = Path(filename).stem
    if Path(filename).suffix == ".npy":
        data = np.load(str(Path(path).joinpath(filename)), allow_pickle=True)
        return data.item(), name

    if Path(filename).suffix == ".pickle":
        data = pd.read_pickle(str(Path(path).joinpath(filename)))
        return data, name


def check_keys(value, raw_data, key, schema, none=True) -> bool:
    """
    Check if all keys in the given list `value` are present in the `raw_data` dictionary
    or can be derived from it using the schema information.

    Args:
        value (list): A list of keys to check.
        raw_data (dict): A dictionary containing the raw data to be validated.
        key (str): A string representing the current key being validated.
        schema (dict): A dictionary containing the schema information for the current key.

    Returns:
        A boolean value indicating whether all the keys in `value` are present in `raw_data`
        or can be derived from it using the schema information.

    Notes:
        - The `schema` dictionary should contain the following keys:
            - "local_def": A dictionary of local definitions to use when processing the raw data.
            - "transformer": A dictionary of transformation functions to use when processing the raw data.

        - If a key in `value` is not found in `raw_data`, the function checks whether it is defined in
          the `local_def` dictionary. If not, it checks whether it can be derived from `raw_data` using
          the `transformer` dictionary. If it can't be derived, the function logs an alert and returns False.

    todo: optimize, make list of potential none
    """
    if none:
        none_vals = dict()
    else:
        none_vals = None

    for v in value:
        if v not in raw_data.keys():

            if v not in schema["local_def"]:
                transformers = ["transformer"]
                transformers_schema = {}

                for t in transformers:
                    if t in schema.keys():
                        transformers_schema = schema[t]

                    if v not in transformers_schema.keys() or (
                        v in transformers_schema.keys()
                        and (transformers_schema[v] not in raw_data.keys())
                    ):
                        # todo: add check exceptions
                        if none:
                            logger.warning(
                                f"{v} not found; {v} will be presented as None."
                            )
                            none_vals[v] = None
                        else:
                            logger.warning(
                                f"{v} not found; can't insert data for {key}. Aborted."
                            )
                            return False, None

                    elif (
                        v in transformers_schema.keys()
                        and transformers_schema[v] in raw_data.keys()
                    ):
                        if v in none_vals.keys():
                            logger.warning(f"{v} found.")
                            del none_vals[v]
    return True, none_vals


def populate(
    table_name, attributes, raw_data, schema, srcf="/data", dstf="processed", move=True
) -> None:
    """
    Populates the given table in the database with the given attributes and raw data.

    Args:
        table_name (str): The name of the table to populate.
        attributes (list): A list of attributes to populate in the table.
        raw_data (dict): A dictionary containing the raw data to populate the table with.
        schema (dict): A dictionary containing information about the schema and tables.

    Notes:
        - The function populates the given table in the database with the data obtained from the
          raw_data dictionary.
        - If a special processing function is defined for a given attribute, it is used to generate
          the value of that attribute.
        - If duplicates are found, they are skipped and not inserted into the table.
        - The function logs a message indicating whether the population was successful or not.
    """
    data = dict()

    for a in attributes:
        print(a)
        # check if there is a special processing for the generation of value of given attribute
        if a in schema["local_def"].keys():
            data[a] = schema["local_def"][a](
                raw_data=raw_data,
                key=a,
                transformer=schema["transformer"],
                srcf=srcf,
                dstf=dstf,
                move=move,
            )
        else:  # dj_def-orientated
            label = a
            change = False
            transformers = ["transformer"]
            for t in transformers:
                if t in schema.keys():
                    if a in schema[t].keys():
                        label = schema[t][a]
                        change = True

                if label in raw_data.keys():
                    data[a] = raw_data[label]
                    if change:
                        logger.info(f"Note: {label} variable name changed to {a}")

    logger.info(f"Populating: {table_name}")  # todo check return code

    schema["dj_tables"][table_name].insert1(data, skip_duplicates=SKIP_DUPLICATES)
    logger.info(f"[POPULATED OK] {table_name}")  # todo check return code


def parse_date(filename):
    # Regular expression to match the date pattern in the filename
    date_pattern = r"(\d{4}-\d{2}-\d{2})"

    # Search for the date pattern in the filename
    match = re.search(date_pattern, filename)

    if match:
        # Extract the matched date string
        date_str = match.group(1)

        # Parse the date string into a datetime object
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")

        return parsed_date
    else:
        return None


def get_files_paths(
    dataset,
    remote_src: Optional[str] = None,
    local_src: str = "/data",
    data: str = "/data",
    filename: str = os.environ["IMG_SRC"],
):
    """
    Simulation of data from gui .npy, if it's missing

    Args:
        dataset: The name of the dataset, formatting is {mouse_name}-{doe}-{attempt}.
        remote_src: The source path for remote files.
        local_src: The source path for local files.
        data: The data path.
        filename: The base filename for the video files.

    """
    dlc_video_path = local_src + "/dlc_video"

    files_info = {
        "teensy_path": {
            "filename": dataset + ".pickle",
            "src": remote_src,
            "dst": local_src + data,
        },
        "dlc_path": {
            "filename": filename + "_" + dataset + "_DLC.hdf5",
            "src": remote_src,
            "dst": dlc_video_path,
        },
        "camera_path": {
            "filename": filename + "_" + dataset + "_TS.npy",
            "src": remote_src,
            "dst": dlc_video_path,
        },
        "video_path": {
            "filename": filename + "_" + dataset + "_VIDEO.avi",
            "src": filename + "_" + dataset + "_VIDEO.avi",
            "dst": dlc_video_path,  # false (remote only)
        },
        "proc_path": {
            "filename": filename + "_" + dataset + "_PROC",
            "src": remote_src,
            "dst": dlc_video_path,
        },
        "gui_output": {
            "filename": dataset + ".npy",
            "src": remote_src,
            "dst": local_src + data,
        },
        "video_meta": {"duration": None, "fps": None, "width": None, "height": None},
        "screen_recording_output": {
            "filename": dataset + ".mkv",
            "dst": "/vr4mice_screen_recordings/raw_screen_recordings/",
        },
        "time_stamp": None,
        "doe": parse_date(dataset),
        "dataset": dataset,
    }
    return files_info


def populate_rig(
    path="/data/data", gui=os.environ["GUI"], srcf="/data", dstf="processed", move=True
) -> None:
    """
    Populates database tables with data from files in the specified directory.

    Args:
        path (str): The path to the directory containing data files.
    Raises:
        OSError: If the specified directory does not exist.

    The function looks for data files with extensions ".npy" and ".pickle" in the
    specified directory, and assumes that files with the same name (excluding
    extension) correspond to the same dataset.

    For each ".pickle" file found, the function loads its data into a dictionary.
    It then looks for the corresponding ".npy" file and loads its data into the
    same dictionary. If no corresponding ".npy" file is found, the function logs
    an error message and returns.

    The function then iterates over a list of schemas and their associated tables.
    For each table, it checks if all required keys are present in the loaded data.
    If so, it populates the table in the database with data from the loaded data
    dictionary using the corresponding schema. If any required keys are missing,
    the function logs an error message and skips populating that table.

    dataset = name of file : mouse_name_doe_attempt
    """

    gui = os.environ.get("GUI", "false").lower() in ["true", "1", "yes"]

    if gui:
        ext = [".npy", ".pickle"]
    else:
        ext = [".pickle"]

    dir_list = get_filenames(ext, path)

    def move_dataset_files(dataset_name: str, base_path: str, dst_folder: str) -> None:
        dst_path = os.path.join(base_path, dst_folder)
        os.makedirs(dst_path, exist_ok=True)
        moved = False
        for ext in [".pickle", ".npy"]:
            filename = f"{dataset_name}{ext}"
            src = os.path.join(base_path, filename)
            if os.path.exists(src):
                shutil.move(src, os.path.join(dst_path, filename))
                moved = True
        if moved:
            logger.info(f"Moved raw files for {dataset_name} to {dst_path}")
        else:
            logger.info(f"No raw files found to move for {dataset_name}")

    if ".pickle" in dir_list.keys():

        for pickle_file in dir_list[".pickle"]:
            try:
                logger.info(f"Processing file: {pickle_file}")
                raw_data_pickle, dataset = get_new_file(pickle_file, path)
                key = f'dataset="{dataset}"'

                if (dj_schema.vr4mice.Dataset() & key).fetch(as_dict=True):
                    logger.info(f"{key} is already in the database, skip.")
                    if move:
                        move_dataset_files(dataset, path, dstf)
                    continue
                else:
                    logger.info(f"{key} not yet in the database, continue.")

                    raw_data_npy = None

                    if ".npy" in dir_list.keys():
                        for npy_file in dir_list[".npy"]:
                            if Path(npy_file).stem == dataset:
                                logger.info(f"Processing file: {npy_file}")
                                raw_data_npy, dataset = get_new_file(npy_file, path)
                                break

                    # if .npy file is missing return
                    if raw_data_npy is None:
                        if gui:
                            logger.warning(
                                f"Attention: .npy file from GUI was not found for {dataset}; \
                                As .npy files from gui were expected (gui flag is {gui}) the population will be aborted."
                            )
                            continue

                        logger.info(
                            f"Attention: .npy file from GUI was not found for {dataset}; \
                            As .npy files from gui can be skipped (gui flag is {gui}) the population will be continued."
                        )

                        # as there is no .npy, we have to restore some parts of raw_data
                        # (mostly info about filepaths location)
                        files_info = get_files_paths(
                            dataset=dataset,
                            remote_src=None,
                            local_src="/data",
                            data=path,
                        )  # paths correspond to docker env
                        raw_data = {**files_info, **raw_data_pickle}
                        schemas = [vr4mice]
                    else:
                        raw_data = {**raw_data_pickle, **raw_data_npy}
                        schemas = [base, vr4mice]

                    for schema in schemas:
                        for table_name, attributes in schema[
                            "tables"
                        ].items():  # get attributes
                            flag, none_vals = check_keys(
                                attributes, raw_data, table_name, schema=schema
                            )
                            if flag:
                                raw_data = {**raw_data, **none_vals}
                                populate(
                                    table_name,
                                    attributes,
                                    raw_data,
                                    schema=schema,
                                    srcf=srcf,
                                    dstf=dstf,
                                    move=move,
                                )

            except Exception as e:
                logger.warning(f"Population of raw data failed for {pickle_file}: {e}")

    elif ".npy" in dir_list.keys():  # case no pickle
        for npy_file in dir_list[".npy"]:
            try:
                raw_data_npy, dataset = get_new_file(npy_file, path)
                raw_data_npy["rig_id"] = 12
                raw_data_npy["license"] = "N/A"
                files_info = get_files_paths(
                    dataset=dataset, remote_src=None, local_src="/data", data=path
                )  # paths correspond to docker env
                raw_data = {**files_info, **raw_data_npy}
                schemas = [base]

                for schema in schemas:
                    for table_name, attributes in schema[
                        "tables"
                    ].items():  # get attributes
                        flag, none_vals = check_keys(
                            attributes, raw_data, table_name, schema=schema
                        )
                        if flag:
                            raw_data = {**raw_data, **none_vals}
                            populate(
                                table_name,
                                attributes,
                                raw_data,
                                schema=schema,
                                srcf=srcf,
                                dstf=dstf,
                                move=move,
                            )
            except Exception as e:
                logger.warning(f"Population of raw data failed for {npy_file}: {e}")
