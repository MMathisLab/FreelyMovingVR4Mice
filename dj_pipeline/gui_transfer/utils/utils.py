import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import QComboBox, QLabel, QLineEdit, QPlainTextEdit

import numpy as np
from config.config import config, logger
from utils.alert import AlertMsg
from utils.session_files import check_file_format


def load_dj_input(path_dj_data, path_json):
    """
    Function to get data from .npy file from database
    Initialisation step

    Args:
    path_dj_data (str): Path to the .npy file.
    path_json (str): Path to the JSON cache file.

    Returns:
    tuple: A tuple containing the following values:
        dj_dict (dict): A dictionary containing data from the .npy file.
        date (datetime): A timestamp representing the current date and time.
        json_dict (dict): A dictionary containing data from the JSON file.
    """

    # load dictionary with entries of the dropdown menus
    dj_data = np.load(path_dj_data, allow_pickle=True)
    dj_dict = dj_data.item()
    json_dict = dict()

    # get db import related datetime
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")

    if Path(path_json).exists():
        with open(path_json) as json_file:
            json_dict = json.load(json_file)

    return dj_dict, date, json_dict


def get_dataset(info_mouse, info_exp):
    """
    Function to create a dataset name that will be associated with all recorded videos
    during this session and used for the output directory.

    Args:
    info_mouse (dict): A dictionary containing information about the mouse.
    info_exp (dict): A dictionary containing experiment-related information.

    Returns:
    str: A string representing the name of the dataset.
    """
    # create file extension for the server, format? ->  different for pipelines?

    dataset = (
        str(info_mouse["mouse_name"])
        + "_"
        + str(info_exp["doe"])
        + "_"
        + str(info_exp["attempt"])
    )

    return dataset


def generate_file(args):
    """
    Function that saves all data to the output directories. Generated .npy data
    goes in the gui_output folder, and for caching, a local cache.json file is used.

    Args:
        args (dict): A dictionary containing the following keys:
            "mouse" (object): An object containing information about the mouse.
            "exp" (object): An object containing experiment-related information.
            "transfer" (object): An object containing transfer-related information.

    Returns:
        tuple: A tuple containing the following values:
            output_file1 (Path): A path to the .npy output file.
            output_file2 (Path): A path to the .json output file.
    """
    # precise for dataset params
    info_mouse = args["mouse"].get_info()
    info_exp = args["exp"].get_info()

    filename = get_dataset(info_mouse, info_exp)

    extra_info = {"time_stamp": datetime.now(), "dataset": filename}

    data = dict()
    for a in args.values():
        data = {**data, **a.get_info()}

    data = {**data, **extra_info}
    p = config.get_gui_output_folder_path

    # .npy
    if not Path(p).exists():
        Path(p).mkdir(parents=True, exist_ok=True)
    output_file1 = Path(p).joinpath(filename + ".npy")
    np.save(str(output_file1), data)

    # .json
    output_file2 = Path(p).joinpath(filename + ".json")
    with open(output_file2, "w") as output_file:
        json.dump(data, output_file, indent=2, sort_keys=True, default=str)
    # output_file2 = Path(p).joinpath(filename + '.json')

    # caching update
    output_file3 = str(config.get_cache_file_path)
    data = {**args["transfer"].get_cache_paths(), **data}

    with open(output_file3, "w") as output_file:
        json.dump(data, output_file, indent=2, sort_keys=True, default=str)

    return output_file1, output_file2


