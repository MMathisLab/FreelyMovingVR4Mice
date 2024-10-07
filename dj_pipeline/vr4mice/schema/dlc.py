from typing import List

import datajoint as dj
import numpy as np
import pandas as pd
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema  # todo adjust paths (base/utils)
from vr4mice.analysis.dlc_helpers import (
    h52dj,
    df2dj,
    dj2h5,
    sync_dlc_w_game,
    sync_keypoint_table,
    getall_dlc_heading_angles,
)

from vr4mice.schema import vr4mice, base_analysis

schema_name = "dlc"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class DLCProcessor(dj.Imported):

    definition = """
    -> vr4mice.DLC
    ---
    start_time: longblob
    frame_time: longblob
    time_stamp: longblob
    step: longblob
    signal: longblob
    photodiode_read: longblob
    photodiode_time: longblob
    x_pos: longblob
    y_pos: longblob
    heading_direction: longblob
    head_angle: longblob
    """

    def make(self, key):
        try:
            fpath = (vr4mice.DLC & key).fetch1("proc_filepath")
            data = np.load(fpath, allow_pickle=True)
            data = {**key, **data}
            self.insert1(data)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class DLCKptsDf(dj.Imported):
    definition = """
    -> vr4mice.DLC
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            h5path = (vr4mice.DLC & key).fetch1("keypoints_filepath")
            data = h52dj(h5path)
            data = {**key, **data}
            self.insert1(data)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_data(self, key):
        try:
            data = (self & key).fetch1()
            return dj2h5(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(self):
        dfs = []
        try:
            data = self.fetch()
            for d in data:
                df = dj2h5(d["data"], d["headers"], d["scorer"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class SyncDLCKptsDf(dj.Imported):
    definition = """
    -> DLCKptsDf
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):
        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            # I believe the key returned here is just the actual data set name aka mouseName_date_attempt so i need to add in the "dataset" key for this function?
            sync_kpts = sync_keypoint_table(
                d={"dataset": key}, keypoint_cuttoff=0.6, filter_window_length=10
            )
            data = df2dj(sync_kpts)
            data = {**key, **data}
            self.insert1(data)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_data(self, key):
        # TODO Mary_app -is there a way here that we can speficy which headers to return?
        # i think this would solve many of both your and mine worries about fetch speed
        try:
            data = (self & key).fetch1()
            return pd.DataFrame(data["data"], columns=data["headers"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(self, key):
        dfs = []
        try:
            data = self.fetch()
            for d in data:
                df = pd.DataFrame(d["data"], columns=d["headers"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class OfflineKinematics(dj.Imported):
    definition = """
    -> SyncDLCKptsDf
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):
        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            sync_keypoints = SyncDLCKptsDf().get_data(key)
            offline_dlc_variables = getall_dlc_heading_angles(
                sync_keypoints.iloc[:, :-3]
            )  # Compute all the kinematic variables
            offline_dlc_variables[
                ["pose_time", "step_time", "step"]
            ] = sync_keypoints.iloc[
                :, -3:
            ]  # Add back in the time index
            # Shift angles so that 0 is aligned with the main screen
            offline_dlc_variables["heading_dir"] = (
                (offline_dlc_variables.heading_dir - 90) + 180
            ) % 360 - 180
            data = df2dj(offline_dlc_variables)
            data = {**key, **data}
            self.insert1(data)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_data(self, key):
        try:
            data = (self & key).fetch1()
            return pd.DataFrame(data["data"], columns=data["headers"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(self, key):
        dfs = []
        try:
            data = self.fetch()
            for d in data:
                df = pd.DataFrame(d["data"], columns=d["headers"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

