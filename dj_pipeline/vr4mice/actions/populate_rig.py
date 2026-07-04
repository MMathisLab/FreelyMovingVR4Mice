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


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")


def _schemas_for_dataset(raw_data_npy, *, populate_base: bool) -> list:
    """Return schema list for a dataset (base+vr4mice or vr4mice-only)."""
    if raw_data_npy is None or not populate_base:
        return [vr4mice]
    return [base, vr4mice]


def _data_rel_path(file_dir: str, srcf: str = "/data") -> str:
    """Path suffix for get_files_paths (local_src + data == file directory)."""
    file_dir = os.path.normpath(file_dir)
    srcf = os.path.normpath(srcf)
    if file_dir == srcf:
        return "/"
    if file_dir.startswith(srcf + os.sep):
        rel = file_dir[len(srcf) :]
        return rel if rel.startswith("/") else f"/{rel}"
    return file_dir if file_dir.startswith("/") else f"/{file_dir}"


def _prepare_gui_raw_data(dataset, raw_data_npy, *, srcf="/data", file_dir: str):
    """Merge GUI .npy metadata with simulated filepath info for base schema populate."""
    raw_data_npy = dict(raw_data_npy)
    raw_data_npy.setdefault("rig_id", 12)
    raw_data_npy.setdefault("license", "N/A")
    files_info = get_files_paths(
        dataset=dataset,
        remote_src=None,
        local_src=srcf,
        data=_data_rel_path(file_dir, srcf),
    )
    return {**files_info, **raw_data_npy}


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


def build_row(
    table_name,
    attributes,
    raw_data,
    schema,
    srcf="/data",
    dstf="processed",
    move=False,
):
    """Build the row dict that populate would insert for a table."""
    data = dict()

    for a in attributes:
        if a in schema["local_def"].keys():
            data[a] = schema["local_def"][a](
                raw_data=raw_data,
                key=a,
                transformer=schema["transformer"],
                srcf=srcf,
                dstf=dstf,
                move=move,
            )
        else:
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
                        logger.debug("Note: %s variable name changed to %s", label, a)

    return data


def row_exists(schema, table_name, data) -> bool:
    """Return True if the table already contains the row primary key."""
    if not data:
        return False

    table = schema["dj_tables"][table_name]
    key = {field: data[field] for field in table.primary_key if field in data}
    if len(key) != len(table.primary_key):
        return False
    return len(table & key) > 0


def collect_population_targets(
    raw_data,
    schemas,
    *,
    srcf="/data",
    dstf="processed",
):
    """Return populate targets in dependency order with their expected row keys."""
    working_data = dict(raw_data)
    targets = []

    for schema in schemas:
        for table_name, attributes in schema["tables"].items():
            flag, none_vals = check_keys(
                attributes, working_data, table_name, schema=schema
            )
            if not flag:
                continue
            if none_vals:
                working_data = {**working_data, **none_vals}
            row = build_row(
                table_name,
                attributes,
                working_data,
                schema,
                srcf=srcf,
                dstf=dstf,
                move=False,
            )
            targets.append(
                {
                    "schema": schema,
                    "table_name": table_name,
                    "attributes": attributes,
                    "row": row,
                }
            )

    return targets


def is_dataset_fully_populated(targets) -> bool:
    """True when every planned populate target already exists in the database."""
    if not targets:
        return False
    return all(
        row_exists(target["schema"], target["table_name"], target["row"])
        for target in targets
    )


def populate_dataset_tables(
    dataset,
    raw_data,
    schemas,
    *,
    srcf="/data",
    dstf="processed",
) -> bool:
    """
    Populate all missing tables for a dataset without moving raw files.

    Returns True only when every target table row exists after populate.
    """
    targets = collect_population_targets(
        raw_data, schemas, srcf=srcf, dstf=dstf
    )
    if not targets:
        logger.warning("No population targets resolved for dataset %s.", dataset)
        return False

    from vr4mice.actions.keys2tables_base import base as base_schema

    if base_schema in schemas:
        from vr4mice.actions.mouse_sync import ensure_mouse_for_session

        ensure_mouse_for_session(raw_data, dataset=dataset, log=logger)

    if is_dataset_fully_populated(targets):
        logger.debug(
            "Dataset %s already fully populated (%d tables).",
            dataset,
            len(targets),
        )
        return True

    working_data = dict(raw_data)
    for schema in schemas:
        for table_name, attributes in schema["tables"].items():
            flag, none_vals = check_keys(
                attributes, working_data, table_name, schema=schema
            )
            if not flag:
                continue
            if none_vals:
                working_data = {**working_data, **none_vals}

            row = build_row(
                table_name,
                attributes,
                working_data,
                schema,
                srcf=srcf,
                dstf=dstf,
                move=False,
            )
            if row_exists(schema, table_name, row):
                continue

            logger.info("Populating: %s", table_name)
            schema["dj_tables"][table_name].insert1(
                row, skip_duplicates=SKIP_DUPLICATES
            )
            logger.info("[POPULATED OK] %s", table_name)

    complete = is_dataset_fully_populated(
        collect_population_targets(raw_data, schemas, srcf=srcf, dstf=dstf)
    )
    if not complete:
        logger.warning(
            "Dataset %s population incomplete; raw files were not moved.",
            dataset,
        )
    return complete


