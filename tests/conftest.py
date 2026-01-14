"""
Shared pytest fixtures for FreelyMovingVR4Mice tests.

Test data location: test_data/Celia_Set_14012026/
Dataset key: Nightingale_2024-08-16_1
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ==============================================================================
# Path Configuration
# ==============================================================================

# Get the project root (scene-migration directory)
# conftest.py is at scene-migration/scene/tests/conftest.py
# So: parent=tests/, parent.parent=scene/, parent.parent.parent=scene-migration/
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data" / "Celia_Set_14012026"

# Dataset identifiers
DATASET_NAME = "Nightingale_2024-08-16_1"
CAMERA_PREFIX = "Imagingsource"


# ==============================================================================
# Data File Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def test_data_path():
    """Path to test data directory."""
    assert TEST_DATA_DIR.exists(), f"Test data directory not found: {TEST_DATA_DIR}"
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def pickle_path(test_data_path):
    """Path to pickle file."""
    path = test_data_path / f"{DATASET_NAME}.pickle"
    assert path.exists(), f"Pickle file not found: {path}"
    return path


@pytest.fixture(scope="session")
def json_path(test_data_path):
    """Path to JSON metadata file."""
    path = test_data_path / f"{DATASET_NAME}.json"
    assert path.exists(), f"JSON file not found: {path}"
    return path


@pytest.fixture(scope="session")
def dlc_hdf5_path(test_data_path):
    """Path to DLC HDF5 file."""
    path = test_data_path / f"{CAMERA_PREFIX}_{DATASET_NAME}_DLC.hdf5"
    assert path.exists(), f"DLC HDF5 file not found: {path}"
    return path


@pytest.fixture(scope="session")
def timestamp_path(test_data_path):
    """Path to timestamp NPY file."""
    path = test_data_path / f"{CAMERA_PREFIX}_{DATASET_NAME}_TS.npy"
    assert path.exists(), f"Timestamp file not found: {path}"
    return path


@pytest.fixture(scope="session")
def proc_path(test_data_path):
    """Path to PROC file."""
    path = test_data_path / f"{CAMERA_PREFIX}_{DATASET_NAME}_PROC"
    assert path.exists(), f"PROC file not found: {path}"
    return path


# ==============================================================================
# Loaded Data Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def pickle_data(pickle_path):
    """
    Loaded pickle file data.

    Contains 53 keys:
    - 33 numpy arrays (various shapes/dtypes)
    - 18 scalars (float/int)
    - 2 lists
    """
    with open(pickle_path, "rb") as f:
        return pickle.load(f)


@pytest.fixture(scope="session")
def json_metadata(json_path):
    """
    Loaded JSON metadata.

    Contains 33 keys including nested path dicts:
    - teensy_path, dlc_path, camera_path, video_path, proc_path
    - video_meta (duration, fps, width, height)
    - Mouse/session info
    """
    with open(json_path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def dlc_dataframe(dlc_hdf5_path):
    """
    DLC keypoints as DataFrame.

    Shape: (281748, 83)
    MultiIndex: 2 levels (bodyparts, coords)
    Column names: ['bodyparts', 'coords']
    """
    return pd.read_hdf(dlc_hdf5_path)


@pytest.fixture(scope="session")
def timestamp_array(timestamp_path):
    """
    Camera timestamps.

    Shape: (455965,)
    Dtype: float64
    Duration: ~4559.65 seconds
    """
    return np.load(timestamp_path)


@pytest.fixture(scope="session")
def proc_data(proc_path):
    """
    Processed DLC data.

    Dict with 11 keys including:
    - x_pos, y_pos: (281876,) float32
    - heading_direction, head_angle: (281876,) float64
    - photodiode_read, photodiode_time: (38754103,) float64
    """
    return np.load(proc_path, allow_pickle=True)


# ==============================================================================
# Derived Data Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def state_array(pickle_data):
    """
    State array from pickle.

    Shape: (339045, 13)
    Dtype: float32
    Contains: x_pos, z_pos, head_dir, mouse_can_report, iti,
              obj_left, mouse_report_correct, report_left, report_right, velocity
    """
    return pickle_data["state"]


@pytest.fixture(scope="session")
def dataset_key():
    """Standard dataset key for queries."""
    return {"dataset": DATASET_NAME}


@pytest.fixture(scope="session")
def video_key():
    """Standard video key for queries."""
    return {
        "dataset": DATASET_NAME,
        "camera": CAMERA_PREFIX,
        "doe": "2024-08-16",
    }


@pytest.fixture(scope="session")
def dlc_key():
    """Standard DLC key for queries."""
    return {
        "dataset": DATASET_NAME,
        "camera": CAMERA_PREFIX,
        "doe": "2024-08-16",
        "model_name": "DLC",
    }


# ==============================================================================
# Expected Values Fixtures (for assertions)
# ==============================================================================

@pytest.fixture(scope="session")
def expected_pickle_keys():
    """Expected keys in pickle file."""
    return [
        "start_time", "episode", "step", "step_time", "state", "action",
        "reward", "terminal", "session_label", "dlc_read_time", "dlc_x",
        "dlc_y", "dlc_heading", "block_labels", "slit_size", "trial_slit_depth",
        "r_report_box", "l_report_box", "start_box", "cropped_image",
        "unity_arena_size", "camera_rotation", "mouse_report_delay",
        "velocity_threshold", "start_box_delay", "distractor", "target_size",
        "grey_screen_active", "camera_type", "target_selection",
        "distractor_selection", "occlusion_type", "target_distance",
        "target_rotation", "reward_size", "prob_obj_on_left", "slit_size_param",
        "block_length_param", "rotate_camera_param", "epoch_param",
        "mouse_report_delay_param", "prob_block_coherence", "slit_depth_param",
        "target_selection_param", "distractor_selection_param",
        "occlusion_type_param", "target_spread_param", "target_rotation_param",
        "target_height_param", "target_distance_param", "trial_prob_object_left",
        "trial_target_spread", "trial_target_height"
    ]


@pytest.fixture(scope="session")
def expected_array_shapes():
    """Expected shapes for key arrays in pickle."""
    return {
        "state": (339045, 13),
        "episode": (339045,),
        "step": (339045,),
        "step_time": (339045,),
        "action": (339045, 1, 4),
        "reward": (339045,),
        "terminal": (339045,),
        "slit_size": (207,),
        "block_labels": (207,),
        "l_report_box": (4,),
        "r_report_box": (4,),
        "start_box": (5,),
        "unity_arena_size": (4,),
    }


@pytest.fixture(scope="session")
def expected_array_dtypes():
    """Expected dtypes for key arrays in pickle."""
    return {
        "state": np.float32,
        "episode": np.int32,
        "step": np.int32,
        "step_time": np.float64,
        "action": np.float64,
        "reward": np.float32,
        "terminal": np.bool_,
        "slit_size": np.float64,
        "l_report_box": np.int32,
    }


@pytest.fixture(scope="session")
def expected_dlc_shape():
    """Expected shape of DLC DataFrame."""
    return (281748, 83)


@pytest.fixture(scope="session")
def expected_dlc_bodyparts():
    """Expected bodyparts in DLC data."""
    return [
        "nose", "left_ear", "right_ear", "left_ear_tip", "right_ear_tip",
        "left_eye", "right_eye", "neck", "mid_back", "mouse_center",
        "mid_backend", "mid_backend2", "mid_backend3", "tail_base",
        "tail1", "tail2", "tail3", "tail4", "tail5",
        "left_shoulder", "left_midside", "left_hip",
        "right_shoulder", "right_midside", "right_hip",
        "tail_end", "head_midpoint", "frame_time", "pose_time"
    ]


@pytest.fixture(scope="session")
def state_index_map():
    """Mapping of state field names to array indices."""
    return {
        "x_pos": 0,
        "z_pos": 1,
        "head_dir": 2,
        "mouse_can_report": 3,
        "iti": 4,
        "obj_left": 5,
        "mouse_report_correct": 6,
        "report_left": 7,
        "report_right": 8,
        "velocity": 9,
    }


# ==============================================================================
# Utility Fixtures
# ==============================================================================

@pytest.fixture
def temp_pickle_data(pickle_data):
    """
    Copy of pickle data that can be modified.
    Use when tests need to modify the data.
    """
    return pickle_data.copy()


@pytest.fixture
def sample_dlc_subset(dlc_dataframe):
    """Small subset of DLC data for faster tests."""
    return dlc_dataframe.iloc[:1000].copy()
