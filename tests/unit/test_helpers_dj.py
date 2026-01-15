"""
Unit tests for helpers_dj.py

Tests the helper functions used for data transformation during
database population, particularly state array extraction and
path handling.

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
)


# ==============================================================================
# Tests for get_state
# ==============================================================================

class TestGetState:
    """Tests for get_state function - extracts values from state array."""

    def test_get_state_x_pos(self, pickle_data, state_index_map):
        """Should extract x_pos (index 0) from state array."""
        result = get_state(raw_data=pickle_data, key="x_pos")
        assert result is not None
        assert len(result) == len(pickle_data["state"])
        # First value should match state[0][0]
        assert result[0] == pickle_data["state"][0][state_index_map["x_pos"]]

    def test_get_state_z_pos(self, pickle_data, state_index_map):
        """Should extract z_pos (index 1) from state array."""
        result = get_state(raw_data=pickle_data, key="z_pos")
        assert result is not None
        assert len(result) == len(pickle_data["state"])
        assert result[0] == pickle_data["state"][0][state_index_map["z_pos"]]

    def test_get_state_head_dir(self, pickle_data, state_index_map):
        """Should extract head_dir (index 2) from state array."""
        result = get_state(raw_data=pickle_data, key="head_dir")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["head_dir"]]

    def test_get_state_mouse_can_report(self, pickle_data, state_index_map):
        """Should extract mouse_can_report (index 3) from state array."""
        result = get_state(raw_data=pickle_data, key="mouse_can_report")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["mouse_can_report"]]

    def test_get_state_iti(self, pickle_data, state_index_map):
        """Should extract iti (index 4) from state array."""
        result = get_state(raw_data=pickle_data, key="iti")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["iti"]]

    def test_get_state_obj_left(self, pickle_data, state_index_map):
        """Should extract obj_left (index 5) from state array."""
        result = get_state(raw_data=pickle_data, key="obj_left")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["obj_left"]]

    def test_get_state_mouse_report_correct(self, pickle_data, state_index_map):
        """Should extract mouse_report_correct (index 6) from state array."""
        result = get_state(raw_data=pickle_data, key="mouse_report_correct")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["mouse_report_correct"]]

    def test_get_state_report_left(self, pickle_data, state_index_map):
        """Should extract report_left (index 7) from state array."""
        result = get_state(raw_data=pickle_data, key="report_left")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["report_left"]]

    def test_get_state_report_right(self, pickle_data, state_index_map):
        """Should extract report_right (index 8) from state array."""
        result = get_state(raw_data=pickle_data, key="report_right")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["report_right"]]

    def test_get_state_velocity(self, pickle_data, state_index_map):
        """Should extract velocity (index 9) from state array."""
        result = get_state(raw_data=pickle_data, key="velocity")
        assert result is not None
        assert result[0] == pickle_data["state"][0][state_index_map["velocity"]]

    def test_get_state_invalid_key(self, pickle_data):
        """Invalid key should return None."""
        result = get_state(raw_data=pickle_data, key="invalid_key")
        assert result is None

    def test_get_state_none_raw_data(self):
        """None raw_data should return None."""
        result = get_state(raw_data=None, key="x_pos")
        assert result is None

    def test_get_state_none_key(self, pickle_data):
        """None key should return None."""
        result = get_state(raw_data=pickle_data, key=None)
        assert result is None

    def test_get_state_all_keys_extract_correctly(self, pickle_data, state_index_map):
        """All state keys should extract to correct length arrays."""
        for key in state_index_map.keys():
            result = get_state(raw_data=pickle_data, key=key)
            assert result is not None, f"Key {key} returned None"
            assert len(result) == len(pickle_data["state"]), \
                f"Key {key} length mismatch"

    def test_get_state_values_match_direct_access(self, pickle_data, state_index_map):
        """Extracted values should match direct array indexing."""
        for key, idx in state_index_map.items():
            result = get_state(raw_data=pickle_data, key=key)
            # Check first few values
            for i in range(min(10, len(result))):
                expected = pickle_data["state"][i][idx]
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
    def test_get_box_old_style_returns_entire_array(self, pickle_data):
        """Old style: transformer mapping to existing key returns whole array."""
        transformer = {"l_box_x_min": "l_report_box"}
        result = get_box(raw_data=pickle_data, key="l_box_x_min", transformer=transformer)
        # Old style returns the entire array
        assert np.array_equal(result, pickle_data["l_report_box"])

    def test_get_box_old_style_r_report_box(self, pickle_data):
        """Old style: r_report_box returns whole array."""
        transformer = {"r_box_x_min": "r_report_box"}
        result = get_box(raw_data=pickle_data, key="r_box_x_min", transformer=transformer)
        assert np.array_equal(result, pickle_data["r_report_box"])

    def test_get_box_old_style_start_box(self, pickle_data):
        """Old style: start_box returns whole array."""
        transformer = {"tt_box_x_min": "start_box"}
        result = get_box(raw_data=pickle_data, key="tt_box_x_min", transformer=transformer)
        assert np.array_equal(result, pickle_data["start_box"])

    # New style tests - transformer maps to non-existent key, uses internal mapping
    def test_get_box_new_style_l_box_x_min(self, pickle_data):
        """New style: extracts l_box_x_min (index 0) from l_report_box."""
        # Map to a key that doesn't exist in raw_data to trigger new style
        transformer = {"l_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="l_box_x_min", transformer=transformer)
        assert result == pickle_data["l_report_box"][0]

    def test_get_box_new_style_l_box_x_max(self, pickle_data):
        """New style: extracts l_box_x_max (index 1) from l_report_box."""
        transformer = {"l_box_x_max": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="l_box_x_max", transformer=transformer)
        assert result == pickle_data["l_report_box"][1]

    def test_get_box_new_style_l_box_z_min(self, pickle_data):
        """New style: extracts l_box_z_min (index 2) from l_report_box."""
        transformer = {"l_box_z_min": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="l_box_z_min", transformer=transformer)
        assert result == pickle_data["l_report_box"][2]

    def test_get_box_new_style_l_box_z_max(self, pickle_data):
        """New style: extracts l_box_z_max (index 3) from l_report_box."""
        transformer = {"l_box_z_max": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="l_box_z_max", transformer=transformer)
        assert result == pickle_data["l_report_box"][3]

    def test_get_box_new_style_r_box_x_min(self, pickle_data):
        """New style: extracts r_box_x_min (index 0) from r_report_box."""
        transformer = {"r_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="r_box_x_min", transformer=transformer)
        assert result == pickle_data["r_report_box"][0]

    def test_get_box_new_style_tt_box_x_min(self, pickle_data):
        """New style: extracts tt_box_x_min (index 0) from start_box."""
        transformer = {"tt_box_x_min": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="tt_box_x_min", transformer=transformer)
        assert result == pickle_data["start_box"][0]

    def test_get_box_new_style_tt_box_angle(self, pickle_data):
        """New style: extracts tt_box_angle (index 4) from start_box."""
        transformer = {"tt_box_angle": "nonexistent_key"}
        result = get_box(raw_data=pickle_data, key="tt_box_angle", transformer=transformer)
        assert result == pickle_data["start_box"][4]


# ==============================================================================
# Tests for get_camera
# ==============================================================================

class TestGetCamera:
    """Tests for get_camera function - extracts camera name from filename."""

    def test_get_camera_from_dlc_path(self, json_metadata):
        """Should extract camera name from DLC filename."""
        # The DLC filename is: Imagingsource_Nightingale_2024-08-16_1_DLC.hdf5
        raw_data = {"dlc_path": json_metadata["dlc_path"]}
        result = get_camera(raw_data=raw_data)
        assert result == "Imagingsource"

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

    def test_get_model_name_from_dlc_path(self, json_metadata):
        """Should extract model name from DLC filename."""
        # The DLC filename is: Imagingsource_Nightingale_2024-08-16_1_DLC.hdf5
        raw_data = {"dlc_path": json_metadata["dlc_path"]}
        result = get_model_name(raw_data=raw_data)
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

    def test_get_video_meta_duration(self, json_metadata):
        """Should extract video duration."""
        result = get_video_meta(raw_data=json_metadata, key="duration")
        assert result == json_metadata["video_meta"]["duration"]
        assert result == 4559.65

    def test_get_video_meta_fps(self, json_metadata):
        """Should extract video FPS."""
        result = get_video_meta(raw_data=json_metadata, key="fps")
        assert result == json_metadata["video_meta"]["fps"]
        assert result == 100.0

    def test_get_video_meta_width(self, json_metadata):
        """Should extract video width."""
        result = get_video_meta(raw_data=json_metadata, key="width")
        assert result == json_metadata["video_meta"]["width"]
        assert result == 530

    def test_get_video_meta_height(self, json_metadata):
        """Should extract video height."""
        result = get_video_meta(raw_data=json_metadata, key="height")
        assert result == json_metadata["video_meta"]["height"]
        assert result == 510


# ==============================================================================
# Tests for get_name
# ==============================================================================

class TestGetName:
    """Tests for get_name function - extracts session label."""

    def test_get_name_from_list(self, pickle_data):
        """Should extract first element from list."""
        result = get_name(raw_data=pickle_data, key="session_label")
        assert result == pickle_data["session_label"][0]
        assert result == "ar_discrim_5_occluders"

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
# Tests for state extraction with real data shapes
# ==============================================================================

class TestStateExtractionShapes:
    """Tests verifying extracted state arrays have correct shapes."""

    def test_extracted_x_pos_shape(self, pickle_data):
        """Extracted x_pos should have shape (339045,)."""
        result = get_state(raw_data=pickle_data, key="x_pos")
        assert len(result) == 339045

    def test_extracted_z_pos_shape(self, pickle_data):
        """Extracted z_pos should have shape (339045,)."""
        result = get_state(raw_data=pickle_data, key="z_pos")
        assert len(result) == 339045

    def test_extracted_velocity_shape(self, pickle_data):
        """Extracted velocity should have shape (339045,)."""
        result = get_state(raw_data=pickle_data, key="velocity")
        assert len(result) == 339045

    def test_all_state_extractions_same_length(self, pickle_data, state_index_map):
        """All extracted state arrays should have same length."""
        lengths = set()
        for key in state_index_map.keys():
            result = get_state(raw_data=pickle_data, key=key)
            lengths.add(len(result))
        assert len(lengths) == 1, f"Different lengths found: {lengths}"
        assert 339045 in lengths
