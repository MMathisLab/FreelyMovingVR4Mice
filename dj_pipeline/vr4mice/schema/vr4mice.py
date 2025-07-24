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
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        from vr4mice.actions.populate_rig import get_files_paths

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


@schema
class FailedSession(dj.Manual):
    definition = """
    # Keys that failed under populate
    -> Dataset
    failed_table_name:   varchar(64)  
    ---
    error_message                :   varchar(1024)  # Error message
    """

    def add_entry(self, dataset_key, table_name, error_message, skip_duplicates=True):
        self.insert1(
            {
                "dataset": dataset_key,
                "failed_table_name": table_name,
                "error_message": error_message,
            },
            skip_duplicates=skip_duplicates,
        )


@schema
class Labels(dj.Lookup):
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
    definition = """
    idx: int
    ---
    lab: varchar(128)
    """

    contents = [[0, "test"], [1, "mathis-lab"], [2, "tolias-lab"], [3, "niell-lab"]]


@schema
class Collab(dj.Computed):
    definition = """
    -> Dataset
    ---
    -> Labs
    """

    def make(self, key, lab=os.environ["DJ_LAB"]):
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
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        from vr4mice.actions.populate_rig import get_files_paths

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
        keys = self.get_keys()
        for key in keys:
            self.make(key)

    def make(self, key):
        from vr4mice.actions.populate_rig import get_files_paths

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
    velocity=NULL: longblob      # new
    frame_flip=NULL: longblob    # new to check?
    """
    # TODO: make populate from file...


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
    mouse_report_delay=NULL: longblob
    occlusion_type=NULL: longblob        # new
    dlc_read_time=NULL: longblob         # new
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
    obj_on_left=NULL: longblob         # the object of interest is one the left
    slit_size: longblob                # The size of the slit that the mouse has to look through
    slit_depth=NULL: longblob          # the depth of the slit # TO DEPRECATE ?
    trial_slit_depth: longblob         # 
    block_labels: longblob
    targets_height=NULL: longblob            # the distance between the targets # TO DEPRECTAE
    target_from_midline=NULL: longblob       # the distance between the targets and the ground   (500*floats) # TO DEPRECATE ?
    targets_z_pos=NULL: longblob             # new
    target_rotation=NULL: longblob           # new
    target_distance=NULL: longblob           # new
    session_label=NULL: longblob             # new
    camera_selection=NULL: longblob          # new
    target_selection=NULL: longblob          # new
    distractor_selection=NULL: longblob      # new
    """


@schema
class SignalsPhotodiode(dj.Computed):

    definition = """
    -> Dataset
    ---
    start_time: blob
    photodiode_time: longblob # timestamp of the photodiode signal
    photodiode_read: longblob # value of the photodiode signal
    generated_frame_time: longblob # timestamp of frame relative to the generated signal
    generated_send_time: longblob # time that the signal gets sent from the dlc processor
    generated_signal: longblob # the signal that is generated by the dlc processor
    """
    key_source = Dataset() #& "dataset LIKE '%Latency%'"

    def make(self, key):
        from vr4mice.actions.populate_rig import get_files_paths
        from vr4mice.analysis.latency_testing import check_data

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            logger.info(f"{key['dataset']}")
            paths = get_files_paths(key["dataset"])
            proc_filepath = (
                f"{paths['proc_path']['dst']}/{paths['proc_path']['filename']}"
            )
            logger.info(f"proc_filepath: {proc_filepath}")
            if os.path.exists(proc_filepath):
                photodiode_data = np.load(proc_filepath, allow_pickle=True)
                if check_data(photodiode_data):
                    data = {
                        "start_time": photodiode_data["start_time"],
                        "photodiode_time": photodiode_data["photodiode_time"],
                        "photodiode_read": photodiode_data["photodiode_read"],
                        "generated_frame_time": photodiode_data["frame_time"],
                        "generated_send_time": photodiode_data["time_stamp"],
                        "generated_signal": photodiode_data["signal"],
                    }
                    self.insert1({**key, **data}, allow_direct_insert=True)
                else: 
                    logger.warning(f"Photodiode data check failed for {key['dataset']}")
                    return
            else:
                logger.warning(f"PROC file not found: {key['dataset']}")
                return

        except Exception as err:
            dataset = key["dataset"]
            FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class GuiParams(dj.Manual):

    definition = """
    -> Dataset
    ---    

    r_report_box=NULL: blob          # right report box coordinates
    l_report_box=NULL: blob          # Left report box coordinates
    start_box=NULL:  blob            # the coordinates of the box that the mouse has to enter to start a trial
    cropped_image=NULL: blob         # the pixels that we want to crop from the camera image (4*int)
    unity_arena_size=NULL: blob      # the size of the unity arena
    camera_rotation=NULL: blob       # the camera rotation, to make sure the right camera angle is displayed in the game
    velocity_threshold=NULL: blob           # new 
    start_box_delay=NULL: blob              # new
    distractor=NULL: blob                   # new
    target_size=NULL: blob                  # new
    grey_screen_active=NULL: blob           # new
    camera_type=NULL: float                 # new
    prob_obj_on_left=NULL: blob             # the probability that the object of interest is one the left
    slit_size_param=NULL: blob              # new 
    block_length_param=NULL: blob           # new 
    rotate_camera_param=NULL: blob          # new 
    epoch_param=NULL: blob                  # new 
    mouse_report_delay_param=NULL: blob     # new 
    prob_block_coherence=NULL: blob         # new 
    slit_depth_param=NULL: blob                  # new 
    target_selection_param=NULL: blob       # new
    distractor_selection_param=NULL: blob   # new
    occlusion_type_param=NULL: blob         # new
    target_spread_param=NULL: blob          # new
    target_rotation_param=NULL: blob        # new
    target_height_param=NULL: blob          # new 
    target_distance_param=NULL: blob        # new

    """


@schema
class TrainingPhaseType(dj.Lookup):
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
    definition = """
    -> Metadata
    ---
    -> TrainingPhaseType
    """

    def make(self, key):  # TODO(mary): refactor to a separate compact function
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
    stores box positions @todo(thomas)
    fetched from teensy output pickle file
    """

    definition = """
    -> Metadata
    ---    
    l_box_x_min: mediumblob
    l_box_x_max: mediumblob
    l_box_z_min: mediumblob
    l_box_z_max: mediumblob
    r_box_x_min: mediumblob
    r_box_x_max: mediumblob
    r_box_z_min: mediumblob
    r_box_z_max: mediumblob
    tt_box_x_min: mediumblob
    tt_box_x_max: mediumblob
    tt_box_z_min: mediumblob
    tt_box_z_max: mediumblob
    tt_box_angle: mediumblob
    """


@schema
class Object(dj.Lookup):
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