def check_missing_data(widget, args):
    """
    Check if any required input fields in the GUI are empty, and display an alert message if so.

    Args:
      widget (QWidget): The widget on which the alert message should be displayed.
      args (dict): A dictionary containing information entered by the user in various input fields of the GUI.

    Returns:
      bool: True if all required input fields have been filled, False otherwise.
    """
    # check that nothing is empty (if err -> window)
    empty_dict = dict()

    # if selected_mouse_info == empty_dict:
    #    # alert please fill the mouse info
    #    msg = "Missing data: please, select mouse name!"
    #    dlg = AlertMsg(widget, msg)
    #    dlg.exec()
    #    return False

    # if selected_exp_info == empty_dict:
    #    msg = "Missing data: please, fill the information about current session!"
    #    dlg = AlertMsg(widget, msg)
    #    dlg.exec()
    #    return False

    for k, v in args.items():
        if k != "transfer":
            for key, value in v.get_info().items():
                if value is None or value == "" or value == "-":
                    # alert
                    msg = v.get_labels(key)
                    if msg[-1] == ":":
                        msg = msg[:-1]
                    msg = "Missing data: " + msg
                    dlg = AlertMsg(widget, msg)
                    dlg.exec()
                    return False

    transfer_file = args["transfer"].get_transfer_files()
    if transfer_file == empty_dict:
        msg = "Missing data: please, select files for transfer!"
        dlg = AlertMsg(widget, msg)
        dlg.exec()
        return False

    keys_files = args["transfer"].get_keys()
    existed_keys = transfer_file.keys()
    for k in keys_files:
        if k not in existed_keys or transfer_file[k] is None:
            # allert attach key file
            msg = (
                "Missing data: please, select "
                + args["transfer"].get_labels(k)
                + " file for transfer!"
            )
            dlg = AlertMsg(widget, msg)
            dlg.exec()
            return False

    return True


def check_files(key, filename, format, current_mouse=None):
    """
    Checks if the specified file or files exist and have the correct file format.
    """
    if isinstance(filename, (list, tuple)):
        if not filename:
            return False
        return check_file_format(key, filename, format, current_mouse)

    return check_file_format(key, filename, format, current_mouse)


def _transfer_file(file_info, ip):
    """
    Transfers a file from source path to destination path using SCP.

    Args:
        file_info (dict): A dictionary containing information about the file.
            The dictionary must contain the following keys:
            - "src" (str): The source directory of the file.
            - "dst" (str): The destination directory of the file.
            - "filename" (str): The name of the file.
        ip (str): The IP address of the destination machine.

    Returns:
        tuple: A tuple containing a boolean indicating if the transfer was successful and the file path.
            The boolean is True if the transfer was successful, otherwise False.
            The file path is the source file path.
    """
    src = Path(file_info["src"]).joinpath(file_info["filename"])

    if src is not None and Path(src).exists():

        # src = str(src).replace("\\", "/")

        if "localhost" in ip:
            dst = str(Path(file_info["dst"]).joinpath(file_info["filename"]))
            if Path(src) != Path(dst):
                if Path(src).exists():
                    shutil.copy(Path(src), Path(dst))
        else:
            dst = ip + str(Path(file_info["dst"]).joinpath(file_info["filename"]))
            dst = str(dst).replace("\\", "/")
            cmd = ["scp", src, dst]

            logger.info(f"{cmd}")
            process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            exit_code = process.wait()
            if exit_code != 0:
                logger.warning(f"{cmd} : failed")
                return False, src

    return True, src


def transfer_files(transfer_files):
    """
    Transfers files using SCP from the source path to the destination path.

    Args:
        transfer_files (dict): A dictionary containing the information for each file to be transferred. The keys are
            arbitrary identifiers for the files, and the values are dictionaries containing the following keys:
            - "src" (str): The source path of the file.
            - "dst" (str): The destination path of the file.
            - "filename" (str): The name of the file.

    Returns:
        bool: True if all files were transferred successfully, False otherwise.

    Raises:
        Any exceptions that occur during file transfer.

    """
    ip = config.get_ip  # check connection - gui ? modify ? cache ? config ?
    host = config.get_host
    # check/create
    if ip != "localhost":
        adr = str(host) + "@" + str(ip) + ":"
    else:
        adr = ip + ":"
    ret = list()
    for key, value in transfer_files.items():
        # if isinstance(value["filename"], list) or \
        #        isinstance(value["filename"], tuple):
        #    for v in value:
        #        _transfer_file(v, dst)
        # else:
        ret.append(_transfer_file(value, adr))

    for val in ret:
        if val[0] is False:
            return False
    return True


