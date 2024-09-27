import os
import sys

from base_actions.connect import connect
from vr4mice.utils.logger import Logger, config_logger

logger = Logger.get_logger()

"""
    Pool of commands

    Modes:
        "connect": connect to the database
        "populate": to populate the data from files
        "fetch": to create .npy file for dropdown menu
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
    config_logger(level="INFO", debug=False)

    mode = sys.argv[1]  # TODO: connect arg deprecate

    connect(tag="")

    # if mode == "set_mouse":
    #    from test.generators.fake_mice import insert_fake_mouse
    #
    #    insert_fake_mouse(name="Barracuda")

    if mode == "connect":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        pass

    elif mode == "populate":  # TODO: gemeral populate and split in func
        from vr4mice.actions.populate_rig import populate_rig

        path = "/data/data"
        check_folder_existence(path)
        populate_rig(path)

    elif mode == "analysis":
        from vr4mice.schema import base_analysis, federated_db

        # NOTE: populate has to be run before

        create_folder_if_not_exist("/data/summary_plots")
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame().populate()
        base_analysis.JShaped().populate()
        base_analysis.GitCommit().populate()

        # base_analysis.OutputPlots.populate()

    elif mode == "dlc":
        # NOTE: populate and analysis have to be run before
        from vr4mice.schema import dlc

        create_folder_if_not_exist("/data/summary_plots")
        dlc.DLCProcessor().populate()
        dlc.DLCKptsDf().populate()
        #dlc.SyncDLCWGame().populate()
        # dlc.DLCKptsBodyparts().populate() #TODO: optional

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
