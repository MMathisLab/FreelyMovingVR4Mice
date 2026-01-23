"""
Unit tests for helpers_dj.py

Tests the helper functions used for data transformation during
database population, particularly state array extraction and
path handling.

NOTE: These tests use synthetic mock data - no real file I/O required.
Tests that verify specific real data shapes are in tests/integration/.

Note: Database-dependent modules are mocked in conftest.py to allow
testing without DataJoint connection.
"""

import numpy as np
import pytest
from pathlib import Path

# Import from helpers_dj (mocks configured in conftest.py)
from helpers_dj import (
    get_state,
    get_box,
    get_camera,
    get_model_name,
    get_video_meta,
    get_name,
    no_value,
    default,
    get_camera_idx,
    get_path,
    get_remote_path,
    no_value_opto,
    no_joystick,
    no_force_field,
)


# ==============================================================================
# Tests for get_state
# ==============================================================================

class TestGetState:
    """Tests for get_state function - extracts values from state array."""

    def test_get_state_x_pos(self, mock_pickle_data, state_index_map):
        """Should extract x_pos (index 0) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="x_pos")
        assert result is not None
        assert len(result) == len(mock_pickle_data["state"])
        # First value should match state[0][0]
        assert result[0] == mock_pickle_data["state"][0][state_index_map["x_pos"]]

    def test_get_state_z_pos(self, mock_pickle_data, state_index_map):
        """Should extract z_pos (index 1) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="z_pos")
        assert result is not None
        assert len(result) == len(mock_pickle_data["state"])
        assert result[0] == mock_pickle_data["state"][0][state_index_map["z_pos"]]

    def test_get_state_head_dir(self, mock_pickle_data, state_index_map):
        """Should extract head_dir (index 2) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="head_dir")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["head_dir"]]

    def test_get_state_mouse_can_report(self, mock_pickle_data, state_index_map):
        """Should extract mouse_can_report (index 3) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="mouse_can_report")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["mouse_can_report"]]

    def test_get_state_iti(self, mock_pickle_data, state_index_map):
        """Should extract iti (index 4) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="iti")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["iti"]]

    def test_get_state_obj_left(self, mock_pickle_data, state_index_map):
        """Should extract obj_left (index 5) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="obj_left")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["obj_left"]]

    def test_get_state_mouse_report_correct(self, mock_pickle_data, state_index_map):
        """Should extract mouse_report_correct (index 6) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="mouse_report_correct")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["mouse_report_correct"]]

    def test_get_state_report_left(self, mock_pickle_data, state_index_map):
        """Should extract report_left (index 7) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="report_left")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["report_left"]]

    def test_get_state_report_right(self, mock_pickle_data, state_index_map):
        """Should extract report_right (index 8) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="report_right")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["report_right"]]

    def test_get_state_velocity(self, mock_pickle_data, state_index_map):
        """Should extract velocity (index 9) from state array."""
        result = get_state(raw_data=mock_pickle_data, key="velocity")
        assert result is not None
        assert result[0] == mock_pickle_data["state"][0][state_index_map["velocity"]]

    def test_get_state_invalid_key(self, mock_pickle_data):
        """Invalid key should return None."""
        result = get_state(raw_data=mock_pickle_data, key="invalid_key")
        assert result is None

    def test_get_state_none_raw_data(self):
        """None raw_data should return None."""
        result = get_state(raw_data=None, key="x_pos")
        assert result is None

    def test_get_state_none_key(self, mock_pickle_data):
        """None key should return None."""
        result = get_state(raw_data=mock_pickle_data, key=None)
        assert result is None

    def test_get_state_all_keys_extract_correctly(self, mock_pickle_data, state_index_map):
        """All state keys should extract to correct length arrays."""
        for key in state_index_map.keys():
            result = get_state(raw_data=mock_pickle_data, key=key)
            assert result is not None, f"Key {key} returned None"
            assert len(result) == len(mock_pickle_data["state"]), \
                f"Key {key} length mismatch"

    def test_get_state_values_match_direct_access(self, mock_pickle_data, state_index_map):
        """Extracted values should match direct array indexing."""
        for key, idx in state_index_map.items():
            result = get_state(raw_data=mock_pickle_data, key=key)
            # Check first few values
            for i in range(min(10, len(result))):
                expected = mock_pickle_data["state"][i][idx]
                assert result[i] == expected, \
                    f"Key {key}, index {i}: expected {expected}, got {result[i]}"


# ==============================================================================
# Tests for get_box
# ==============================================================================

class TestGetBox:
    """Tests for get_box function - extracts box coordinates.

    The function has two modes:
    - Old style: if transformer[key] exists in raw_data, returns entire array
    - New style: looks up key in internal mappings, returns indexed value
    """

    # Old style tests - transformer maps to existing raw_data key
    def test_get_box_old_style_returns_entire_array(self, mock_pickle_data):
        """Old style: transformer mapping to existing key returns whole array."""
        transformer = {"l_box_x_min": "l_report_box"}
        result = get_box(raw_data=mock_pickle_data, key="l_box_x_min", transformer=transformer)
        # Old style returns the entire array
        assert np.array_equal(result, mock_pickle_data["l_report_box"])

    def test_get_box_old_style_r_report_box(self, mock_pickle_data):
        """Old style: r_report_box returns whole array."""
        transformer = {"r_box_x_min": "r_report_box"}
        result = get_box(raw_data=mock_pickle_data, key="r_box_x_min", transformer=transformer)
        assert np.array_equal(result, mock_pickle_data["r_report_box"])

    def test_get_box_old_style_start_box(self, mock_pickle_data):
        """Old style: start_box returns whole array."""
        transformer = {"tt_box_x_min": "start_box"}
        result = get_box(raw_data=mock_pickle_data, key="tt_box_x_min", transformer=transformer)
        assert np.array_equal(result, mock_pickle_data["start_box"])

    # New style tests - transformer maps to non-existent key, uses internal mapping
    def test_get_box_new_style_l_box_x_min(self, mock_pickle_data):
        """New style: extracts l_box_x_min (index 0) from l_report_box."""
        # Map to a key that doesn't exist in raw_data to trigger new style
        transformer = {"l_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="l_box_x_min", transformer=transformer)
        assert result == mock_pickle_data["l_report_box"][0]

    def test_get_box_new_style_l_box_x_max(self, mock_pickle_data):
        """New style: extracts l_box_x_max (index 1) from l_report_box."""
        transformer = {"l_box_x_max": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="l_box_x_max", transformer=transformer)
        assert result == mock_pickle_data["l_report_box"][1]

    def test_get_box_new_style_l_box_z_min(self, mock_pickle_data):
        """New style: extracts l_box_z_min (index 2) from l_report_box."""
        transformer = {"l_box_z_min": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="l_box_z_min", transformer=transformer)
        assert result == mock_pickle_data["l_report_box"][2]

    def test_get_box_new_style_l_box_z_max(self, mock_pickle_data):
        """New style: extracts l_box_z_max (index 3) from l_report_box."""
        transformer = {"l_box_z_max": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="l_box_z_max", transformer=transformer)
        assert result == mock_pickle_data["l_report_box"][3]

    def test_get_box_new_style_r_box_x_min(self, mock_pickle_data):
        """New style: extracts r_box_x_min (index 0) from r_report_box."""
        transformer = {"r_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="r_box_x_min", transformer=transformer)
        assert result == mock_pickle_data["r_report_box"][0]

    def test_get_box_new_style_tt_box_x_min(self, mock_pickle_data):
        """New style: extracts tt_box_x_min (index 0) from start_box."""
        transformer = {"tt_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="tt_box_x_min", transformer=transformer)
        assert result == mock_pickle_data["start_box"][0]

    def test_get_box_new_style_tt_box_angle(self, mock_pickle_data):
        """New style: extracts tt_box_angle (index 4) from start_box."""
        transformer = {"tt_box_angle": "nonexistent_key"}
        result = get_box(raw_data=mock_pickle_data, key="tt_box_angle", transformer=transformer)
        assert result == mock_pickle_data["start_box"][4]


# ==============================================================================
# Tests for get_camera
# ==============================================================================

class TestGetCamera:
    """Tests for get_camera function - extracts camera name from filename."""

    def test_get_camera_from_dlc_path(self, mock_json_metadata):
        """Should extract camera name from DLC filename."""
        # The DLC filename follows pattern: {Camera}_{dataset}_DLC.hdf5
        raw_data = {"dlc_path": mock_json_metadata["dlc_path"]}
        result = get_camera(raw_data=raw_data)
        # mock_json_metadata has filename: mock_DLC.hdf5
        # Camera should be "mock"
        assert result == "mock"

    def test_get_camera_extracts_first_part(self):
        """Should extract the first part before underscore."""
        raw_data = {
            "dlc_path": {
                "filename": "TestCamera_Mouse_2024-01-01_1_DLC.hdf5",
                "dst": "/some/path",
                "src": "/source/path"
            }
        }
        result = get_camera(raw_data=raw_data)
        assert result == "TestCamera"


# ==============================================================================
# Tests for get_model_name
# ==============================================================================

class TestGetModelName:
    """Tests for get_model_name function - extracts DLC model name."""

    def test_get_model_name_from_dlc_path(self, mock_json_metadata):
        """Should extract model name from DLC filename."""
        raw_data = {"dlc_path": mock_json_metadata["dlc_path"]}
        result = get_model_name(raw_data=raw_data)
        # mock_json_metadata has filename: mock_DLC.hdf5
        # Model name should be "DLC"
        assert result == "DLC"

    def test_get_model_name_extracts_last_part(self):
        """Should extract the last part before extension."""
        raw_data = {
            "dlc_path": {
                "filename": "Camera_Mouse_2024-01-01_1_CustomModel.hdf5",
                "dst": "/some/path",
                "src": "/source/path"
            }
        }
        result = get_model_name(raw_data=raw_data)
        assert result == "CustomModel"


# ==============================================================================
# Tests for get_video_meta
# ==============================================================================

class TestGetVideoMeta:
    """Tests for get_video_meta function - extracts video metadata."""

    def test_get_video_meta_duration(self, mock_json_metadata):
        """Should extract video duration."""
        result = get_video_meta(raw_data=mock_json_metadata, key="duration")
        assert result == mock_json_metadata["video_meta"]["duration"]
        assert result == 100.0  # Value from mock

    def test_get_video_meta_fps(self, mock_json_metadata):
        """Should extract video FPS."""
        result = get_video_meta(raw_data=mock_json_metadata, key="fps")
        assert result == mock_json_metadata["video_meta"]["fps"]
        assert result == 30.0  # Value from mock

    def test_get_video_meta_width(self, mock_json_metadata):
        """Should extract video width."""
        result = get_video_meta(raw_data=mock_json_metadata, key="width")
        assert result == mock_json_metadata["video_meta"]["width"]
        assert result == 640  # Value from mock

    def test_get_video_meta_height(self, mock_json_metadata):
        """Should extract video height."""
        result = get_video_meta(raw_data=mock_json_metadata, key="height")
        assert result == mock_json_metadata["video_meta"]["height"]
        assert result == 480  # Value from mock


# ==============================================================================
# Tests for get_name
# ==============================================================================

class TestGetName:
    """Tests for get_name function - extracts session label."""

    def test_get_name_from_list(self, mock_pickle_data):
        """Should extract first element from list."""
        result = get_name(raw_data=mock_pickle_data, key="session_label")
        assert result == mock_pickle_data["session_label"][0]
        assert result == "ar_discrim_5_occluders"  # Value from mock

    def test_get_name_returns_none_for_non_list(self):
        """Should return None for non-list values."""
        raw_data = {"session_label": "not_a_list"}
        result = get_name(raw_data=raw_data, key="session_label")
        assert result is None


# ==============================================================================
# Tests for utility functions
# ==============================================================================

class TestUtilityFunctions:
    """Tests for simple utility functions."""

    def test_no_value_returns_none_string(self):
        """no_value should return 'none' string."""
        result = no_value()
        assert result == "none"

    def test_default_returns_minus_one(self):
        """default should return -1."""
        result = default()
        assert result == -1

    def test_get_camera_idx_returns_one(self):
        """get_camera_idx should return 1."""
        result = get_camera_idx()
        assert result == 1


# ==============================================================================
# Tests for state extraction with mock data shapes
# ==============================================================================

class TestStateExtractionShapes:
    """Tests verifying extracted state arrays have correct shapes."""

    def test_extracted_state_shape_matches_input(self, mock_pickle_data):
        """Extracted state should have same length as mock state array."""
        result = get_state(raw_data=mock_pickle_data, key="x_pos")
        # Mock data has 1000 steps
        assert len(result) == mock_pickle_data["state"].shape[0]
        assert len(result) == 1000  # Mock fixture default

    def test_all_state_extractions_same_length(self, mock_pickle_data, state_index_map):
        """All extracted state arrays should have same length."""
        lengths = set()
        for key in state_index_map.keys():
            result = get_state(raw_data=mock_pickle_data, key=key)
            lengths.add(len(result))
        assert len(lengths) == 1, f"Different lengths found: {lengths}"
        # All should match the mock state array length
        assert mock_pickle_data["state"].shape[0] in lengths


# ==============================================================================
# Tests for get_path
# ==============================================================================

class TestGetPath:
    """Tests for get_path function - file path construction and moving.

    The function:
    1. Looks up raw_key from transformer[key]
    2. Gets file_info from raw_data[raw_key]
    3. Constructs path from file_info["dst"] and file_info["filename"]
    4. Verifies path exists
    5. Optionally moves file from /data to processed folder
    """

    @pytest.fixture
    def mock_file_info(self, tmp_path):
        """Create a mock file structure for testing get_path."""
        # Create directory structure: tmp_path/data/some_dir/
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sub_dir = data_dir / "test_session"
        sub_dir.mkdir()

        # Create a test file
        test_file = sub_dir / "test_data.pickle"
        test_file.write_text("test content")

        return {
            "base_path": tmp_path,
            "data_dir": data_dir,
            "sub_dir": sub_dir,
            "test_file": test_file,
        }

    def test_get_path_constructs_valid_path(self, mock_file_info):
        """get_path should construct a valid file path from raw_data.

        Note: get_path extracts just the final directory name from dst,
        then constructs: srcf / final_dir_name / filename
        """
        raw_data = {
            "teensy_path": {
                "filename": "test_data.pickle",
                # dst path - get_path uses Path(dst).name to get final component
                "dst": str(mock_file_info["sub_dir"]),
                "src": "/remote/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        # get_path constructs: srcf / Path(dst).name / filename
        # So srcf should be the parent of the directory containing the file
        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),  # Parent of test_session
            move=False,
        )

        # Should return the path if file exists
        assert result is not False
        assert Path(result).exists()

    def test_get_path_returns_false_for_nonexistent_file(self, tmp_path):
        """get_path should return False when file doesn't exist."""
        raw_data = {
            "teensy_path": {
                "filename": "nonexistent.pickle",
                "dst": str(tmp_path / "nonexistent_dir"),
                "src": "/remote/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(tmp_path),
            move=False,
        )

        assert result is False

    def test_get_path_moves_file_when_move_true(self, mock_file_info):
        """get_path should move file to processed folder when move=True."""
        # Setup: file is in data_dir/data/ (parent named 'data')
        # get_path expects parent to be named 'data' to trigger move
        data_subdir = mock_file_info["data_dir"] / "data"
        data_subdir.mkdir(exist_ok=True)
        source_file = data_subdir / "moveable.pickle"
        source_file.write_text("content to move")

        raw_data = {
            "teensy_path": {
                "filename": "moveable.pickle",
                "dst": str(data_subdir),
                "src": "/remote/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),
            dstf="processed",
            move=True,
        )

        # File should be moved to processed folder
        processed_dir = mock_file_info["data_dir"] / "processed"
        processed_file = processed_dir / "moveable.pickle"

        assert processed_dir.exists()
        assert processed_file.exists()
        assert not source_file.exists()  # Original should be gone
        assert str(result) == str(processed_file)

    def test_get_path_no_move_when_move_false(self, mock_file_info):
        """get_path should not move file when move=False."""
        # Setup directory structure
        data_subdir = mock_file_info["data_dir"] / "data"
        data_subdir.mkdir(exist_ok=True)
        source_file = data_subdir / "stay_here.pickle"
        source_file.write_text("content to stay")

        raw_data = {
            "teensy_path": {
                "filename": "stay_here.pickle",
                "dst": str(data_subdir),
                "src": "/remote/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),
            move=False,
        )

        # File should still be in original location
        assert source_file.exists()
        assert Path(result).exists()

    def test_get_path_exp_session_filepath_uses_npy(self, mock_file_info):
        """exp_session_filepath key should look for .npy file instead.

        Note: When key is "exp_session_filepath", the function internally
        changes it to "exp_teensy_filepath" and looks for .npy extension.
        """
        # Create session directory structure
        session_dir = mock_file_info["data_dir"] / "test_session"
        session_dir.mkdir(exist_ok=True)
        pickle_file = session_dir / "test_session.pickle"
        npy_file = session_dir / "test_session.npy"
        pickle_file.write_text("pickle content")
        npy_file.write_text("npy content")

        raw_data = {
            "teensy_path": {
                "filename": "test_session.pickle",
                "dst": str(session_dir),
                "src": "/remote/path",
            }
        }
        # Transformer must have exp_teensy_filepath since the function
        # internally changes key from exp_session_filepath to exp_teensy_filepath
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_session_filepath",  # This key triggers .npy lookup
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),
            move=False,
        )

        # Should look for .npy file (stem + .npy)
        assert result is not False
        assert ".npy" in str(result)

    def test_get_path_handles_windows_paths(self, mock_file_info):
        """get_path should handle Windows-style path separators."""
        data_subdir = mock_file_info["data_dir"] / "win_test"
        data_subdir.mkdir(exist_ok=True)
        test_file = data_subdir / "win_file.pickle"
        test_file.write_text("windows content")

        raw_data = {
            "teensy_path": {
                "filename": "win_file.pickle",
                # Windows-style path with backslashes
                "dst": str(data_subdir).replace("/", "\\"),
                "src": "C:\\remote\\path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),
            move=False,
        )

        # Should handle Windows paths correctly
        assert result is not False

    def test_get_path_handles_double_slashes(self, mock_file_info):
        """get_path should handle paths with double slashes."""
        data_subdir = mock_file_info["data_dir"] / "slash_test"
        data_subdir.mkdir(exist_ok=True)
        test_file = data_subdir / "slash_file.pickle"
        test_file.write_text("slash content")

        raw_data = {
            "teensy_path": {
                "filename": "slash_file.pickle",
                # Path with double slashes
                "dst": str(data_subdir).replace("/", "//"),
                "src": "//remote//path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
            srcf=str(mock_file_info["data_dir"]),
            move=False,
        )

        # Should handle double slashes correctly
        assert result is not False


# ==============================================================================
# Tests for get_remote_path
# ==============================================================================

class TestGetRemotePath:
    """Tests for get_remote_path function - remote file path construction."""

    def test_get_remote_path_constructs_full_path(self):
        """get_remote_path should construct full remote path."""
        raw_data = {
            "teensy_path": {
                "filename": "data.pickle",
                "src": "/remote/source/path",
                "dst": "/local/dest/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_remote_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
        )

        assert result == "/remote/source/path/data.pickle"

    def test_get_remote_path_returns_none_for_empty_src(self):
        """get_remote_path should return None when src is empty."""
        raw_data = {
            "teensy_path": {
                "filename": "data.pickle",
                "src": "",  # Empty source
                "dst": "/local/dest/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_remote_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
        )

        assert result is None

    def test_get_remote_path_returns_none_for_none_src(self):
        """get_remote_path should return None when src is None."""
        raw_data = {
            "teensy_path": {
                "filename": "data.pickle",
                "src": None,  # None source
                "dst": "/local/dest/path",
            }
        }
        transformer = {"exp_teensy_filepath": "teensy_path"}

        result = get_remote_path(
            raw_data=raw_data,
            key="exp_teensy_filepath",
            transformer=transformer,
        )

        assert result is None

    def test_get_remote_path_uses_transformer_mapping(self):
        """get_remote_path should use transformer to map key to raw_data key."""
        raw_data = {
            "dlc_path": {
                "filename": "keypoints.hdf5",
                "src": "/remote/dlc/path",
                "dst": "/local/dlc/path",
            }
        }
        transformer = {"keypoints_filepath": "dlc_path"}

        result = get_remote_path(
            raw_data=raw_data,
            key="keypoints_filepath",
            transformer=transformer,
        )

        assert result == "/remote/dlc/path/keypoints.hdf5"

    def test_get_remote_path_handles_complex_paths(self):
        """get_remote_path should handle complex nested paths."""
        raw_data = {
            "video_path": {
                "filename": "session_video.avi",
                "src": "/mnt/storage/lab/experiments/2024/videos",
                "dst": "/tmp/local",
            }
        }
        transformer = {"video_filepath": "video_path"}

        result = get_remote_path(
            raw_data=raw_data,
            key="video_filepath",
            transformer=transformer,
        )

        assert result == "/mnt/storage/lab/experiments/2024/videos/session_video.avi"


# ==============================================================================
# Tests for additional utility functions (previously uncovered)
# ==============================================================================

class TestAdditionalUtilityFunctions:
    """Tests for utility functions that were previously uncovered."""

    def test_no_value_opto_returns_expected_list(self):
        """no_value_opto should return list with none/-1 values."""
        result = no_value_opto()
        assert result == ["none", -1, -1, -1, "none", "none", "none"]
        assert len(result) == 7

    def test_no_joystick_returns_none_string(self):
        """no_joystick should return 'none' string."""
        result = no_joystick()
        assert result == "none"

    def test_no_force_field_returns_none_string(self):
        """no_force_field should return 'none' string."""
        result = no_force_field()
        assert result == "none"


# ==============================================================================
# Tests for edge cases in get_state
# ==============================================================================

class TestGetStateEdgeCases:
    """Tests for edge cases in get_state function."""

    def test_get_state_short_state_array(self):
        """get_state should handle state arrays shorter than expected index."""
        # Create state with fewer columns than expected
        short_state = np.array([[1.0, 2.0, 3.0]])  # Only 3 columns
        raw_data = {"state": short_state}

        # Velocity is at index 9, which doesn't exist
        result = get_state(raw_data=raw_data, key="velocity")

        # Should return None for that index
        assert result is not None
        assert result[0] is None


# ==============================================================================
# Note: Tests with specific real data values (e.g., 339045 steps) are in
# tests/integration/ where they use real golden dataset files.
# ==============================================================================
