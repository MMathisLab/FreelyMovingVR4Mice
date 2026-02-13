"""
Shared pytest fixtures for FreelyMovingVR4Mice tests.

This module implements the testing infrastructure pattern with:
- Auto-marking: Tests automatically classified as unit/integration based on fixtures
- Graceful skipping: Integration tests skip with clear messages when data unavailable
- Environment configuration: .env.test.local for flexible data paths
- Synthetic mock fixtures: Unit tests use fake data, no file I/O

Golden dataset: Nightingale_2024-08-16_1 in test_data/golden_dataset/
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ==============================================================================
# Environment Configuration (load before anything else)
# ==============================================================================

# Load .env.test.local if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.test.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # dotenv not installed, rely on system environment

# RAW_ROOT_DATA_DIR fallback to temp directory
# This allows unit tests to run without data configured
if "RAW_ROOT_DATA_DIR" not in os.environ:
    raw_temp = Path(tempfile.gettempdir()) / "scene_test_raw"
    raw_temp.mkdir(exist_ok=True)
    os.environ["RAW_ROOT_DATA_DIR"] = str(raw_temp)

# Set required environment variables for populate_rig module
os.environ.setdefault("IMG_SRC", "Imagingsource")
os.environ.setdefault("GUI", "false")

# ==============================================================================
# Path Configuration
# ==============================================================================

# Get the project root (scene-migration directory)
# conftest.py is at scene-migration/scene/tests/conftest.py
# So: parent=tests/, parent.parent=scene/, parent.parent.parent=scene-migration/
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCENE_ROOT = Path(__file__).parent.parent  # scene/ directory

# Add module paths to sys.path for imports
ANALYSIS_PATH = SCENE_ROOT / "dj_pipeline" / "vr4mice" / "analysis"
ACTIONS_PATH = SCENE_ROOT / "dj_pipeline" / "vr4mice" / "actions"
BASE_SCHEMAS_PATH = SCENE_ROOT / "dj_pipeline" / "base" / "base_min_schemas"
BASE_ACTIONS_PATH = SCENE_ROOT / "dj_pipeline" / "base" / "base_actions"

for path in [ANALYSIS_PATH, ACTIONS_PATH, BASE_SCHEMAS_PATH, BASE_ACTIONS_PATH]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# ==============================================================================
# Mock DataJoint-dependent modules before they're imported
# ==============================================================================

# Mock database-dependent modules. helpers_dj.py and populate_rig.py have
# module-level imports of base_schemas and vr4mice.schema that connect to MySQL
# at import time. These mocks let unit tests import those modules without a DB.
# Integration tests clear these mocks in dj_config/pipeline fixtures (see
# integration/conftest.py) before importing the real modules.
mock_mice = MagicMock()
mock_schemas = MagicMock()
mock_schemas.mice = mock_mice
mock_base_schemas = MagicMock()
mock_base_schemas.schemas = mock_schemas

# Mock vr4mice.utils.logger
mock_logger = MagicMock()
mock_logger.Logger.get_logger.return_value = MagicMock()

# Mock vr4mice package structure
mock_vr4mice = MagicMock()
mock_vr4mice.utils = MagicMock()
mock_vr4mice.utils.logger = mock_logger

# Mock vr4mice.actions subpackage for populate_rig
mock_keys2tables_base = MagicMock()
mock_keys2tables_base.base = {}
mock_keys2tables_vr4mice = MagicMock()
mock_keys2tables_vr4mice.vr4mice = {}
mock_vr4mice.actions = MagicMock()
mock_vr4mice.actions.keys2tables_base = mock_keys2tables_base
mock_vr4mice.actions.keys2tables_vr4mice = mock_keys2tables_vr4mice

# Mock vr4mice.schema (dj_schema)
mock_dj_schema = MagicMock()
mock_vr4mice.schema = mock_dj_schema

# Apply mocks to sys.modules before any imports
sys.modules['base_schemas'] = mock_base_schemas
sys.modules['base_schemas.schemas'] = mock_schemas
sys.modules['base_schemas.schemas.mice'] = mock_mice
sys.modules['vr4mice'] = mock_vr4mice
sys.modules['vr4mice.utils'] = mock_vr4mice.utils
sys.modules['vr4mice.utils.logger'] = mock_logger
sys.modules['vr4mice.actions'] = mock_vr4mice.actions
sys.modules['vr4mice.actions.keys2tables_base'] = mock_keys2tables_base
sys.modules['vr4mice.actions.keys2tables_vr4mice'] = mock_keys2tables_vr4mice
sys.modules['vr4mice.schema'] = mock_dj_schema

# Dataset identifiers (golden dataset)
DATASET_NAME = "Nightingale_2024-08-16_1"
CAMERA_PREFIX = "Imagingsource"


# ==============================================================================
# Auto-Marking Hook
# ==============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Automatically mark tests as unit or integration based on fixture usage.

    Tests using any integration fixture are marked as 'integration'.
    All other tests are marked as 'unit'.

    Run unit tests only: pytest -m "not integration"
    Run integration tests only: pytest -m integration
    """
    integration_fixtures = {
        # MySQL/DataJoint fixtures
        "mysql_container",
        "dj_config",
        "pipeline",
        "clean_schemas",
        # Real data fixtures (golden dataset)
        "require_nightingale_data",
        "nightingale_session_path",
    }

    for item in items:
        if set(item.fixturenames) & integration_fixtures:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)


