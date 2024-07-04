# for names that don't match the convention for x,y reason
from vr4mice.actions.helpers_dj import (
    get_camera,
    get_camera_idx,
    get_model_name,
    get_path,
    get_remote_path,
    get_state,
    get_video_meta,
    no_value,
)
from vr4mice.schema import dlc, vr4mice

# note: populates DLC too


"""
    Skeleton of vr4mice datajoint tables definitions used for the population:
    Define tables, attributes and order of population
"""

transformer = {  # todo add file preprocessing
    "prop_obj_on_left": "probGreenLeft",
    #"slit_size": "slitSize",  # don't use
    "target_from_midline": "targetsFromMidline",
    "targets_height": "targetsheight",
    #'report_delay': 'mouseReportDelay', mouse_report_delay -> use only
    "right_report_box": "R_report_box",  # meta
    "left_report_box": "L_report_box",  # meta
    "camera_rotation": "camera_roation",
    "left_box_x_min": "L_box_x_min",
    "left_box_x_max": "L_box_x_max",
    "left_box_z_min": "L_box_z_min",
    "left_box_z_max": "L_box_z_max",
    "right_box_x_min": "R_box_x_min",
    "right_box_x_max": "R_box_x_max",
    "right_box_z_min": "R_box_z_min",
    "right_box_z_max": "R_box_z_max",
    "tt_box_x_min": "TT_box_x_min",
    "tt_box_x_max": "TT_box_x_max",
    "tt_box_z_min": "TT_box_z_min",
    "tt_box_z_max": "TT_box_z_max",
    "tt_box_angle": "TT_box_angle",
    "keypoints_filepath": "dlc_path",  # local : FS ?!
    "proc_filepath": "proc_path",
    "exp_teensy_filepath": "teensy_path",  # pickle, local
    "timestamp_filepath": "camera_path",  # TS, : FS
    "video_filepath": "video_path",  # remote
    # NEW
    "obj_on_left": "Object_on_Left",
    "camera_selection": "cameraSelection",
    # "start_box_delay": "startBoxDelay", #skip
    # "velocity_threshold": "velocityThreshold", #skip => use velocity_threshold
    "targets_z_pos": "targetsZpos",
    # targetSize : #skip (@tom) => use the target_size value only
    # Grey_screen_active : #skip (@tom) => use the grey_screen_active value only
    "r_report_box": "R_report_box",
    "l_report_box": "L_report_box:",
}

# todo: optimize this part of parcing (auto)
# todo: add check about rows in database in .pickle file

local_def = {
    "state": no_value,  # no
    "x_pos": get_state,
    "z_pos": get_state,
    "head_dir": get_state,
    "mouse_can_report": get_state,
    "iti": get_state,
    "mouse_report_correct": get_state,
    "obj_left": get_state,
    "report_left": get_state,
    "report_right": get_state,
    "velocity": get_state,
    "frame_flip": get_state,
    "keypoints_filepath": get_path,
    "proc_filepath": get_path,
    "exp_teensy_filepath": get_path,
    "exp_session_filepath": get_path,
    "timestamp_filepath": get_path,
    "video_filepath": get_remote_path,
    "model_name": get_model_name,  # from file name?
    "camera": get_camera,  # from file name?
    "duration": get_video_meta,
    "fps": get_video_meta,
    "width": get_video_meta,
    "height": get_video_meta,
    "camera_idx": get_camera_idx,
}

# KEYS #
dataset = ["dataset", "exp_teensy_filepath", "exp_session_filepath"]

vr4mice_table = [
    "dataset",  #
    "mouse_name",  #
    "day",  #
    "attempt",  #
]

video = [
    "dataset",  #
    "camera",  #
    "doe",
    "duration",
    "fps",
    "width",
    "height",
    "video_filepath",
    "timestamp_filepath",
    # new:
    "camera_type",
]

# TODO: check
dlc_video = [
    "camera_idx",
    "video_filepath",
]
# TODO: check
keypoints = [
    "dataset",  #
    "camera",  #
    "doe",  #
    "model_name",  #
    "keypoints_filepath",
    "proc_filepath",
]

box = [
    "dataset",
    "left_box_x_min",
    "left_box_x_max",
    "left_box_z_min",
    "left_box_z_max",
    "right_box_x_min",
    "right_box_x_max",
    "right_box_z_min",
    "right_box_z_max",
    "tt_box_x_min",
    "tt_box_x_max",
    "tt_box_z_min",
    "tt_box_z_max",
    "tt_box_angle",
]

metadata = [
    "dataset",
    "cropped_image",
    "unity_arena_size",
    "right_report_box",
    "left_report_box",
    "start_box",
    "camera_rotation",
    "prop_obj_on_left",
    "obj_on_left",
    "slit_size",
    "slit_depth",
    "trial_slit_depth",
    "block_labels",
    "targets_height",
    "target_from_midline",
    # new
    "targets_z_pos",
    "target_rotation",
    "target_distance",
    "distractor",
    "target_size",
    "grey_screen_active",
    "session_label",
    "camera_selection",
    "target_selection",
    "distractor_selection",
]

mouse_state = [  # corresponds to variable state
    "dataset",
    "x_pos",
    "z_pos",
    "head_dir",
    "mouse_can_report",
    "iti",
    "mouse_report_correct",
    "obj_left",
    "report_left",
    "report_right",
    # new
    "velocity",
    # "frame_flip",
]

state = [
    "dataset",
    "start_time",
    "episode",
    "step",
    "step_time",
    "action",
    "reward",
    "terminal",
    "mouse_report_delay",
    # new
    "start_box_delay",
    "velocity_threshold",
    "occlusion_type",
    "dlc_read_time",
    "dlc_x",
    "dlc_y",
    "dlc_heading",
]

tables = {  # order matters (dependencies))
    "Dataset": dataset,
    "MouseState": mouse_state,
    "State": state,
    "Metadata": metadata,
    "Box": box,
    "Video": video,
    # TODO: check
    "VideoToAnalyze": dlc_video,
    "DLC": keypoints,
    # "VR4Mice": vr4mice_table, # note: old version artefact
}

dj_tables = {  # in order
    "Dataset": vr4mice.Dataset(),
    "MouseState": vr4mice.MouseState(),
    "State": vr4mice.State(),
    "Metadata": vr4mice.Metadata(),
    "Box": vr4mice.Box(),
    "VideoToAnalyze": dlc.VideoToAnalyze(),
    # "DLC": dlc.DLC(),  # .npy
    "DLC": vr4mice.DLC(),  # .npy #TODO check
    "Video": vr4mice.Video(),  # .npy
    # "VR4Mice": vr4mice.VR4Mice(),  # old version artefact
}

vr4mice = {
    "tables": tables,
    "dj_tables": dj_tables,
    "local_def": local_def,
    "transformer": transformer,
}