def sync_dataset_paths_after_move(
    dataset: str, srcf: str = "/data", dstf: str = "processed"
) -> None:
    """Point Dataset filepath columns at the processed folder after a move."""
    processed_dir = os.path.join(srcf, dstf)
    key = {"dataset": dataset}
    table = dj_schema.vr4mice.Dataset()
    if not (table & key):
        return

    row = (table & key).fetch1()
    updates = {}
    for field in ("exp_teensy_filepath", "exp_session_filepath"):
        current = row.get(field)
        if not current:
            continue
        filename = os.path.basename(str(current))
        new_path = os.path.join(processed_dir, filename)
        if os.path.exists(new_path) and str(current) != new_path:
            updates[field] = new_path

    if updates:
        table.update1({**key, **updates})
        logger.debug("Updated Dataset file paths after move for %s", dataset)


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
    data = build_row(
        table_name,
        attributes,
        raw_data,
        schema,
        srcf=srcf,
        dstf=dstf,
        move=move,
    )

    logger.info(f"Populating: {table_name}")

    schema["dj_tables"][table_name].insert1(data, skip_duplicates=SKIP_DUPLICATES)
    logger.info(f"[POPULATED OK] {table_name}")


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


def _dstf_for_folder(folder_path: str, srcf: str = "/data") -> str:
    """Folder name relative to srcf for filepath metadata (e.g. data, processed)."""
    rel = _data_rel_path(folder_path, srcf).lstrip("/")
    return rel or "processed"


def populate_base_from_gui_folder(
    folder_path: str,
    *,
    srcf: str = "/data",
    sync_days_first: bool = False,
) -> tuple[int, int]:
    """
    Populate base/exp schema (stub Mouse rows only) from GUI .npy files in a folder.

    Day sync is off by default here; call sync_days() once over all GUI folders
    (data + processed) before batch populate so numbering stays consistent.

    Returns (completed_count, failed_count).
    """
    folder_path = os.path.normpath(folder_path)
    if not os.path.isdir(folder_path):
        logger.debug("GUI folder %s does not exist; skipping.", folder_path)
        return (0, 0)

    if sync_days_first:
        from vr4mice.actions.sync_days import sync_days

        sync_days()

    dir_list = get_filenames([".npy"], folder_path)
    if ".npy" not in dir_list:
        logger.info("No GUI .npy files in %s", folder_path)
        return (0, 0)

    dstf = _dstf_for_folder(folder_path, srcf)
    ok, failed = 0, 0

    for npy_file in dir_list[".npy"]:
        try:
            raw_data_npy, dataset = get_new_file(npy_file, folder_path)
            raw_data = _prepare_gui_raw_data(
                dataset, raw_data_npy, srcf=srcf, file_dir=folder_path
            )
            complete = populate_dataset_tables(
                dataset,
                raw_data,
                [base],
                srcf=srcf,
                dstf=dstf,
            )
            if complete:
                ok += 1
                logger.info("Base populate complete for %s", dataset)
            else:
                failed += 1
                logger.warning(
                    "Base populate incomplete for %s (will retry on next run).", dataset
                )
        except Exception as e:
            failed += 1
            logger.warning(
                "Base populate failed for %s in %s: %s", npy_file, folder_path, e
            )

    return (ok, failed)


def populate_processed_gui(
    *,
    srcf: str = "/data",
    dstf: str = "processed",
    populate_base: bool = True,
) -> None:
    """
    Backfill base (exp/mice) schema from all GUI .npy files in the processed folder.

    Corrects experiment day in each .npy via sync_days before population.
    """
    if not populate_base:
        return

    processed_path = os.path.join(srcf, dstf)
    if not os.path.isdir(processed_path):
        logger.debug(
            "Processed folder %s does not exist; skipping GUI backfill.", processed_path
        )
        return

    from vr4mice.actions.sync_days import sync_days

    logger.info(
        "Syncing experiment days in GUI files (data + processed) before backfill."
    )
    sync_days()

    dir_list = get_filenames([".npy"], processed_path)
    if ".npy" not in dir_list:
        logger.info("No GUI .npy files in %s", processed_path)
        return

    logger.info(
        "Backfilling base schema from %d GUI file(s) in %s",
        len(dir_list[".npy"]),
        processed_path,
    )

    for npy_file in dir_list[".npy"]:
        try:
            raw_data_npy, dataset = get_new_file(npy_file, processed_path)
            pickle_path = Path(processed_path) / f"{dataset}.pickle"
            raw_data_pickle = None
            if pickle_path.is_file():
                raw_data_pickle, _ = get_new_file(pickle_path.name, processed_path)

            if raw_data_pickle:
                raw_data = {
                    **_prepare_gui_raw_data(
                        dataset, raw_data_npy, srcf=srcf, file_dir=processed_path
                    ),
                    **raw_data_pickle,
                    **raw_data_npy,
                }
                schemas = _schemas_for_dataset(raw_data_npy, populate_base=True)
            else:
                raw_data = _prepare_gui_raw_data(
                    dataset, raw_data_npy, srcf=srcf, file_dir=processed_path
                )
                schemas = [base]

            complete = populate_dataset_tables(
                dataset,
                raw_data,
                schemas,
                srcf=srcf,
                dstf=dstf,
            )
            if complete:
                logger.info("Processed GUI backfill complete for %s", dataset)
            else:
                logger.warning(
                    "Processed GUI backfill incomplete for %s (will retry on next run).",
                    dataset,
                )
        except Exception as e:
            logger.warning("Processed GUI backfill failed for %s: %s", npy_file, e)