# ==============================================================================
# Golden Dataset Configuration (Nightingale)
# ==============================================================================

@pytest.fixture(scope="session")
def nightingale_session_info():
    """
    Information about the Nightingale golden dataset.

    This is the primary test dataset containing:
    - Pickle file with state data (339045 steps)
    - JSON metadata with session configuration
    - DLC HDF5 file with keypoints (281748 frames)
    - Timestamp NPY file
    - Processed PROC file
    """
    return {
        "dataset_name": DATASET_NAME,
        "camera_prefix": CAMERA_PREFIX,
        "session_dir_name": "golden_dataset",
    }


@pytest.fixture(scope="session")
def nightingale_session_path(nightingale_session_info):
    """Get path to Nightingale golden dataset directory."""
    raw_dir = Path(os.environ["RAW_ROOT_DATA_DIR"])
    # Check both possible locations:
    # 1. Directly under RAW_ROOT_DATA_DIR (e.g., /data/Celia_Set_14012026/)
    # 2. Via test_data subdirectory (e.g., scene-migration/test_data/Celia_Set_14012026/)

    # First check if PROJECT_ROOT/test_data exists (development setup)
    dev_path = PROJECT_ROOT / "test_data" / nightingale_session_info["session_dir_name"]
    if dev_path.exists():
        return dev_path

    # Otherwise use RAW_ROOT_DATA_DIR directly
    return raw_dir / nightingale_session_info["session_dir_name"]


@pytest.fixture(scope="function")
def require_nightingale_data(nightingale_session_path, nightingale_session_info):
    """
    Ensure Nightingale golden dataset exists. Skip test if not available.

    Tests using this fixture will be automatically skipped if the data
    directory doesn't exist or is missing required files. Configure
    RAW_ROOT_DATA_DIR in .env.test.local to enable these tests.

    NOTE: integration/conftest.py defines its own require_nightingale_data
    that shadows this one inside integration/. Both do the same thing but
    take different parameters due to different fixture chains.
    """
    dataset_name = nightingale_session_info["dataset_name"]
    camera_prefix = nightingale_session_info["camera_prefix"]

    if not nightingale_session_path.exists():
        pytest.skip(
            f"Golden dataset not found at: {nightingale_session_path}\n"
            "Configure RAW_ROOT_DATA_DIR in .env.test.local to enable integration tests.\n"
            "See .env.test.local.example for configuration instructions."
        )

    # Check required files exist
    required_files = [
        f"{dataset_name}.pickle",
        f"{dataset_name}.json",
        f"{camera_prefix}_{dataset_name}_DLC.hdf5",
        f"{camera_prefix}_{dataset_name}_TS.npy",
        f"{camera_prefix}_{dataset_name}_PROC",
    ]

    missing = [f for f in required_files if not (nightingale_session_path / f).exists()]
    if missing:
        pytest.skip(
            f"Golden dataset incomplete at: {nightingale_session_path}\n"
            f"Missing files: {missing}"
        )

    return nightingale_session_path


# ==============================================================================
# Mock Fixtures (Synthetic Data for Unit Tests)
# ==============================================================================

