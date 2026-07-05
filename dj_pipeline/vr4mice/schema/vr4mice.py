"""Core VR4Mice schema tables for datasets, metadata, and raw signals."""

import os

import datajoint as dj
import numpy as np

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

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
    camera: varchar(128)
    """
    contents = [["Imagingsource"], ["TISCam"]]


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
    exp_teensy_filepath: varchar(255) # pickle file
    exp_session_filepath: varchar(255)  # npy file
    session_label: varchar(255)
    """

    def get_keys(self, folder="/data/processed"):
        keys = []
        dataset_keys = Dataset().fetch("dataset", as_dict=True)
        camera_keys = Camera().fetch("camera", as_dict=True)
        for dk in dataset_keys:
            for ck in camera_keys:
                keys.append({**dk, **ck})
        return keys

    def populate(self):
        """Populate Dataset by iterating all dataset/camera keys."""
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        """Insert a Video row from file paths resolved for a dataset."""
        from vr4mice.actions.populate_rig import get_files_paths

        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            logger.info(f"{key['dataset']}")
            paths = get_files_paths(key["dataset"])
            video_filepath = (
                f"{paths['video_path']['dst']}/{paths['video_path']['filename']}"
            )
            timestamp_filepath = (
                f"{paths['camera_path']['dst']}/{paths['camera_path']['filename']}"
            )
            video_meta = paths["video_meta"]
            data = {
                "doe": paths["doe"],
                "video_filepath": video_filepath,
                "timestamp_filepath": timestamp_filepath,
            }
            data = {**key, **data, **video_meta}
            Video().insert1(data, skip_duplicates=True)
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class FailedSession(dj.Manual):
    """Tracks dataset/table pairs that failed during populate/compute."""

    definition = """
    # Keys that failed under populate
    -> Dataset
    failed_table_name:   varchar(64)  
    ---
    error_message                :   varchar(1024)  # Error message
    """

    def add_entry(self, dataset_key, table_name, error_message, skip_duplicates=True):
        """Insert a failed-session record for a dataset and table."""
        self.insert1(
            {
                "dataset": dataset_key,
                "failed_table_name": table_name,
                "error_message": error_message,
            },
            skip_duplicates=skip_duplicates,
        )

    @classmethod
    def should_skip(cls, key, table_name, logger=None) -> bool:
        """Return True if dataset is in FailedSession; optionally log at debug."""
        dataset = None
        if isinstance(key, dict):
            dataset = key.get("dataset")
        else:
            dataset = key

        if not dataset:
            return False

        failed = cls() & {"dataset": dataset, "failed_table_name": table_name}
        if failed:
            if logger:
                failed_rows = failed.fetch(
                    "failed_table_name", "error_message", as_dict=True
                )
                table_rows = [
                    row
                    for row in failed_rows
                    if row.get("failed_table_name") == table_name
                ]
                target_rows = table_rows if table_rows else failed_rows
                error_msg = None
                if target_rows:
                    error_msg = target_rows[-1].get("error_message")
                short_error = None
                if error_msg:
                    short_error = (
                        (error_msg[:160] + "...") if len(error_msg) > 160 else error_msg
                    )
                if short_error:
                    logger.debug(
                        f"skip {table_name} {dataset} (FailedSession: {short_error})"
                    )
                else:
                    logger.debug(f"skip {table_name} {dataset} (FailedSession)")
            return True

        return False


@schema
class Labels(dj.Lookup):
    """
    Labels definition table:
    stores custom group labels assigned to datasets
    """

    definition = """
    idx: int
    ---
    label: varchar(128)
    """

    contents = [
        # [0, "example_label"],  # auto fill during Groups manual populate (if doesn't exist)
    ]

    @classmethod
    def get_next_idx(cls):
        if not cls.fetch("idx"):
            return 0
        current_max = cls.fetch("idx").max()
        return current_max + 1 if current_max is not None else 0