def move_dataset_files(
    dataset_name: str,
    base_path: str,
    dst_folder: str,
    srcf: str = "/data",
) -> None:
    """Move pickle/npy session files to processed only after population succeeds."""
    # Match get_path(): session files under .../data/ move to srcf/dst_folder.
    dst_path = os.path.join(srcf, dst_folder)
    os.makedirs(dst_path, exist_ok=True)
    moved = False
    for suffix in [".pickle", ".npy"]:
        filename = f"{dataset_name}{suffix}"
        src = os.path.join(base_path, filename)
        if os.path.exists(src):
            shutil.move(src, os.path.join(dst_path, filename))
            moved = True
    if moved:
        logger.info(f"Moved raw files for {dataset_name} to {dst_path}")
        sync_dataset_paths_after_move(dataset_name, srcf=srcf, dstf=dst_folder)
    else:
        logger.debug(f"No raw files found to move for {dataset_name}")


def populate_rig(
    path="/data/data",
    srcf="/data",
    dstf="processed",
    move=True,
    populate_base=None,
) -> None:
    """
    Populates database tables with data from files in the specified directory.

    Args:
        path (str): The path to the directory containing data files.
        populate_base (bool | None): Populate exp/mice base schema from .npy metadata.
            Defaults to True, or the POPULATE_BASE environment variable when None.
    Raises:
        OSError: If the specified directory does not exist.

    The function looks for data files with extensions ".npy" and ".pickle" in the
    specified directory, and assumes that files with the same name (excluding
    extension) correspond to the same dataset.

    For each ".pickle" file found, the function loads its data into a dictionary.
    It then looks for the corresponding ".npy" file and loads its data into the
    same dictionary. If no corresponding ".npy" file is found, the function logs
    an error message and returns.

    The function then populates every applicable table for the dataset. Population
    and file moves are atomic: raw pickle/npy files are moved to the processed
    folder only after every target table row exists in the database. Partial
    population (e.g. Dataset without State) is retried on the next run.

    dataset = name of file : mouse_name_doe_attempt
    """
    if populate_base is None:
        populate_base = _env_bool("POPULATE_BASE", default=True)

    gui = os.environ.get("GUI", "false").lower() in ["true", "1", "yes"]

    if not populate_base:
        logger.info(
            "Base schema (exp/mice) population disabled; only vr4mice tables will be populated."
        )

    if gui:
        ext = [".npy", ".pickle"]
    else:
        ext = [".pickle"]

    dir_list = get_filenames(ext, path)

    if ".pickle" in dir_list.keys():

        for pickle_file in dir_list[".pickle"]:
            try:
                logger.info(f"Processing file: {pickle_file}")
                raw_data_pickle, dataset = get_new_file(pickle_file, path)

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
                        local_src=srcf,
                        data=_data_rel_path(path, srcf),
                    )
                    raw_data = {**files_info, **raw_data_pickle}
                    schemas = _schemas_for_dataset(None, populate_base=populate_base)
                else:
                    raw_data = {**raw_data_pickle, **raw_data_npy}
                    schemas = _schemas_for_dataset(
                        raw_data_npy, populate_base=populate_base
                    )

                complete = populate_dataset_tables(
                    dataset,
                    raw_data,
                    schemas,
                    srcf=srcf,
                    dstf=dstf,
                )
                if complete and move:
                    move_dataset_files(dataset, path, dstf, srcf=srcf)

            except Exception as e:
                logger.warning(f"Population of raw data failed for {pickle_file}: {e}")

    elif ".npy" in dir_list.keys():  # case no pickle
        if not populate_base:
            logger.info("Skipping .npy-only files (base schema population disabled).")
            return
        for npy_file in dir_list[".npy"]:
            try:
                raw_data_npy, dataset = get_new_file(npy_file, path)
                raw_data = _prepare_gui_raw_data(
                    dataset, raw_data_npy, srcf=srcf, file_dir=path
                )
                schemas = [base]

                complete = populate_dataset_tables(
                    dataset,
                    raw_data,
                    schemas,
                    srcf=srcf,
                    dstf=dstf,
                )
                if complete and move:
                    move_dataset_files(dataset, path, dstf, srcf=srcf)
            except Exception as e:
                logger.warning(f"Population of raw data failed for {npy_file}: {e}")

    if populate_base:
        populate_processed_gui(srcf=srcf, dstf=dstf, populate_base=populate_base)