def move_files(files_info):
    """
    Move submitted rig files into the configured processed folder.
    """
    dst = Path(config.get_processed_path)
    dst.mkdir(parents=True, exist_ok=True)

    for file_info in files_info:
        if not file_info:
            continue
        src = Path(file_info["src"]).joinpath(file_info["filename"])
        if not src.exists():
            logger.warning(f"Processed move skipped, missing file: {src}")
            continue
        target = dst / src.name
        if src.resolve() == target.resolve():
            continue
        shutil.move(str(src), str(target))


def init_watcher():  # launch dlc + wait/transfer once created (queue), init watcher on  folder
    pass


def get_filled_info(info, values):
    """
    Fills the given dictionary with information extracted from various PyQt5 GUI elements.

    Args:
    info (dict): The dictionary to be filled with information.
    values (dict): A dictionary that maps keys to PyQt5 GUI elements (e.g. QComboBox, QLineEdit).
    """
    for key, value in values.items():
        if isinstance(value, QComboBox):
            info[key] = str(value.currentText())
        elif isinstance(value, QLineEdit) or isinstance(value, QLabel):
            info[key] = str(value.text())
        elif isinstance(value, QPlainTextEdit):
            info[key] = value.toPlainText()


def adjust_keys(info, values, key2info, primary_keys):
    """
    Adjusts the keys of a dictionary info based on a mapping provided by key2info and primary_keys.

    Args:
    info (dict): A dictionary containing the information to be adjusted.
    values (dict): A dictionary with the current keys in info to be adjusted.
    key2info (dict): A dictionary mapping the keys in values to the desired keys in info.
    primary_keys (dict or None): A dictionary mapping primary keys to their corresponding secondary keys.

    Note:
    This function modifies the info dictionary in place.
    """

    for key in values.keys():
        if primary_keys is not None:
            if key in primary_keys.keys():
                display = info[key]
                if display not in key2info:
                    logger.warning(f"No lookup entry for dropdown value: {display}")
                    continue
                primary_value = key2info[display]
                primary_key = primary_keys[key]
                del info[key]
                info[primary_key] = primary_value


def read_npy(pat):
    """
    Reads and prints the contents of a npy file.

    Args:
    path (str, optional): The path of the npy file to read.
    """
    f = np.load(path, allow_pickle=True)
    print(f)


def get_options(choices, key, key2info, primary_keys):
    """
    Returns a list of options based on the given choices for a specific key.

    Args:
    choices (dict): A dictionary of choices for each key.
    key (str): The key to get options for.
    key2info (dict): A dictionary mapping keys to their values.
    primary_keys (dict): A dictionary of primary keys and their values.

    Returns:
    list: A list of options for the given key.
    """
    if isinstance(choices[key][0], dict):
        options = ["-"] + build_option_text(choices, key, key2info, primary_keys)
    else:
        options = ["-"] + choices[key]
    return options


def build_option_text(choices, key, key2info, primary_keys):
    """
    Returns a list of options based on the given choices for a specific key.
    Concatenates the lookup entries to get one option from different attributes.

    Args:
    choices (dict): A dictionary of choices for each key.
    key (str): The key to get options for.
    key2info (dict): A dictionary mapping keys to their values.
    primary_keys (dict): A dictionary of primary keys and their values.

    Returns:
    list: A list of options for the given key.
    """
    options = list()
    for line in choices[key]:
        concat = ""
        skip = False
        for elm in line.values():
            # if isinstance(elm, str) and \
            #        elm.lower() == "none":
            #    skip = True
            #    break
            concat += str(elm) + " - "
        if not skip:
            concat = concat[:-2]
            primary_key = primary_keys[key]
            key2info[concat] = line[primary_key]
            options.append(concat)
    return options