@schema
class Groups(dj.Manual):
    """
    Groups definition table:
    links datasets to custom Labels entries
    """

    definition = """
    -> Dataset
    -> Labels
    """

    def add(self, dataset, label):
        try:
            key = f"dataset='{dataset}'"
            a = (Dataset & key).fetch()
            if a.size == 0:
                logger.warning(
                    f"No Dataset entry found for {dataset}: can't populate {self.__class__.__name__} table."
                )
                return
            key = f"label='{label}'"
            label_idx = (Labels & key).fetch("idx")[0]

            if label_idx is None:
                label_idx = Labels().get_next_idx()
                Labels.insert1({"idx": label_idx, "label": label})

            self.insert1({"dataset": dataset, "idx": label_idx})

        except Exception as err:
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {dataset}. Error: {err}."
            logger.warning(err)


@schema
class Labs(dj.Lookup):
    """
    Labs definition table:
    stores collaborating lab identifiers
    """

    definition = """
    idx: int
    ---
    lab: varchar(128)
    """

    contents = [[0, "test"], [1, "mathis-lab"], [2, "tolias-lab"], [3, "niell-lab"]]


@schema
class Collab(dj.Computed):
    """
    Collab definition table:
    links each dataset to a collaborating lab
    """

    definition = """
    -> Dataset
    ---
    -> Labs
    """

    def make(self, key, lab=os.environ["DJ_LAB"]):
        """Insert a Collab row linking a dataset to the configured lab."""
        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            lab = f"lab='{lab}'"
            idx = (Labs() & lab).fetch("idx", as_dict=True)[0]
            data = {**key, **idx}
            self.insert1(data)
        except Exception as err:
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


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
    duration=NULL: int
    fps=NULL: int
    width=NULL: int
    height=NULL: int
    video_filepath="": varchar(255)
    timestamp_filepath="": varchar(255)
    
    """
    # idx to reference the video in analysis table

    def get_keys(self):
        keys = []
        dataset_keys = Dataset().fetch("dataset", as_dict=True)
        camera_keys = Camera().fetch("camera", as_dict=True)
        for dk in dataset_keys:
            for ck in camera_keys:
                keys.append({**dk, **ck})
        return keys

    def populate(self):
        """Populate Video by iterating all dataset/camera keys."""
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        """Insert a Video row from rig files for a dataset."""
        from vr4mice.actions.populate_rig import get_files_paths

        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            logger.info(f"{key['dataset']}")
            paths = get_files_paths(key["dataset"])
            video_filepath = (
                f"{paths['video_path']['dst']}/{paths['video_path']['filename']}"
            )
            timestamp_filepath = (
                f"{paths['camera_path']['dst']}/{paths['camera_path']['filename']}"
            )
            video_meta = paths["video_meta"]
            data = {
                "doe": paths["doe"],
                "video_filepath": video_filepath,
                "timestamp_filepath": timestamp_filepath,
            }
            data = {**key, **data, **video_meta}
            Video().insert1(data, skip_duplicates=True)

        except Exception as err:
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


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

    def add(self, model_name):
        self.insert1({"model_name": model_name})


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
    keypoints_filepath: varchar(255) # keypoints hdf5
    proc_filepath: varchar(255)  # computed dlc metrics
    """

    def get_keys(self):
        keys = []
        video_keys = Video().fetch("dataset", "camera", "doe", as_dict=True)
        model_name = ModelName().fetch("model_name", as_dict=True)
        for vk in video_keys:
            for mn in model_name:
                keys.append({**vk, **mn})
        return keys

    def populate(self):
        """Populate DLC by iterating all dataset/camera/model keys."""
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        """Insert a DLC row using keypoints and processed paths."""
        from vr4mice.actions.populate_rig import get_files_paths

        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            logger.info(f"{key['dataset']}")
            paths = get_files_paths(key["dataset"])
            keypoints_filepath = (
                f"{paths['dlc_path']['dst']}/{paths['dlc_path']['filename']}"
            )
            proc_filepath = (
                f"{paths['proc_path']['dst']}/{paths['proc_path']['filename']}"
            )
            data = {
                "keypoints_filepath": keypoints_filepath,
                "proc_filepath": proc_filepath,
            }
            data = {**key, **data}
            DLC().insert1(data, skip_duplicates=True)

        except Exception as err:
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class MouseState(dj.Manual):  # variable State
    """
    MouseState definition table:
    stores mouse game-related position and events (see State for overlap).
    fetched from teensy output pickle file
    """

    definition = """
   -> Dataset
   ---
    x_pos: <blob>         # mouse position x
    z_pos: <blob>         # mouse position z
    head_dir: <blob>      # mouse heading direction
    mouse_can_report: <blob>  # mouse can report
    iti: <blob>           #
    obj_left: <blob>      # Object of interest on left
    
    mouse_report_correct: <blob>  # mouse_report_correct
    report_left: <blob>   # mouse_reports_left
    report_right: <blob>  # mouse_reports right
    velocity=NULL: <blob>      # new
    frame_flip=NULL: <blob>    # new to check?
    """


