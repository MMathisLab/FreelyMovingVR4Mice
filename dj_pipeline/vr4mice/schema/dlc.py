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
    -> vr4mice.DLC
    -> base_analysis.DataFrame
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
class OffLnKinematics(dj.Imported):
    definition = """
    -> syncDLCKptsDf
    -> base_analysis.DataFrame
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
            offline_dlc_variables ["heading_dir"] = ((offline_dlc_variables.heading_dir - 90) + 180) % 360 - 180
            data = df2dj(offline_dlc_variables)
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


# TODO we should deprecate this table in favour of the OffLn_kineimatics table that way we have a nice feedforward pipline
@schema
class SyncDLCWGame(dj.Imported):
    definition = """
    -> DLCKptsDf
    -> base_analysis.DataFrame
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key):

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            dlc_dict = DLCKptsDf().get_data(key)
            df = base_analysis.DataFrame().get_data(key)
            df["start_time"] = (vr4mice.State() & key).fetch1("start_time")
            data = sync_dlc_w_game(dlc_dict, game_data=df)
            data = df2dj(data)
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
            return pd.DataFrame(data["data"], columns=data["headers"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(self):
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


# TODO: probably will be deprecated: (by bodyparts storage)
@schema
class DLCKptsBodyparts(dj.Imported):

    definition = """
    -> vr4mice.DLC
    version               : varchar(8) # keeps the deeplabcut version
    joint_name            : varchar(512) # Name of the joints
    ---
    x_pos: longblob
    y_pos: longblob
    likelihood: longblob
    time: longblob
    frame_time: longblob
    pose_time: longblob
    """

    def make(self, key):

        data = ((vr4mice.Video * vr4mice.DLC) & key).fetch(
            "keypoints_filepath", "timestamp_filepath", as_dict=True,
        )[0]

        h5fpath = data["keypoints_filepath"]
        tsfpath = data["timestamp_filepath"]

        try:
            df = pd.read_hdf(h5fpath, "df_with_missing")
        except Exception as e:
            logger.warning("Error occurred while reading HDF file:", e)
        try:
            frame_times = np.load(tsfpath)
        except Exception as e:
            logger.info("Error occurred while loading NPY file:", e)

        logger.info(f"Populating for: {h5fpath} and {tsfpath})")

        body_parts = df.columns.get_level_values(0)  # 0 as no scorer
        _, idx = np.unique(body_parts, return_index=True)
        body_parts = body_parts[np.sort(idx)]

        data = {}
        data["version"] = "live"  # TODO: ?
        data["time"] = frame_times

        data["frame_time"] = df["frame_time"].values
        data["pose_time"] = df["pose_time"].values

        for bp in body_parts:
            data["joint_name"] = bp
            # if model in df:
            if "x" in df[bp]:
                data["x_pos"] = df[bp]["x"].values
            if "y" in df[bp]:
                data["y_pos"] = df[bp]["y"].values
            if "likelihood" in df[bp]:
                data["likelihood"] = df[bp]["likelihood"].values
            data = {**key, **data}

            try:
                self.insert1(data)
                logger.info(f"{self.__class__.__name__} populated for {key} and {bp}.")

            except Exception as e:
                logger.info(
                    "Error occurred while populating {self.__class__.__name__} \
                        populated for {key} and {bp}:",
                    e,
                )
