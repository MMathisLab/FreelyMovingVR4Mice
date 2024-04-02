import os
import numpy as np
import pickle
from pathlib import Path

from vr4mice.utils.logger import Logger
"""
    Script that populates database according on the input data from files and key2tables hints.
"""
logger = Logger.get_logger()

from vr4mice.actions.keys2tables_base import base
from vr4mice.actions.keys2tables_vr4mice import vr4mice

SKIP_DUPLICATES = True


def get_filenames(ext, path='/tmp') -> dict:
    """
    Get a dictionary of filenames with the specified extensions from the given path.

    Args:
    ext (list): List of file extensions to search for.
    path (str): Path to the directory to search for files. Default is '/tmp'.

    Returns:
    dict: A dictionary with keys as file extensions and values as lists of filenames with the corresponding extension.
    """

    output = dict()
    for file in os.listdir(path):
        for e in ext:
            if file.endswith(e):
                if e not in output.keys():
                    output[e] = list()
                output[e].append(file)
                break
    return output


def get_new_file(filename, path='/tmp'):
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
        with open(str(Path(path).joinpath(filename)), "rb") as fd:
            return pickle.load(fd), name


def check_keys(value, raw_data, key, schema) -> bool:
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

    for v in value:
        if v not in raw_data.keys():

            if v not in schema["local_def"]:
                if v not in schema["transformer"].keys() or \
                        (v in schema["transformer"].keys()
                         and schema["transformer"][v] not in raw_data.keys()):  # check exceptions

                    logger.info("[ALERT] " + str(v) +
                                " not found; can't insert data for " +
                                str(key))
                    return False
    return True


def populate(table_name, attributes, raw_data, schema) -> None:
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
        # check if there is a special processing for the generation of value of given attribute
        if a in schema["local_def"].keys():
            data[a] = schema["local_def"][a](raw_data=raw_data,
                                             key=a,
                                             transformer=schema["transformer"])
        else:  # dj_def-orientated
            label = a
            if a in schema["transformer"].keys():
                label = schema["transformer"][a]
            data[a] = raw_data[label]

    schema["dj_tables"][table_name].insert1(data,
                                            skip_duplicates=SKIP_DUPLICATES)
    logger.info("[POPULATED OK] " + str(table_name))  # todo check return code


def populate_rig(path) -> None:
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

    ext = [".npy", ".pickle"]  # format: pickle/npy

    dir_list = get_filenames(ext, path)

    if ".pickle" in dir_list.keys():

        for pickle_file in dir_list[".pickle"]:
            raw_data_pickle, dataset = get_new_file(pickle_file, path)

            raw_data_npy = None

            if ".npy" in dir_list.keys():  # todo(mary) optimize
                for npy_file in dir_list[".npy"]:
                    logger.info(npy_file)
                    # compare dataset
                    # (can be modified if names of files for same dataset are not similar)
                    if Path(npy_file).stem == dataset:
                        raw_data_npy, dataset = get_new_file(npy_file, path)
                        break

            # if .npy file is missing return
            if raw_data_npy is None:
                logger.info("RETURN")
                # todo problem
                return

            # all datasets combined
            raw_data = {**raw_data_pickle, **raw_data_npy}
            # populate all schemas
            schemas = [base, vr4mice]
            for schema in schemas:
                # populate all tables
                for table_name, attributes in schema["tables"].items(
                ):  # get attributes
                    if check_keys(attributes,
                                  raw_data,
                                  table_name,
                                  schema=schema):
                        populate(table_name,
                                 attributes,
                                 raw_data,
                                 schema=schema)