@schema
class State(dj.Manual):
    """
    State definition table:
    - Stores trial related information
    - Fetched from teensy output pickle file
    """

    definition = """
    -> MouseState
    ---
    start_time: <blob> 
    episode: <blob> 
    step: <blob>   
    step_time: <blob>   
    action: <blob>   
    reward: <blob>   
    terminal: <blob>    
    mouse_report_delay=NULL: <blob>
    occlusion_type=NULL: <blob>        # new
    dlc_read_time=NULL: <blob>         # new
    dlc_x: <blob>             # pos in dlc coords 
    dlc_y: <blob>             # pos in dlc coords 
    dlc_heading: <blob>       # pos in dlc coords 
    """


@schema
class Metadata(dj.Manual):
    """
    Metadata definition table:
    - Stores metadata: unity parameters
    - Fetched from teensy output pickle file
    """

    definition = """
    -> Dataset
    ---
    obj_on_left=NULL: <blob>         # the object of interest is one the left
    slit_size: <blob>                # The size of the slit that the mouse has to look through
    slit_depth=NULL: <blob>          # the depth of the slit # TO DEPRECATE ?
    trial_slit_depth: <blob>         # 
    block_labels: <blob>
    targets_height=NULL: <blob>            # the distance between the targets # TO DEPRECTAE
    target_from_midline=NULL: <blob>       # the distance between the targets and the ground   (500*floats) # TO DEPRECATE ?
    targets_z_pos=NULL: <blob>             # new
    target_rotation=NULL: <blob>           # new
    target_distance=NULL: <blob>           # new
    session_label=NULL: <blob>             # new
    camera_selection=NULL: <blob>          # new
    target_selection=NULL: <blob>          # new
    distractor_selection=NULL: <blob>      # new
    """


