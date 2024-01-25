from typing import List

import datajoint as dj

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

from base_schemas.schemas import exp
from base_schemas.schemas import mice

schema_name = "vr4mice"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class Camera(dj.Lookup):
    """
        Camera definition table:
        to be updated if new camera name comes
    """

    definition = """
    camera: char(128)
    """
    contents = [["Imagingsource"]]


@schema
class Dataset(dj.Manual):
    """
        Dataset definition table:
        stores dataset names, representing VR experiments;
        keeps raw pickle and npy files
        format: mouse_name_doe_attempt
    """

    definition = """
    dataset: varchar(512)
    ---
    exp_teensy_filepath: filepath@data # pickle file
    exp_session_filepath: filepath@data  # npy file

    """


@schema
class VR4Mice(dj.Manual):
    """
        VR4Mice definition table:
        links together Dataset with base Mouse, Exp schemas
    """

    definition = """
   -> Dataset
   ---
   -> mice.Mouse
   -> exp.Session
   
   """


@schema
class Video(dj.Manual):
    """
        Video definition table:
        Stores raw video files metadata, as well as timestamp files
        and the path to the raw video on the rig's PC
    """

    definition = """
    -> Dataset
    -> Camera    
    doe: date  # YYYY-MM-DD
    ---  
    duration: int
    fps: int
    width: int
    height: int
    video_filepath: char(255)
    timestamp_filepath: filepath@data
    
    """
    # idx to reference the video in analysis table


@schema
class ModelName(dj.Lookup):
    """
        ModelName definition table:
        stores the names of the DLC models applied to the video analysis;
        can be extended in case of the new model type;
        currently associated with model name used in the dlc gui output
     """

    definition = """
    model_name: varchar(255)
    ---
    """
    contents = [["DLC"]]


@schema
class DLC(dj.Manual):
    """
       DLC definition table:
       stores local paths to keypoints and processed keypoints files
    """
    definition = """
    -> Video
    -> ModelName
    ---
    keypoints_filepath: filepath@data # keypoints hdf5
    proc_filepath: filepath@data  # computed dlc metrics
    
    """


@schema
class MouseState(dj.Manual):  # variable State
    """
        MouseState definition table:
        stores mouse game-related position and events @todo(check thomas)
        fetched from teensy output pickle file
    """

    definition = """
   -> Dataset
   ---
    x_pos: longblob         # mouse position x
    z_pos: longblob         # mouse position z
    head_dir: longblob      # mouse heading direction
    mouse_can_report: longblob  # mouse can report
    iti: longblob           #
    obj_left: longblob      # Object of interest on left
    
    mouse_report_correct: longblob  # mouse_report_correct
    report_left: longblob   # mouse_reports_left
    report_right: longblob  # mouse_reports right
    
    """


@schema
class State(dj.Manual):
    """
         State definition table:
         stores trial related information  @todo(thomas)
         fetched from teensy output pickle file
     """

    definition = """
    -> MouseState
    ---
    start_time: longblob 
    episode: longblob 
    step: longblob   
    step_time: longblob   
    action: longblob   
    reward: longblob   
    terminal: longblob
    
    mouse_report_delay: longblob
               
    dlc_x: longblob             # pos in dlc coords 
    dlc_y: longblob             # pos in dlc coords 
    dlc_heading: longblob       # pos in dlc coords 
    
    """


@schema
class Metadata(dj.Manual):
    """
         Metadata definition table:
         stores metadata @todo(thomas)
         fetched from teensy output pickle file
    """

    # unity params

    definition = """
    -> Dataset
    ---    
    cropped_image: longblob           # the pixels that we want to crop from the camera image (4*int)
    unity_arena_size: longblob        # the size of the unity arena
    right_report_box: longblob        # right report box coordinates
    left_report_box: longblob         # Left report box coordinates
    
    start_box:  longblob               # the coordinates of the box that the mouse has to enter to start a trial
    camera_rotation: longblob          # the camera rotation, to make sure the right camera angle is displayed in the game
    prop_obj_on_left: longblob         # the probability that the object of interest is one the left
    
    slit_size: longblob                # The size of the slit that the mouse has to look through
    slit_depth: longblob               # the depth of the slit 
    trial_slit_depth: longblob         # 
    block_labels: longblob
    
    targets_height: longblob            # the distance between the targets
    target_from_midline: longblob       # the distance between the targets and the ground   (500*floats)
    
    """


@schema
class Box(dj.Manual):
    """
        Box definition table:
        stores box positions @todo(thomas)
        fetched from teensy output pickle file
    """

    definition = """
    -> Metadata
    ---    
    left_box_x_min: mediumblob
    left_box_x_max: mediumblob
    left_box_z_min: mediumblob
    left_box_z_max: mediumblob
    right_box_x_min: mediumblob
    right_box_x_max: mediumblob
    right_box_z_min: mediumblob
    right_box_z_max: mediumblob
    tt_box_x_min: mediumblob
    tt_box_x_max: mediumblob
    tt_box_z_min: mediumblob
    tt_box_z_max: mediumblob
    tt_box_angle: mediumblob

    """
