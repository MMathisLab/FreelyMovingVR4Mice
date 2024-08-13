from typing import List

import datajoint as dj
import numpy as np
import pandas as pd
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema  # todo adjust paths (base/utils)

from vr4mice.schema import vr4mice

schema_name = "dlc"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()

#TODO: link with dlc base schemas!!

@schema
class DLCProcessor(dj.Imported):
    """ """

    definition = """
    -> vr4mice.DLC
    ---
    time_stamp: longblob
    x_pos: longblob
    y_pos: longblob
    heading_direction: longblob
    head_angle: longblob
    """

    def make(self, key):
        fpath = ((vr4mice.Video * vr4mice.DLC) & key).fetch(
            "proc_filepath",
        )[0]

        data = np.load(fpath, allow_pickle=True)
        data = {**key, **data}
        self.insert1(data)
        logger.info(f"{self.__class__.__name__} populated for {key}.")


@schema
class DLCKeypoints(dj.Imported):
    """ """

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
            "keypoints_filepath",
            "timestamp_filepath",
            as_dict=True,
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