@schema
class SignalsPhotodiode(dj.Computed):
    """
    SignalsPhotodiode definition table:
    stores photodiode and generated sync signals from the PROC file
    """

    definition = """
    -> Dataset
    ---
    start_time             : <blob>
    photodiode_time        : <blob>         # timestamp of the photodiode signal
    photodiode_read        : <blob>         # value of the photodiode signal
    generated_frame_time   : <blob>         # timestamp of frame relative to the generated signal
    generated_send_time    : <blob>         # time that the signal gets sent from the dlc processor
    generated_signal       : <blob>         # the signal that is generated by the dlc processor
    signal_type=NULL       : varchar(32)      # type of signal generated (e.g., 'pulse', 'pulse_geo')
    signal_delay=NULL      : float            # delay between signal generation and photodiode response (seconds)
    """

    def make(self, key):
        """Compute photodiode-aligned signals for a dataset."""
        from vr4mice.actions.populate_rig import get_files_paths
        from vr4mice.analysis.latency_testing import (
            check_data,
            load_proc_dict,
            normalize_proc_data,
        )

        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            paths = get_files_paths(key["dataset"])
            proc_filepath = (
                f"{paths['proc_path']['dst']}/{paths['proc_path']['filename']}"
            )
            if not os.path.exists(proc_filepath):
                logger.debug(
                    "PROC file not found, skipping latency for %s",
                    key["dataset"],
                )
                return

            logger.debug("Populating %s from %s", key["dataset"], proc_filepath)
            photodiode_data = normalize_proc_data(
                load_proc_dict(np.load(proc_filepath, allow_pickle=True))
            )
            if check_data(photodiode_data):
                data = {
                    "start_time": photodiode_data["start_time"],
                    "photodiode_time": photodiode_data["photodiode_time"],
                    "photodiode_read": photodiode_data["photodiode_read"],
                    "generated_frame_time": photodiode_data["frame_time"],
                    "generated_send_time": photodiode_data["time_stamp"],
                    "generated_signal": photodiode_data["signal"],
                    "signal_type": photodiode_data.get("signal_type", None),
                    "signal_delay": photodiode_data.get("signal_delay", None),
                }
                self.insert1(
                    {**key, **data},
                    allow_direct_insert=True,
                    skip_duplicates=True,
                )
            else:
                FailedSession().add_entry(
                    key["dataset"],
                    self.__class__.__name__,
                    "No photodiode signal in PROC file",
                )
                logger.debug(
                    "No photodiode signal for %s; recorded in FailedSession",
                    key["dataset"],
                )
                return

        except (TypeError, ValueError) as err:
            logger.warning(
                "Skipping %s for %s: %s", self.__class__.__name__, key["dataset"], err
            )
            return
        except dj.errors.DuplicateError:
            logger.debug(
                "%s already populated for %s",
                self.__class__.__name__,
                key["dataset"],
            )
            return
        except Exception as err:
            if "Duplicate entry" in str(err):
                logger.debug(
                    "%s already populated for %s",
                    self.__class__.__name__,
                    key["dataset"],
                )
                return
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class GuiParams(dj.Manual):
    """
    GuiParams definition table:
    stores Unity game parameters fetched from the teensy output pickle file
    """

    definition = """
    -> Dataset
    ---    

    r_report_box=NULL: <blob>          # right report box coordinates
    l_report_box=NULL: <blob>          # Left report box coordinates
    start_box=NULL:  <blob>            # the coordinates of the box that the mouse has to enter to start a trial
    cropped_image=NULL: <blob>         # the pixels that we want to crop from the camera image (4*int)
    unity_arena_size=NULL: <blob>      # the size of the unity arena
    camera_rotation=NULL: <blob>       # the camera rotation, to make sure the right camera angle is displayed in the game
    velocity_threshold=NULL: <blob>           # new 
    start_box_delay=NULL: <blob>              # new
    distractor=NULL: <blob>                   # new
    target_size=NULL: <blob>                  # new
    grey_screen_active=NULL: <blob>           # new
    camera_type=NULL: float                 # new
    prob_obj_on_left=NULL: <blob>             # the probability that the object of interest is one the left
    slit_size_param=NULL: <blob>              # new 
    block_length_param=NULL: <blob>           # new 
    rotate_camera_param=NULL: <blob>          # new 
    epoch_param=NULL: <blob>                  # new 
    mouse_report_delay_param=NULL: <blob>     # new 
    prob_block_coherence=NULL: <blob>         # new 
    slit_depth_param=NULL: <blob>                  # new 
    target_selection_param=NULL: <blob>       # new
    distractor_selection_param=NULL: <blob>   # new
    occlusion_type_param=NULL: <blob>         # new
    target_spread_param=NULL: <blob>          # new
    target_rotation_param=NULL: <blob>        # new
    target_height_param=NULL: <blob>          # new 
    target_distance_param=NULL: <blob>        # new

    """


@schema
class TrainingPhaseType(dj.Lookup):
    """
    TrainingPhaseType definition table:
    stores training phase categories used to classify datasets
    """

    definition = """
    idx: int
    ---
    training_phase: varchar(128)
    """

    contents = [
        [0, "pilot"],  # early trainings
        [1, "detection"],
        [2, "discrimination"],
        [3, "test_discrimination_2_slit_sizes"],
        [4, "test_discrimination_5_slit_sizes"],
        # others with slit_size_number
    ]

    @classmethod
    def get_next_index(cls):
        current_max = cls.fetch("idx").max()
        return current_max + 1 if current_max is not None else 0


