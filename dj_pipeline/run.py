import sys

from vr4mice.utils.logger import Logger, config_logger
from base_actions.connect import connect

"""
    The main script that is entry point for all interactions with database:

    Different command modes:
        "connect": to simple connect to the database, should be followed by the user name
            todo: add restrictions
        "set_mouse": for debugging to add a new random mouse for test
        "populate": to populate the data from files
        "fetch": to create .npy file for dropdown menu
        
    todo: paths in environmental variables 
    todo: getops
    
    "tag" to precise a version of schema to access: empty: main version
"""
logger = Logger.get_logger()

if __name__ == "__main__":
    config_logger(level="INFO", debug=False)

    mode = sys.argv[1]

    connect(tag="")  # to check: last from Oct: v1_

    if mode == "set_mouse":
        from test.generators.fake_mice import insert_fake_mouse

        insert_fake_mouse(name="Barracuda")

    elif mode == "populate":
        from vr4mice.actions.populate_rig import populate_rig

        populate_rig(path="/data/data")

    elif mode == "fetch":
        from vr4mice.actions.fetch_data import fetch_data

        fetch_data(dst="/shared/gui_menu.npy")

    elif mode == "connect":
        from vr4mice.schema import vr4mice

        pass

    elif mode == "update":  # sync with main: missing data in existed tables
        pass

    elif mode == "sync_days":
        from vr4mice.actions.sync_days import sync_days

        sync_days(path="/data/data")
