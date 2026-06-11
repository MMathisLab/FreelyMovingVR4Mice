from datetime import datetime
from pathlib import Path

import numpy as np

from vr4mice.actions.populate_rig import get_filenames, get_new_file

"""
    Script that helps to synchronise the days of experiments if there is a mismatch.
"""


def mouse_in_db(name, date, date_format="%Y-%m-%d"):
    """
    A function that checks if a mouse is in the database,
    and returns the number of days since the mouse's is involved in experiment.
    If there is no information about experiments session returns None.

    Args:
    name (str): The name of the mouse.
    date (str): Th known date of experiments (from dataset to test)
    date_format (str): The format of the date string, defaults to "%Y-%m-%d".

    Returns:
    int: The number of days since the mouse's starting experiments, None if first time.
    """
    from base_schemas.schemas import mice

    mouse = mice.Mouse() & 'mouse_name = "%s"' % name

    start_date = mouse.get_starting_date()
    if start_date is None:
        return None

    date = datetime.strptime(date, date_format).date()
    return (date - start_date).days + 1


def sync_days(path, date_format="%Y-%m-%d"):
    """
    Synchronize the info about current experiment day for every mouse dataset
    Sorts dates, and updates day values in the .npy files according to calculated order.

    Args:
    path (str): A string representing the path of the directory containing datasets files
    date_format (str, optional): A string representing the date format used in the data files' names.
    Defaults to "%Y-%m-%d".
    """
    ext = [".npy"]

    dir_list = get_filenames(ext, path)

    dir_list = dir_list[".npy"]

    ret_arr = dict()
    raw_dir = list()

    for filename in dir_list:
        filename = filename.split(".")[0]
        tmp = filename.split("_")
        date = tmp[1]
        name = tmp[0]
        attempt = tmp[2]

        ret = mouse_in_db(name, date)  # check if mice in the database
        if ret == None:
            raw_dir.append([date, name, attempt])
        else:
            print(ret)
            ret_arr[filename] = ret

    sorted_dir = sorted(raw_dir, key=lambda day: datetime.strptime(day[0], date_format))

    idx = 1
    prec = ""

    for elm in sorted_dir:

        if elm[0] != prec:
            if prec != "":
                # check difference in days:
                d1 = datetime.strptime(prec, date_format)
                d2 = datetime.strptime(elm[0], date_format)
                delta = d2 - d1
                idx += int(delta.days)
            prec = elm[0]

        ret_arr[elm[1] + "_" + elm[0] + "_" + elm[2]] = idx

    for f in dir_list:
        raw_data_npy, dataset = get_new_file(f, path)

        if dataset in ret_arr.keys():
            idx = ret_arr[dataset]
            if raw_data_npy["day"] != idx:
                raw_data_npy["day"] = idx
                np.save(str(Path(path).joinpath(f)), raw_data_npy)
