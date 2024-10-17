from typing import List, Optional

import datajoint as dj
import numpy as np
import pandas as pd

import vr4mice.analysis.dlc_helpers as dlc_helpers
import vr4mice.analysis.utils as utils
import vr4mice.schema.vr4mice as vr4mice
import vr4mice.utils.logger
import vr4mice.utils.schema_config as schema_config  # TODO(mary): adjust paths (base/utils)

schema_name = "dlc"
schema = schema_config.get_schema(schema_name, locals())

logger = vr4mice.utils.logger.Logger.get_logger()


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
    """All available raw DLC keypoints with likelihood."""

    definition = """
    -> vr4mice.DLC
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key: dict):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            h5_path = (vr4mice.DLC & key).fetch1("keypoints_filepath")
            data = utils.h5_to_dj(h5_path)
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

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch1(*columns)
                    data = dict(zip(columns, data))
                else:
                    data = (self & key).fetch1()
            return utils.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(
        self, columns: Optional[List[str]] = None
    ) -> Optional[List[pd.DataFrame]]:
        dfs = []
        try:
            if self:
                if columns:
                    data = self.fetch(*columns, as_dict=True)
                else:
                    data = self.fetch()
            for d in data:
                df = utils.dj_to_df(d["data"], d["headers"], d["scorer"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}")
            return None


@schema
class SyncDLCKptsDf(dj.Computed):
    """Filtered and game-synchronized DLC keypoints."""

    definition = """
    -> DLCKptsDf
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key: dict):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        logger.info(f"Populating {self.__class__.__name__} for {key}.")
        try:
            sync_kpts = dlc_helpers.sync_keypoint_table(
                dataset_key=key, keypoint_cuttoff=0.6, filter_window_length=10
            )
            data = utils.df_to_dj(sync_kpts)

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

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch1(*columns)
                    data = dict(zip(columns, data))
                else:
                    data = (self & key).fetch1()
            return utils.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(
        self, columns: Optional[List[str]] = None
    ) -> Optional[List[pd.DataFrame]]:
        dfs = []
        try:
            if self:
                if columns:
                    data = self.fetch(*columns, as_dict=True)
                else:
                    data = self.fetch()
            for d in data:
                df = utils.dj_to_df(d["data"], d["headers"], d["scorer"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}")
            return None


@schema
class OfflineKinematics(dj.Computed):
    """Heading directions and head angles."""

    definition = """
    -> SyncDLCKptsDf
    ---
    data: longblob
    headers : blob
    scorer=NULL: varchar(256)
    """

    def make(self, key: dict):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        logger.info(f"Populating {self.__class__.__name__} for {key}.")

        try:
            sync_keypoints = SyncDLCKptsDf().get_data(key)
            offline_dlc_variables = dlc_helpers.compute_head_angles(
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
            data = utils.df_to_dj(offline_dlc_variables)

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

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch1(*columns)
                    data = dict(zip(columns, data))
                else:
                    data = (self & key).fetch1()
            return utils.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_all_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[List[pd.DataFrame]]:
        dfs = []
        try:
            if self:
                if columns:
                    data = self.fetch(*columns, as_dict=True)
                else:
                    data = self.fetch()
            for d in data:
                df = utils.dj_to_df(d["data"], d["headers"], d["scorer"])
                dfs.append(df)
            return dfs

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None
