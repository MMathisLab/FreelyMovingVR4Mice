from typing import List, Optional

import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.schema import vr4mice
import vr4mice.analysis.dlc_helpers as dlc_helpers
from vr4mice.utils import logger, schema_config

schema_name = "dlc"
schema = schema_config.get_schema(schema_name, locals())

logger = logger.Logger.get_logger()


@schema
class DLCProcessor(dj.Imported):
    definition = """
    -> vr4mice.DLC
    ---
    start_time=NULL: <blob>
    frame_time=NULL: <blob>
    time_stamp=NULL: <blob>
    step=NULL: <blob>
    signal=NULL: <blob>
    photodiode_read=NULL: <blob>
    photodiode_time=NULL: <blob>
    x_pos: <blob>
    y_pos: <blob>
    heading_direction: <blob>
    head_angle: <blob>
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
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None


@schema
class DLCKptsDf(dj.Computed):
    """All available raw DLC keypoints with likelihood."""

    definition = """
    -> vr4mice.DLC
    ---
    data: <blob>
    headers : <blob>
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
            data = dlc_helpers.h5_to_dj(h5_path)
            if not "camera" in key or not "doe" in key:
                key = (vr4mice.DLC() & key).fetch(
                    *vr4mice.DLC().primary_key, as_dict=True
                )[0]
            data = {**key, **data}
            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    raise NotImplementedError()
                else:
                    data = (self & key).fetch1()
            return dlc_helpers.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class SyncDLCKptsDf(dj.Computed):
    """Filtered and game-synchronized DLC keypoints."""

    definition = """
    -> DLCKptsDf
    ---
    data: <blob>
    headers : <blob>
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
            data = dlc_helpers.df_to_dj(sync_kpts)

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
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    raise NotImplementedError()
                else:
                    data = (self & key).fetch1()
            return dlc_helpers.dj_to_df(data["data"], data["headers"], data["scorer"])

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class OfflineKinematics(dj.Computed):

    """Stores the mouse body kinematics that are computed offline.
    This table pulls data from the synchronized and interpolated DLC keypoint table
    and recomputes various kinematic variables.
    """

    definition = """
    -> SyncDLCKptsDf
    ---
    head_center_x: <blob> # the center of the mouse head in x at each frame
    head_center_y: <blob> # the center of the mouse head in y at each frame
    heading_dir: <blob> # the direction of the mouses body (tail base to neck) relative to the main screen 
    head_angle: <blob> # the angle of the head relative to heading_dir
    pose_time: <blob> # the time that the pose was inferred
    step_time: <blob> # the time of the frame in game time
    step: <blob> # the nearest game step to the dlc frame
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
            if sync_keypoints is False or sync_keypoints is None:
                logger.info(
                    f"The SyncDLCKptsDf for could not be returned {self.__class__.__name__} could not be populated for {key}"
                )
                return None

            data = dlc_helpers.get_offline_dlc_variables(sync_keypoints)
            data = data.to_dict(orient="list")
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
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch(*columns, as_dict=True)[0]
                else:
                    data = (self & key).fetch(as_dict=True)[0]
                return pd.DataFrame(data)
            else:
                return False

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}: {err}")
            return None