@pytest.fixture(scope="function")
def mock_pickle_data():
    """
    Synthetic pickle data matching Nightingale structure.

    Smaller size (1000 steps instead of 339045) for fast tests.
    No file I/O required - data is generated in memory.
    """
    n_steps = 1000
    n_episodes = 10
    n_blocks = 5

    # Generate episodes - ensure we have exactly n_steps
    # Create episode indices (each episode has ~100 steps)
    steps_per_episode = n_steps // n_episodes
    episodes = np.repeat(np.arange(n_episodes), steps_per_episode)
    # Pad to exact length if needed
    if len(episodes) < n_steps:
        episodes = np.concatenate([episodes, np.full(n_steps - len(episodes), n_episodes - 1)])
    episodes = episodes[:n_steps].astype(np.int32)

    # Generate step numbers within each episode
    steps = np.zeros(n_steps, dtype=np.int32)
    for ep in range(n_episodes):
        mask = episodes == ep
        steps[mask] = np.arange(mask.sum())

    return {
        # Core state data
        "state": np.random.rand(n_steps, 13).astype(np.float32),
        "episode": episodes.astype(np.int32),
        "step": steps,
        "step_time": np.linspace(0, 100, n_steps).astype(np.float64),
        "action": np.random.rand(n_steps, 1, 4).astype(np.float64),
        "reward": np.random.choice([0.0, 1.0], n_steps).astype(np.float32),
        "terminal": np.zeros(n_steps, dtype=bool),

        # Session metadata
        "session_label": ["ar_discrim_5_occluders"],
        "start_time": "2024-08-16_12-00-00",

        # Box coordinates
        "l_report_box": np.array([-10, 10, 20, 40], dtype=np.int32),
        "r_report_box": np.array([10, 30, 20, 40], dtype=np.int32),
        "start_box": np.array([0, 0, 15, 15, 5], dtype=np.int32),
        "unity_arena_size": np.array([-100, 100, -100, 100], dtype=np.int32),

        # Block/trial data
        "block_labels": np.random.choice([0, 1], n_blocks).astype(np.float64),
        "slit_size": np.random.rand(n_blocks).astype(np.float64) * 10,
        "trial_slit_depth": np.random.rand(n_blocks).astype(np.float64),

        # DLC-related data (smaller)
        "dlc_read_time": np.linspace(0, 100, 500).astype(np.float64),
        "dlc_x": np.random.rand(500).astype(np.float64) * 100,
        "dlc_y": np.random.rand(500).astype(np.float64) * 100,
        "dlc_heading": np.random.rand(500).astype(np.float64) * 360,

        # Scalar parameters
        "camera_rotation": 0.0,
        "mouse_report_delay": 0.5,
        "velocity_threshold": 5.0,
        "start_box_delay": 1.0,
        "distractor": 0,
        "target_size": 10.0,
        "grey_screen_active": 0,
        "camera_type": "Imagingsource",
        "target_selection": 1,
        "distractor_selection": 0,
        "occlusion_type": 0,
        "target_distance": 50.0,
        "target_rotation": 0.0,
        "reward_size": 1.0,
        "prob_obj_on_left": 0.5,
        "slit_size_param": 5.0,
        "block_length_param": 20,
        "rotate_camera_param": 0,
        "epoch_param": 1,
        "mouse_report_delay_param": 0.5,
        "prob_block_coherence": 0.8,
        "slit_depth_param": 1.0,
        "target_selection_param": 1,
        "distractor_selection_param": 0,
        "occlusion_type_param": 0,
        "target_spread_param": 10.0,
        "target_rotation_param": 0.0,
        "target_height_param": 5.0,
        "target_distance_param": 50.0,
        "trial_prob_object_left": np.random.rand(n_blocks).astype(np.float64),
        "trial_target_spread": np.random.rand(n_blocks).astype(np.float64) * 10,
        "trial_target_height": np.random.rand(n_blocks).astype(np.float64) * 10,

        # Cropped image placeholder
        "cropped_image": np.zeros((64, 64, 3), dtype=np.uint8),
    }


