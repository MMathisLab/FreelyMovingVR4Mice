#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

from base_schemas.schemas import mice

from vr4mice.utils.logger import Logger

"""
    Ensemble of functions referenced in the "local definition" dictionary 
    for local definition of database attributes 
"""

logger = Logger.get_logger()


def get_session_incr(raw_data=None, **kwargs):
    """
    Returns the session increment for a given mouse.

    Args:
        raw_data (dict): A dictionary of raw data containing information about the mouse.
        **kwargs: Additional keyword arguments.

    Returns:
        int or None: The session increment for the mouse, or None if raw_data is None.

    Note:
        get_session_increment function is proper to the Mouse datajoint class for table definition
    """

    if raw_data is not None:
        mouse = mice.Mouse() & 'mouse_name = "%s"' % raw_data["mouse_name"]
        return mouse.get_session_increment()
    return None


def no_value(**kwargs):
    """
    Used for "None" attributes
    """
    return "none"


def get_camera_idx(**kwargs):
    """
    Default: 1
    """
    return 1


def default(**kwargs):
    """
    Used for -1 attributes
    """
    return -1


def no_value_opto(**kwargs):
    """
    Used for no optogenetics case
    """
    return ["none", -1, -1, -1, "none", "none", "none"]


def no_joystick(**kwargs):
    """
    Used for no joystick case
    """
    return "none"


def no_force_field(**kwargs):
    """
    Used for forcefield case
    """
    return "none"


def get_state(raw_data=None, key=None, **kwargs):
    """
    A function used for the "state" array that doesn't have keys associated to every entry;
    It that takes in raw_data and a key and returns the values of the specified key from the raw_data.

    Args:
    raw_data (dict): A dictionary containing the raw data.
    key (str): The key to get values from.

    Returns:
    list: A list containing the values of the specified key.
    """

    if raw_data is None or key is None:
        return None

    keys = {
        "x_pos": 0,
        "z_pos": 1,
        "head_dir": 2,
        "mouse_can_report": 3,
        "iti": 4,
        "obj_left": 5,
        "mouse_report_correct": 6,
        "report_left": 7,
        "report_right": 8,
        "velocity": 9,
        # "frame_flip": 10
    }

    if key not in keys:
        return None

    data = list()
    idx = keys[key]

    for s in raw_data["state"]:
        if idx < len(s):
            data.append(s[idx])
        else:
            data.append(None)
    return data


def get_path(
    raw_data=None,
    key=None,
    transformer=None,
    srcf="/data",
    dstf="processed",
    move=True,
    **kwargs,
):
    """
    A function that gets the path from the raw_data file, verifies that the file exists,
    and moves it in the processed folder.
    Use case: for the "data" folder files to be processed

    Args:
    raw_data (dict): A dictionary containing the raw data.
    key (str): The key to get the file path for.
    transformer (dict): A dictionary mapping the specified key to its corresponding raw key.

    Returns:
    str: The file path for the specified key or False if problem

    Todo: support of multiple paths
    """
    flag = False

    # exp session key doesn't exist in npy file, so adjusted here as has the same destination
    if key == "exp_session_filepath":
        key = "exp_teensy_filepath"
        flag = True

    raw_key = transformer[key]  # note: assuming that for all paths needed - ??
    file_info = raw_data[raw_key]
    filename = file_info["filename"]

    if flag:  # todo properly
        filename = Path(filename).stem
        filename = str(filename) + ".npy"

    # windows paths conventions
    src = file_info["dst"].replace("\\", "/")
    src = src.replace("//", "/")
    src = Path(src).name
    path = Path(src).joinpath(filename)
    path = Path(srcf).joinpath(path)

    if path.exists():
        parent = path.parent

        if parent.name == "data":
            processed = Path(parent.parent).joinpath(dstf)
            if not os.path.exists(processed):
                os.makedirs(processed)
            processed = processed.joinpath(filename)
            if move:
                shutil.move(path, processed)
                logger.info("Moving: " + str(path) + " --> " + str(processed))
                path = str(processed)
        return path
    else:
        logger.warning("Path doesn not exist: " + str(path))
        return False  # todo err


def get_remote_path(raw_data=None, key=None, transformer=None, **kwargs):
    raw_key = transformer[key]
    file_info = raw_data[raw_key]  # todo multiple paths... ? for dlc
    filename = file_info["filename"]
    src = file_info["src"]
    if src:
        path = Path(src).joinpath(filename)
        return str(path)
    return None


def get_model_name(raw_data=None, key=None, transformer=None, **kwargs):
    """
    Extracts the model name from the dlc file name
    todo: if multiple paths/make user select model
    """
    file_info = raw_data["dlc_path"]
    filename = file_info["filename"]
    arr = str(Path(filename).stem).split("_")
    name = arr[-1]
    return name


def get_camera(raw_data=None, key=None, transformer=None, **kwargs):
    """
    Extracts the camera name from the dlc file name
    todo: if multiple paths/make user select camera name
    """
    file_info = raw_data["dlc_path"]
    filename = file_info["filename"]
    arr = str(Path(filename).stem).split("_")
    name = arr[0]
    return name


def get_video_meta(raw_data=None, key=None, **kwargs):
    """
    Extracts video's metadata
    """
    return raw_data["video_meta"][key]


def get_box(raw_data=None, key=None, transformer=None, **kwargs):

    l_report_box = {
        "l_box_x_min": 0,
        "l_box_x_max": 1,
        "l_box_z_min": 2,
        "l_box_z_max": 3,
    }

    r_report_box = {
        "r_box_x_min": 0,
        "r_box_x_max": 1,
        "r_box_z_min": 2,
        "r_box_z_max": 3,
    }
    start_box = {
        "tt_box_x_min": 0,
        "tt_box_x_max": 1,
        "tt_box_z_min": 2,
        "tt_box_z_max": 3,
        "tt_box_angle": 4,
    }

    box = {
        "l_report_box": l_report_box,
        "r_report_box": r_report_box,
        "start_box": start_box,
    }

    # cover old style
    if transformer[key] in raw_data.keys():
        raw_key = transformer[key]
        data = raw_data[raw_key]
        logger.info(f"Old/ Key: {key} Raw key: {raw_key}, data: {data}")
        return data

    # new style
    for n, b in box.items():
        if key in b.keys():
            idx = b[key]
            name = n
            data = raw_data[name][idx]
            logger.info(f"New/ Key: {key}, idx: {idx}, name: {name}, data: {data}")
            return data


def get_name(raw_data=None, key=None, **kwargs):
    val = raw_data[key]
    logger.info(f"Session label: {key}: {val}")
    if isinstance(val, list):
        return val[0]
    return None
