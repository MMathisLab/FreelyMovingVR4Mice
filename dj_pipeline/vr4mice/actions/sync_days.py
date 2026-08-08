import os
from collections import defaultdict
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


def _days_from_exp_dates(
    sessions: List[List[str]], date_format: str = "%Y-%m-%d"
) -> dict[str, int]:
    """
    Assign experiment day numbers from calendar dates for one mouse.

    First session date is day 1; gaps between calendar dates add to the day index
    (e.g. Jan 1 → day 1, Jan 3 → day 3). Multiple attempts on the same date share
    the same day number.
    """
    days = {}
    sorted_sessions = sorted(
        sessions, key=lambda row: datetime.strptime(row[0], date_format)
    )
    idx = 1
    prev_date = ""

    for date, name, attempt in sorted_sessions:
        if date != prev_date:
            if prev_date:
                d1 = datetime.strptime(prev_date, date_format)
                d2 = datetime.strptime(date, date_format)
                idx += int((d2 - d1).days)
            prev_date = date
        days[f"{name}_{date}_{attempt}"] = idx

    return days


def sync_days(
    paths: Optional[Union[str, Sequence[str]]] = None,
    date_format: str = "%Y-%m-%d",
) -> None:
    """
    Synchronize experiment day values in GUI .npy files.

    Day is always relative to each mouse's experiment timeline:
    - If the mouse already has exp.Session rows, day = (doe − first session doe) + 1.
    - Otherwise day is inferred from session filenames on disk (earliest date = day 1),
      scanning all requested folders together so data/ and processed/ stay consistent.

    Args:
        paths: One folder, a list of folders, or None. When None, scans both
            /data/data and /data/processed together.
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
        if len(tmp) < 3:
            logger.warning("Skipping unparseable dataset stem %r", dataset)
            continue
        date = tmp[1]
        name = tmp[0]
        attempt = tmp[2]

        ret = mouse_in_db(name, date)
        if ret is None:
            raw_dir.append([date, name, attempt])
        else:
            logger.debug("Day for %s from DB: %d", dataset, ret)
            ret_arr[dataset] = ret

    by_mouse: dict[str, List[List[str]]] = defaultdict(list)
    for date, name, attempt in raw_dir:
        by_mouse[name].append([date, name, attempt])

    for name, sessions in by_mouse.items():
        ret_arr.update(_days_from_exp_dates(sessions, date_format=date_format))
        logger.debug(
            "Inferred days for %s from %d on-disk session(s).", name, len(sessions)
        )

    for folder, filename, dataset in file_entries:
        if dataset not in ret_arr:
            continue

        day = int(ret_arr[dataset])
        try:
            raw_data_npy, _ = get_new_file(filename, folder)
        except Exception as err:
            logger.warning(
                "Skipping day sync for %s in %s: cannot load (%s: %s)",
                dataset,
                folder,
                type(err).__name__,
                err,
            )
            continue

        if not isinstance(raw_data_npy, dict):
            logger.warning(
                "Skipping day sync for %s in %s: .npy root is %s, not a dict",
                dataset,
                folder,
                type(raw_data_npy).__name__,
            )
            continue

        old_day = raw_data_npy.get("day")
        try:
            old_day_int = int(old_day) if old_day is not None else None
        except (TypeError, ValueError):
            old_day_int = None

        if old_day_int == day:
            continue

        raw_data_npy["day"] = day
        out_path = Path(folder).joinpath(filename)
        try:
            np.save(str(out_path), raw_data_npy)
        except Exception as err:
            logger.warning(
                "Skipping day sync write for %s (%s): %s: %s",
                out_path,
                dataset,
                type(err).__name__,
                err,
            )
            continue
        logger.info(
            "Updated day for %s in %s: %s -> %s", dataset, folder, old_day, day
        )
