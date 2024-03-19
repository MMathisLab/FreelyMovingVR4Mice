from typing import List

import datajoint as dj

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema  # todo adjust paths (base/utils)

schema_name = "dlc"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class VideoToAnalyze(dj.Manual):
    """
        path should be added from main Video pipelines table
    """
    definition = """
        idx : int 
        video_filepath: char(255)
        ---
    """


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
    #model_idx: int
    contents = [["DLC-live"]]


@schema
class DLC(dj.Manual):  # params?
    """
       DLC definition table:
       stores local paths to keypoints and processed keypoints files
    """
    definition = """
    -> VideoToAnalyze
    -> ModelName
    
    ---
    keypoints_filepath: filepath@data # keypoints hdf5
    proc_filepath: filepath@data  # computed dlc metrics

    """

    @property
    def key_source(self):
        return DLC() * VideoToAnalyze()


@schema
class DLCProcessor(dj.Imported):
    """

    """
    definition = """
    -> DLC
    ---
    time_step: longblob
    x_pos: longblob
    y_pos: longblob
    heading_angle: longblob
    angle_of_head: longblob
    """

    def make(self, key):
        file = (DLC & key).fetch1("proc_filepath")


@schema
class DLCKeypoints(dj.Imported):
    """

    """
    definition = """
    -> DLC 
    ---
    x_pos: longblob
    y_pos: longblob
    likelihood: longblob
    time: longblob   
    """

    def make(self, key):
        # get file to load:
        # if no file entry for video X, model X --> analyze (remote?)
        pass
