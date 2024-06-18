from typing import List

import datajoint as dj
import numpy as np
import pandas as pd
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema  # todo adjust paths (base/utils)

schema_name = "dlc"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


# to do add dataset in key, as now it's by filepath and that's sad


@schema
class VideoToAnalyze(dj.Manual):
    """
    path should be added from main Video pipelines table
    """

    definition = """
    camera_idx : int 
    video_filepath: varchar(255)
    ---
    """

    def get_dataset(self, key):
        key2 = {"video_filepath": key["video_filepath"]}
        dataset = (vr4mice.Video & key2).fetch1("dataset")
        return dataset


@schema
class ModelName(dj.Lookup):  # add adapter : separate table
    """
    ModelName definition table:
    stores the names of the DLC models applied to the video analysis;
    can be extended in case of the new model type;
    currently associated with model name used in the dlc gui output

    model_name is not PK, to make it possible to rename,
    but still keeping all data coherent
    """

    definition = """
    model_name: varchar(255)
    """
    contents = [["DLC"]]

    def add(self, model_name):
        self.insert1({"model_name": model_name})


@schema
class DLC(dj.Imported):  # params?
    """
    DLC definition table:
    stores local paths to keypoints and processed keypoints files
    """

    definition = """
    -> VideoToAnalyze
    -> ModelName
    ---
    keypoints_filepath: varchar(255)  # keypoints hdf5
    proc_filepath: varchar(255)  # computed dlc metrics
    """

    @property
    def key_source(self):
        return VideoToAnalyze

    def make(self, key):
        from vr4mice.schema import vr4mice

        key2 = {"video_filepath": key["video_filepath"]}
        data = ((vr4mice.Video * vr4mice.DLC) & key2).fetch(
            "model_name",
            "video_filepath",
            "keypoints_filepath",
            "proc_filepath",
            as_dict=True,
        )[0]
        data = {**key, **data}
        self.insert1(data)
        logger.info(f"{self.__class__.__name__} populated for {key}.")


@schema
class DLCProcessor(dj.Imported):
    """ """

    definition = """
    -> DLC
    ---
    time_stamp: longblob
    x_pos: longblob
    y_pos: longblob
    heading_direction: longblob
    head_angle: longblob
    """

    def make(self, key):
        fpath = (DLC & key).fetch1("proc_filepath")
        data = np.load(fpath, allow_pickle=True)
        data = {**key, **data}
        self.insert1(data)
        logger.info(f"{self.__class__.__name__} populated for {key}.")


@schema
class DLCKeypoints(dj.Imported):
    """ """

    definition = """
    -> DLC 
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

        from vr4mice.schema import vr4mice

        h5fpath = (DLC & key).fetch1("keypoints_filepath")
        key2 = {"video_filepath": key["video_filepath"]}
        tsfpath = (vr4mice.Video & key2).fetch1("timestamp_filepath")
        try:
            df = pd.read_hdf(h5fpath, "df_with_missing")
        except Exception as e:
            logger.warning("Error occurred while reading HDF file:", e)
        try:
            frame_times = np.load(tsfpath)
        except Exception as e:
            logger.info("Error occurred while loading NPY file:", e)

        logger.info("Populating for: " + str(h5fpath) + " and " + str(tsfpath))

        body_parts = df.columns.get_level_values(0)  # 0 as no scorer
        _, idx = np.unique(body_parts, return_index=True)
        body_parts = body_parts[np.sort(idx)]

        data = {}
        data["version"] = "live"  # todo: adjust: conda install?
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

        def get_dataset(self, key):
            key2 = {"video_filepath": key["video_filepath"]}
            dataset = (vr4mice.Video & key2).fetch1("dataset")
            return dataset
