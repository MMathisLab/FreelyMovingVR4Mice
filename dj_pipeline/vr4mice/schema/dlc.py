from typing import List

import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.analysis.dlc_helpers import (
    df2dj,
    dj2h5,
    get_all_dlc_heading_angles,
    h52dj,
    sync_dlc_w_game,
    sync_keypoint_table,
)
from vr4mice.schema import base_analysis, vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema  # todo adjust paths (base/utils)

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

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        try:
            fpath = (vr4mice.DLC & key).fetch1("proc_filepath")
            data = np.load(fpath, allow_pickle=True)

            if (
                not "camera" in key or not "doe" in key
            ):  # TODO: add allow_direct_insert in arg
                key = (vr4mice.DLC() & key).fetch(
                    *vr4mice.DLC().primary_key, as_dict=True
                )[0]

            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class DLCKptsDf(dj.Computed):
    definition = """
    -> vr4mice.DLC
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            h5path = (vr4mice.DLC & key).fetch1("keypoints_filepath")
            data = h52dj(h5path)
            if not "camera" in key or not "doe" in key:
                key = (vr4mice.DLC() & key).fetch(
                    *vr4mice.DLC().primary_key, as_dict=True
                )[0]
            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
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
class SyncDLCKptsDf(dj.Computed):
    definition = """
    -> DLCKptsDf
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            sync_kpts = sync_keypoint_table(
                dataset_key=key, keypoint_cuttoff=0.6, filter_window_length=10
            )
            data = df2dj(sync_kpts)

            if (
                not "camera" in key or not "doe" in key
            ):  # TODO: add allow_direct_insert in arg
                key = (vr4mice.DLC() & key).fetch(
                    *vr4mice.DLC().primary_key, as_dict=True
                )[0]

            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_data(self, key):
        # TODO: add columns arg as it was made in base_analysis schema
        try:
            data = (self & key).fetch1()
            return dj2h5(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(self, key):
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
class OfflineKinematics(dj.Computed):
    """ Stores the mouse body kinematics that are computed offline.
        This table pulls data from the synchronized and interpolated DLC keypoint table 
        and recomputes various kinematic variables.
    """
    definition = """
    -> SyncDLCKptsDf
    ---
    head_center_x: longblob # the center of the mouse head in x at each frame
    head_center_y: longblob # the center of the mouse head in y at each frame
    heading_dir: longblob # the direction of the mouses body (tail base to neck) relative to the main screen 
    head_angle: longblob # the angle of the head relative to head_dir
    pose_time: longblob # the time that the pose was inferred
    step_time: longblob # the time of the frame in game time
    step: longblob # the nearest game step to the dlc frame
    """

    def make(self, key):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            sync_keypoints = SyncDLCKptsDf().get_data(key)
            offline_dlc_variables = get_all_dlc_heading_angles(
                sync_keypoints.iloc[:, :-3]
            )  # Compute all the kinematic variables
            offline_dlc_variables[
                ["pose_time", "step", "step_time"]
            ] = sync_keypoints.iloc[
                :, -3:
            ]  # Add back in the time index
            # Shift angles so that 0 is aligned with the main screen
            offline_dlc_variables["heading_dir"] = (
                (offline_dlc_variables.heading_dir - 90) + 180
            ) % 360 - 180
            
            data = offline_dlc_variables

            if (
                not "camera" in key or not "doe" in key
            ):  # TODO: add allow_direct_insert in arg
                key = (vr4mice.DLC() & key).fetch(
                    *vr4mice.DLC().primary_key, as_dict=True
                )[0]

            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_data(self, key, columns=None):
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch(*columns, as_dict=True)[0]
                else:
                    data = (self & key).fetch(as_dict=True)[0]
                df = pd.DataFrame(data)    
                return df   
            else:
                return False

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None
