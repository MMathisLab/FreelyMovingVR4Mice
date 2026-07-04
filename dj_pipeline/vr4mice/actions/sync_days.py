import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

import numpy as np

from vr4mice.actions.populate_rig import get_filenames, get_new_file
from vr4mice.utils.logger import Logger

"""
    Script that helps to synchronise the days of experiments if there is a mismatch.
"""
logger = Logger.get_logger()

DEFAULT_GUI_PATHS = ("/data/data", "/data/processed")


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

    mouse = mice.Mouse() & {"mouse_name": name}

    start_date = mouse.get_starting_date()
    if start_date is None:
        return None

    date = datetime.strptime(date, date_format).date()
    return (date - start_date).days + 1


def _normalize_paths(
    paths: Optional[Union[str, Sequence[str]]],
) -> List[str]:
    if paths is None:
        candidates = list(DEFAULT_GUI_PATHS)
    elif isinstance(paths, str):
        candidates = [paths]
    else:
        candidates = list(paths)

    existing = [os.path.normpath(path) for path in candidates if os.path.isdir(path)]
    return existing


def _collect_gui_npy_files(paths: Iterable[str]) -> List[tuple[str, str, str]]:
    """Return (folder, filename, dataset_stem) for every GUI .npy under paths."""
    entries: List[tuple[str, str, str]] = []
    for path in paths:
        dir_list = get_filenames([".npy"], path)
        if ".npy" not in dir_list:
            continue
        for filename in dir_list[".npy"]:
            entries.append((path, filename, filename.split(".")[0]))
    return entries


def sync_days(
    paths: Optional[Union[str, Sequence[str]]] = None,
    date_format: str = "%Y-%m-%d",
) -> None:
    """
    Synchronize experiment day values in GUI .npy files.

    Args:
        paths: One folder, a list of folders, or None. When None, scans both
            /data/data and /data/processed together so day numbering stays
            consistent across incoming and archived sessions.
        date_format: Date format used in dataset filenames.
    """
    paths = _normalize_paths(paths)
    if not paths:
        logger.debug("No GUI folders found for day sync (%s).", DEFAULT_GUI_PATHS)
        return

    file_entries = _collect_gui_npy_files(paths)
    if not file_entries:
        logger.info("No .npy files to sync in %s", paths)
        return

    logger.info(
        "Syncing experiment days across %d GUI file(s) in %s",
        len(file_entries),
        ", ".join(paths),
    )

    ret_arr = {}
    raw_dir = []
    seen_datasets = set()

    for _path, _filename, dataset in file_entries:
        if dataset in seen_datasets:
            continue
        seen_datasets.add(dataset)

        tmp = dataset.split("_")
        date = tmp[1]
        name = tmp[0]
        attempt = tmp[2]

        ret = mouse_in_db(name, date)
        if ret is None:
            raw_dir.append([date, name, attempt])
        else:
            logger.debug("Day for %s from DB: %d", dataset, ret)
            ret_arr[dataset] = ret

    sorted_dir = sorted(raw_dir, key=lambda day: datetime.strptime(day[0], date_format))

    idx = 1
    prec = ""

    for elm in sorted_dir:
        if elm[0] != prec:
            if prec != "":
                d1 = datetime.strptime(prec, date_format)
                d2 = datetime.strptime(elm[0], date_format)
                delta = d2 - d1
                idx += int(delta.days)
            prec = elm[0]

        ret_arr[elm[1] + "_" + elm[0] + "_" + elm[2]] = idx

    for folder, filename, dataset in file_entries:
        if dataset not in ret_arr:
            continue

        day = ret_arr[dataset]
        raw_data_npy, _ = get_new_file(filename, folder)
        if raw_data_npy["day"] != day:
            old_day = raw_data_npy["day"]
            raw_data_npy["day"] = day
            np.save(str(Path(folder).joinpath(filename)), raw_data_npy)
            logger.info(
                "Updated day for %s in %s: %s -> %s", dataset, folder, old_day, day
            )
