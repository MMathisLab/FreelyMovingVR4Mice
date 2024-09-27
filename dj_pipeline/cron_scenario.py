import os

from base_actions.connect import connect

connect(tag="", db_host=os.environ["DJ_HOST"])


from vr4mice.actions.populate_rig import populate_rig
from vr4mice.actions.fetch_data import fetch_data
from vr4mice.utils.logger import Logger
from run import check_folder_existence, create_folder_if_not_exist


logger = Logger.get_logger()

# note: paths and args are set here to default (same as in the source file),
# here to show up the specs


try:
    path = "/data/data"
    check_folder_existence(path)
    populate_rig(path)
except Exception as e:
    logger.error(f"An error occurred in populate_and_move: {e}")

try:
    from vr4mice.schema import base_analysis, dlc

    create_folder_if_not_exist("/data/summary_plots")
    base_analysis.DataFrame.populate()
    base_analysis.BoxDataFrame()
    base_analysis.JShaped().populate()
    base_analysis.GitCommit().populate()

    # base_analysis.OutputPlots.populate()
    dlc.DLCProcessor().populate()
    dlc.DLCKptsDf().populate()
    #dlc.SyncDLCWGame().populate()
    #dlc.DLCKptsBodyparts().populate()  # TODO: optional

except Exception as e:
    logger.error(f"An error occurred in populate_decision_making.populate: {e}")

try:
    path = "/shared"
    # check_folder_existence(path)
    # fetch_data(dst="/shared/gui_menu.npy")
except Exception as e:
    logger.error(f"An error occurred in fetch_data: {e}")
