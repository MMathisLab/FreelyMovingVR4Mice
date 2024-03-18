from pydantic import validate_call
from pathlib import Path
import numpy as np
import pickle
import h5py


@validate_call
def load_pickle(path: Path) -> dict:
    with open(path, mode="rb") as f:
        data = pickle.load(f)
    return data


def load_dlc_hdf5(path: Path):
    df_with_missing = {}
    with h5py.File(path, "r") as f:
        h5_group = f["df_with_missing"]
        for block in h5_group:
            # loads into memory
            df_with_missing[block] = h5_group[block][:]
    return df_with_missing

# Currently has to be in the form of:
# field name in file -> field name in schemas
# This is because there are cases where the field name in file has been renamed,
# meaning there are more than one variation in the files, but only one in the schemas.
field_name_transform = {
    "probGreenLeft": "prop_obj_on_left",
    "Object_on_Left": "prop_obj_on_left",  # this appears in more recent datasets it seems
    "slitSize": "slit_size",  # meta
    "targetsFromMidline": "target_from_midline",
    "targetsheight": "targets_height",
    "mouseReportDelay": "report_delay",
    "R_report_box": "right_report_box",  # meta
    "L_report_box": "left_report_box",  # meta
    "camera_roation": "camera_rotation",
    "L_box_x_min": "left_box_x_min",
    "L_box_x_max": "left_box_x_max",
    "L_box_z_min": "left_box_z_min",
    "L_box_z_max": "left_box_z_max",
    "R_box_x_min": "right_box_x_min",
    "R_box_x_max": "right_box_x_max",
    "R_box_z_min": "right_box_z_min",
    "R_box_z_max": "right_box_z_max",
    "TT_box_x_min": "tt_box_x_min",
    "TT_box_x_max": "tt_box_x_max",
    "TT_box_z_min": "tt_box_z_min",
    "TT_box_z_max": "tt_box_z_max",
    "TT_box_angle": "tt_box_angle",
}


class NormalizedData:
    dummy_data = {
        "idx": 0,  # Part of VideoToAnalyze, not sure yet what it's for in the original pipeline
        "exp_session_filepath": "",  # npy file from dj_pipeline gui that isn't usually used in this path
        # 'prop_obj_on_left': None, # This is in the vr4mice.Metadata table, but doesn't appear to be present in newer teensy pickle files, original name is probGreenLeft
        # 'angle_of_head': None, # longblob in DLCProcessor that couldn't be found and was not directly referenced in key2tables_vr4mice
    }

    def __init__(
        self,
        teensy_filepath: Path,
        related_dir: Path,
        related_prefix: str = "Imagingsource_",
    ):
        self.teensy_filepath = Path(teensy_filepath)
        self.generic_name = self.teensy_filepath.stem

        self.related_dir = related_dir
        self.related_prefix = related_prefix

        self.teensy_data = TeensyData(self.teensy_filepath, load_now=True)
        self.related_data = RelatedData(
            self.related_dir,
            self.generic_name,
            prefix=self.related_prefix,
            load_now=True,
        )

    def export(self):
        return {
            **self.dummy_data,  # load potential dummy data now, so it can be overwritten
            **self.teensy_data.export_as_fields(),
            **self.related_data.export_as_fields(),
        }


# Not sure if this class is needed for just the data pickle dict
class TeensyData:
    filepath_key = "exp_teensy_filepath"  # pickle, local

    def __init__(self, path: Path, load_now=False):
        self.path = path
        if load_now:
            self.load()

    def _process_state(self):
        state_keys = {
            "x_pos": 0,
            "z_pos": 1,
            "head_dir": 2,
            "mouse_can_report": 3,
            "iti": 4,
            "obj_left": 5,
            "mouse_report_correct": 6,
            "report_left": 7,
            "report_right": 8,
        }

        state = self.data["state"]
        self.data["state"] = {key: state[idx] for key, idx in state_keys.items()}

    def load(self):
        from datetime import datetime

        self.data = load_pickle(self.path)

        renamed_data = {}
        for key, value in self.data.items():
            if key in field_name_transform:
                key = field_name_transform[key]
            renamed_data[key] = value
        self.data = renamed_data

        extra_data = {
            "dataset": self.path.stem,  # generic name
            self.filepath_key: str(self.path),
            "doe": datetime.fromtimestamp(
                self.data["start_time"]
            ).date(),  # date of experiment
        }
        self.data.update(extra_data)

        self._process_state()

    def export_as_fields(self):
        return {**self.data}

    @staticmethod
    def export_mouse_state(data: dict):
        return {"dataset": data["dataset"], **data["state"]}