@schema
class DatasetType(dj.Computed):
    """
    DatasetType definition table:
    assigns each dataset to a training phase based on metadata and state
    """

    definition = """
    -> Metadata
    ---
    -> TrainingPhaseType
    """

    def make(self, key):
        """Assign a dataset to a training phase based on metadata and state."""
        if FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            undefined = False
            distractor = (GuiParams & key).fetch1("distractor")
            slit_size = (Metadata & key).fetch1("slit_size")
            slit_size_number = len(np.unique(slit_size))
            if distractor is None:
                # fetch pilot
                training_phase_idx = (
                    TrainingPhaseType() & "training_phase='pilot'"
                ).fetch1("idx")
            else:

                if not (State & key):
                    logger.warning(
                        f"No State found for {key}: can't determine occlusion_type."
                    )
                    return

                occlusion_type = (State & key).fetch1("occlusion_type")[0]
                if occlusion_type is None:
                    logger.warning(
                        f"Occlusion type is None for {key}: can't populate DatasetType."
                    )
                    return

                if (distractor == 0.0) & (occlusion_type == 0.0):
                    # fetch detection
                    training_phase_idx = (
                        TrainingPhaseType() & "training_phase='detection'"
                    ).fetch1("idx")

                elif distractor == 1.0:

                    if (slit_size_number == 1) & (occlusion_type == 0.0):
                        # fetch discrimination
                        training_phase_idx = (
                            TrainingPhaseType() & "training_phase='discrimination'"
                        ).fetch1("idx")

                    elif (slit_size_number > 1) & (occlusion_type != 0.0):
                        phase_type = (
                            f"test_discrimination_{slit_size_number}_slit_sizes"
                        )
                        var = f"training_phase='{phase_type}'"
                        ret = (TrainingPhaseType() & var).fetch(as_dict=True)
                        if not ret:
                            idx = TrainingPhaseType.get_next_index()
                            data = {"idx": idx, "training_phase": phase_type}
                            TrainingPhaseType.insert1(data)
                            msg = f"New entry {data} has been added to TrainingPhaseType lookup table!"
                            logger.warning(msg)
                            training_phase_idx = idx
                        else:
                            training_phase_idx = ret[0]["idx"]
                    else:
                        undefined = True
                else:
                    undefined = True

            if undefined:
                msg = f"Can't define training_phase for {key}: can't populate DatasetType."
                logger.warning(msg)
                return

            data = {"dataset": key["dataset"], "idx": training_phase_idx}
            self.insert1(data)

        except Exception as err:
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class Box(dj.Manual):
    """
    Box definition table:
    stores box positions derived from teensy output pickle file.
    fetched from teensy output pickle file
    """

    definition = """
    -> Metadata
    ---    
    l_box_x_min: <blob>
    l_box_x_max: <blob>
    l_box_z_min: <blob>
    l_box_z_max: <blob>
    r_box_x_min: <blob>
    r_box_x_max: <blob>
    r_box_z_min: <blob>
    r_box_z_max: <blob>
    tt_box_x_min: <blob>
    tt_box_x_max: <blob>
    tt_box_z_min: <blob>
    tt_box_z_max: <blob>
    tt_box_angle: <blob>
    """


@schema
class Object(dj.Lookup):
    """
    Object definition table:
    stores target and distractor object names used in the game
    """

    definition = """
    idx: int
    ---
    object: varchar(128)
    """
    contents = [
        [0, "white_cube"],
        [1, "black_cube"],
        [2, "grey_teardrop"],
        [3, "grey_pacman"],
        [4, "black_teardrop"],
        [5, "black_pacman"],
        [6, "white_teardrop"],
        [7, "white_pacman"],
        [8, "zebra_teardrop"],
        [9, "zebra_ball"],
        [10, "white_ball"],
        [11, "light_grey_zebra_teardrop"],
        [12, "dark_grey_zerba_teardrop"],
    ]

    def get_object_name(self, idx):
        key = f"idx='{idx}'"
        return (self & key).fetch1("object")