@pytest.fixture(scope="function")
def mock_json_metadata():
    """
    Synthetic JSON metadata matching Nightingale structure.

    Contains all expected keys with realistic placeholder values.
    """
    return {
        "dataset": "mock_dataset_2024-01-01_1",
        "mouse_name": "MockMouse",
        "doe": "2024-01-01",
        "session": "1",

        # Video metadata
        "video_meta": {
            "duration": 100.0,
            "fps": 30.0,
            "width": 640,
            "height": 480,
        },

        # Path dictionaries
        "teensy_path": {
            "filename": "mock_teensy.csv",
            "src": "/mock/src/path",
            "dst": "/mock/dst/path",
        },
        "dlc_path": {
            "filename": "mock_DLC.hdf5",
            "src": "/mock/src/path",
            "dst": "/mock/dst/path",
        },
        "camera_path": {
            "filename": "mock_camera.mp4",
            "src": "/mock/src/path",
            "dst": "/mock/dst/path",
        },
        "video_path": {
            "filename": "mock_video.mp4",
            "src": "/mock/src/path",
            "dst": "/mock/dst/path",
        },
        "proc_path": {
            "filename": "mock_PROC",
            "src": "/mock/src/path",
            "dst": "/mock/dst/path",
        },

        # Additional metadata
        "experimenter": "test_user",
        "rig": "test_rig",
        "task": "ar_discrim_5_occluders",
        "notes": "Mock data for testing",
    }


@pytest.fixture(scope="function")
def mock_dlc_dataframe():
    """
    Synthetic DLC DataFrame matching Nightingale structure.

    Smaller size (500 frames instead of 281748) for fast tests.
    MultiIndex columns match real DLC output format.
    """
    n_frames = 500

    # Bodyparts from the real dataset
    bodyparts = [
        "nose", "left_ear", "right_ear", "left_ear_tip", "right_ear_tip",
        "left_eye", "right_eye", "neck", "mid_back", "mouse_center",
        "mid_backend", "mid_backend2", "mid_backend3", "tail_base",
        "tail1", "tail2", "tail3", "tail4", "tail5",
        "left_shoulder", "left_midside", "left_hip",
        "right_shoulder", "right_midside", "right_hip",
        "tail_end", "head_midpoint", "frame_time", "pose_time",
    ]
    coords = ["x", "y", "likelihood"]

    # Create MultiIndex columns
    columns = pd.MultiIndex.from_product(
        [bodyparts, coords],
        names=["bodyparts", "coords"]
    )

    # Generate random data
    n_cols = len(bodyparts) * len(coords)
    data = np.random.rand(n_frames, n_cols).astype(np.float64)

    # Make likelihood values more realistic (mostly high)
    for i, bp in enumerate(bodyparts):
        likelihood_idx = i * 3 + 2  # Every 3rd column is likelihood
        data[:, likelihood_idx] = np.random.uniform(0.8, 1.0, n_frames)

    # Make x, y values in pixel range
    for i, bp in enumerate(bodyparts):
        x_idx = i * 3
        y_idx = i * 3 + 1
        data[:, x_idx] = np.random.uniform(0, 640, n_frames)
        data[:, y_idx] = np.random.uniform(0, 480, n_frames)

    return pd.DataFrame(data, columns=columns)


@pytest.fixture(scope="function")
def mock_timestamp_array():
    """
    Synthetic timestamp array.

    Smaller size (1000 frames instead of 455965) for fast tests.
    """
    n_frames = 1000
    # Simulate 30fps with some jitter
    timestamps = np.cumsum(np.random.normal(1/30, 0.001, n_frames))
    return timestamps.astype(np.float64)


@pytest.fixture(scope="function")
def mock_proc_data():
    """
    Synthetic processed DLC data.

    Smaller size (1000 frames instead of 281876) for fast tests.
    """
    n_frames = 1000
    n_photodiode = 10000

    return {
        "x_pos": np.random.rand(n_frames).astype(np.float32) * 100,
        "y_pos": np.random.rand(n_frames).astype(np.float32) * 100,
        "heading_direction": np.random.rand(n_frames).astype(np.float64) * 360,
        "head_angle": np.random.rand(n_frames).astype(np.float64) * 180 - 90,
        "timestamps": np.linspace(0, 100, n_frames).astype(np.float64),
        "photodiode_read": np.random.rand(n_photodiode).astype(np.float64),
        "photodiode_time": np.linspace(0, 100, n_photodiode).astype(np.float64),
        "bodypart_x": np.random.rand(n_frames, 29).astype(np.float32) * 640,
        "bodypart_y": np.random.rand(n_frames, 29).astype(np.float32) * 480,
        "bodypart_likelihood": np.random.uniform(0.8, 1.0, (n_frames, 29)).astype(np.float32),
        "dlc_timestamps": np.linspace(0, 100, n_frames).astype(np.float64),
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
    """Expected shapes for key arrays in pickle (real data)."""
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
    """Expected shape of DLC DataFrame (real data)."""
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
# Standard Keys Fixtures
# ==============================================================================

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