class RelatedData:
    suffixes = {
        "PROC": load_pickle,  # PROC is related to DLCProcessor
        "TS.npy": np.load,
        "DLC.hdf5": load_dlc_hdf5,
        "VIDEO.avi": lambda x: x,
    }

    datajoint_key_transform = {
        "PROC": "proc_filepath",  # original: proc_path
        "TS.npy": "timestamp_filepath",  # TS, : FS, original: camera_path
        "DLC.hdf5": "keypoints_filepath",  # local : FS ?!, original: dlc_path
        "VIDEO.avi": "video_filepath",  # remote, original: video_path
    }

    def __init__(
        self,
        directory: Path,
        generic_name: str,
        prefix="Imagingsource_",
        load_now=False,
    ):
        self.directory = directory
        self.prefix = prefix
        if not generic_name.endswith("_"):
            generic_name += "_"
        self.generic_name = generic_name
        self.data = {}
        self.found_filepaths = {}
        if load_now:
            self.load_all()

    def load_suffix(self, suffix: str):
        filename = self.generic_name + suffix
        if self.prefix is not None:
            filename = self.prefix + filename
        filepath = self.directory / filename
        if filepath.is_file():
            self.data[suffix] = self.suffixes[suffix](filepath)
            self.found_filepaths[self.datajoint_key_transform[suffix]] = str(filepath)
        else:
            print(f"{filepath} is missing, skipping loading")

    def _process_proc(self):
        # rename from field names in file to field names in the tables
        field_rename = {"head_angle": "heading_angle", "heading_direction": "head_dir"}

        for name_in_file, name_in_table in field_rename.items():
            self.data["PROC"][name_in_table] = self.data["PROC"].pop(name_in_file)

    def _process_dlc(self):
        dlc_fields = {}

        dlc_file_stem = str(Path(self.found_filepaths["keypoints_filepath"]).stem)

        # in most cases this will just be 'DLC'
        dlc_fields["model_name"] = dlc_file_stem.split("_")[-1]

        # this should be the same as self.prefix.split('_')[0]
        dlc_fields["camera"] = dlc_file_stem.split("_")[0]

        self.data["DLC.hdf5_original"] = self.data[
            "DLC.hdf5"
        ]  # Remove when done setting up the DLC processing
        self.data["DLC.hdf5"] = dlc_fields

    def _process_video_meta(self):
        # def _check_video(self, keys, video_label="video_path"):
        """
        Extracting of video's metadata and updates `self.info` dictionary.
        Args:
            keys (List[str]): List of keys to check for video file.
            video_label (str): Key to video file in `self.transfer_file`
        """

        from moviepy.editor import VideoFileClip

        video_meta = {}

        video_meta["duration"] = 0
        video_meta["fps"] = 0
        video_meta["width"] = 0
        video_meta["height"] = 0

        clip = VideoFileClip(str(self.found_filepaths["video_filepath"]))
        if clip:
            if clip.duration:
                video_meta["duration"] = clip.duration
            if clip.fps:
                video_meta["fps"] = clip.fps
            if clip.size:
                video_meta["width"], video_meta["height"] = clip.size

        self.data["VIDEO.avi"] = video_meta

    def load_all(self):
        for suffix in self.suffixes:
            self.load_suffix(suffix)
        self._process_proc()
        self._process_dlc()
        self._process_video_meta()

    def export_as_fields(self):
        return {
            **self.found_filepaths,
            **self.data["PROC"],
            **self.data["DLC.hdf5"],
            **self.data["VIDEO.avi"],
        }
