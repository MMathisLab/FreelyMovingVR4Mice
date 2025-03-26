import logging
import os
import argparse

import sys
import warnings

from base_actions.connect import connect
from vr4mice.utils.logger import Logger, config_logger

logger = Logger.get_logger()


logging.getLogger("settings").setLevel(logging.ERROR)

warnings.simplefilter(action="ignore", category=FutureWarning)


"""
    Pool of commands

    Modes:
    "connect": connect to the database
    "populate": populate the raw data from files
    "fetch": create .npy file for dropdown menu
    "analysis": perform data analysis: populate base_analysis
    "summary": generate summary plots: populate summary plots
    "dlc": process DeepLabCut data: populate dlc tables
    "update": sync missing data in existing tables
    "sync_days": synchronize days in the dataset (process raw .npy files)
"""


def create_folder_if_not_exist(folder_path):
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            logger.info(f"Folder '{folder_path}' created successfully.")
        except OSError as e:
            logger.warning(f"Error: {e}")
            exit(1)
    else:
        logger.info(f"Folder '{folder_path}' already exists.")


def check_folder_existence(folder_path):
    if not os.path.exists(folder_path):
        logger.warning(f"Folder '{folder_path}' does not exist. Exiting.")
        sys.exit(1)
    else:
        logger.info(f"Folder '{folder_path}' exists.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
    )
    args = parser.parse_args()

    config_logger(level="INFO", debug=False)

    mode = sys.argv[1]

    connect(tag="")

    if mode == "connect":
        from vr4mice.schema import vr4mice, base_analysis, dlc, base

        pass

    elif mode == "populate":
        from vr4mice.actions.populate_rig import populate_rig
        from vr4mice.schema import vr4mice

        if args.aws:
            path = "/data/processed"
            move = False
        else:
            path = "/data/data"
            move = True

        check_folder_existence(path)
        populate_rig(path=path, move=move)
        vr4mice.Collab().populate()

    elif mode == "analysis":
        from vr4mice.schema import base_analysis, base

        # NOTE: populate has to be run before

        create_folder_if_not_exist("/data/summary_plots")
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame().populate()
        base_analysis.GitCommit().populate()

    elif mode == "summary":
        from vr4mice.schema import base_analysis

        base_analysis.SummaryPlots().populate()
        base_analysis.TrackingSummaryPlots().populate()

    elif mode == "dlc":
        # NOTE: populate and analysis have to be run before
        from vr4mice.schema import dlc

        create_folder_if_not_exist("/data/summary_plots")
        dlc.DLCProcessor().populate()
        dlc.DLCKptsDf().populate()
        dlc.SyncDLCKptsDf().populate()
        dlc.OfflineKinematics().populate()

    elif mode == "fetch":  # TODO: adjust path
        from vr4mice.actions.fetch_data import fetch_data

        path = "/shared"
        check_folder_existence(path)

        fetch_data(dst="/shared/gui_menu.npy")

    elif mode == "update":  # sync with main: missing data in existed tables
        pass

    elif mode == "sync_days":
        from vr4mice.actions.sync_days import sync_days

        sync_days(path="/data/data")
