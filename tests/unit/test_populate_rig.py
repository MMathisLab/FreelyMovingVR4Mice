"""
Unit tests for populate_rig.py

Tests the pure/semi-pure functions used for file discovery and data loading
during database population. Database-dependent functions (populate, populate_rig)
are tested separately in integration tests.

Note: Database-dependent modules are mocked in conftest.py to allow
testing without DataJoint connection.
"""

import os
import pickle
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

# Import from populate_rig (mocks configured in conftest.py)
from populate_rig import (
    get_filenames,
    get_new_file,
    parse_date,
    get_files_paths,
    check_keys,
)


# ==============================================================================
# Tests for get_filenames
# ==============================================================================

class TestGetFilenames:
    """Tests for get_filenames function - discovers files by extension."""

    def test_get_filenames_returns_dict(self, tmp_path):
        """Should return a dictionary."""
        result = get_filenames([".txt"], str(tmp_path))
        assert isinstance(result, dict)

    def test_get_filenames_empty_dir_returns_empty_dict(self, tmp_path):
        """Empty directory should return empty dict."""
        result = get_filenames([".txt"], str(tmp_path))
        assert result == {}

    def test_get_filenames_finds_pickle_files(self, tmp_path):
        """Should find .pickle files."""
        # Create test files
        (tmp_path / "test1.pickle").touch()
        (tmp_path / "test2.pickle").touch()

        result = get_filenames([".pickle"], str(tmp_path))

        assert ".pickle" in result
        assert len(result[".pickle"]) == 2
        assert "test1.pickle" in result[".pickle"]
        assert "test2.pickle" in result[".pickle"]

    def test_get_filenames_finds_npy_files(self, tmp_path):
        """Should find .npy files."""
        (tmp_path / "data1.npy").touch()
        (tmp_path / "data2.npy").touch()

        result = get_filenames([".npy"], str(tmp_path))

        assert ".npy" in result
        assert len(result[".npy"]) == 2

    def test_get_filenames_multiple_extensions(self, tmp_path):
        """Should handle multiple extensions."""
        (tmp_path / "test.pickle").touch()
        (tmp_path / "test.npy").touch()
        (tmp_path / "test.json").touch()

        result = get_filenames([".pickle", ".npy"], str(tmp_path))

        assert ".pickle" in result
        assert ".npy" in result
        assert ".json" not in result

    def test_get_filenames_ignores_other_extensions(self, tmp_path):
        """Should ignore files with non-matching extensions."""
        (tmp_path / "test.pickle").touch()
        (tmp_path / "test.txt").touch()
        (tmp_path / "test.csv").touch()

        result = get_filenames([".pickle"], str(tmp_path))

        assert ".pickle" in result
        assert ".txt" not in result
        assert ".csv" not in result

    def test_get_filenames_sorted_order(self, tmp_path):
        """Should return files in sorted order."""
        (tmp_path / "c_file.pickle").touch()
        (tmp_path / "a_file.pickle").touch()
        (tmp_path / "b_file.pickle").touch()

        result = get_filenames([".pickle"], str(tmp_path))

        assert result[".pickle"] == ["a_file.pickle", "b_file.pickle", "c_file.pickle"]


# ==============================================================================
# Tests for get_new_file
# ==============================================================================

class TestGetNewFile:
    """Tests for get_new_file function - loads data from files."""

    def test_get_new_file_loads_pickle(self, tmp_path):
        """Should load .pickle files."""
        # Create test pickle file
        test_data = {"key1": "value1", "key2": [1, 2, 3]}
        pickle_path = tmp_path / "test.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(test_data, f)

        data, name = get_new_file("test.pickle", str(tmp_path))

        assert name == "test"
        assert data == test_data

    def test_get_new_file_loads_npy(self, tmp_path):
        """Should load .npy files with allow_pickle=True."""
        # Create test npy file with dict
        test_data = {"array": np.array([1, 2, 3]), "value": 42}
        npy_path = tmp_path / "test.npy"
        np.save(str(npy_path), test_data)

        data, name = get_new_file("test.npy", str(tmp_path))

        assert name == "test"
        assert "array" in data
        assert "value" in data

    def test_get_new_file_returns_name_without_extension(self, tmp_path):
        """Should return filename without extension."""
        test_data = {}
        pickle_path = tmp_path / "Mouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(test_data, f)

        data, name = get_new_file("Mouse_2024-01-01_1.pickle", str(tmp_path))

        assert name == "Mouse_2024-01-01_1"

    def test_get_new_file_with_real_pickle(self, pickle_path):
        """Should load real test pickle file."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        assert name == "Nightingale_2024-08-16_1"
        assert isinstance(data, dict)
        assert "state" in data


# ==============================================================================
# Tests for parse_date
# ==============================================================================

class TestParseDate:
    """Tests for parse_date function - extracts date from filename."""

    def test_parse_date_extracts_date(self):
        """Should extract date from filename."""
        result = parse_date("Mouse_2024-08-16_1")

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 8
        assert result.day == 16

    def test_parse_date_different_formats(self):
        """Should work with various filename formats."""
        test_cases = [
            ("Nightingale_2024-08-16_1", datetime(2024, 8, 16)),
            ("data_2023-01-01_experiment", datetime(2023, 1, 1)),
            ("2022-12-31_file", datetime(2022, 12, 31)),
            ("prefix_2021-06-15_suffix_extra", datetime(2021, 6, 15)),
        ]

        for filename, expected in test_cases:
            result = parse_date(filename)
            assert result == expected, f"Failed for {filename}"

    def test_parse_date_no_date_returns_none(self):
        """Should return None if no date pattern found."""
        result = parse_date("no_date_here")
        assert result is None

    def test_parse_date_invalid_date_format(self):
        """Should return None for invalid date format."""
        result = parse_date("file_16-08-2024")  # DD-MM-YYYY format
        assert result is None

    def test_parse_date_partial_date(self):
        """Should return None for partial date patterns."""
        result = parse_date("file_2024-08")  # Missing day
        assert result is None

    def test_parse_date_first_match(self):
        """Should return first date match if multiple dates present."""
        result = parse_date("2023-01-01_to_2023-12-31")

        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1


# ==============================================================================
# Tests for get_files_paths
# ==============================================================================

class TestGetFilesPaths:
    """Tests for get_files_paths function - generates file paths dictionary."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Set up environment variable for tests."""
        monkeypatch.setenv("IMG_SRC", "Imagingsource")

    def test_get_files_paths_returns_dict(self, mock_env):
        """Should return a dictionary."""
        result = get_files_paths("Mouse_2024-01-01_1")
        assert isinstance(result, dict)

    def test_get_files_paths_has_required_keys(self, mock_env):
        """Should have all required path keys."""
        result = get_files_paths("Mouse_2024-01-01_1")

        required_keys = [
            "teensy_path", "dlc_path", "camera_path", "video_path",
            "proc_path", "gui_output", "video_meta", "time_stamp",
            "doe", "dataset"
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_get_files_paths_dataset_value(self, mock_env):
        """Should store dataset name."""
        result = get_files_paths("Nightingale_2024-08-16_1")
        assert result["dataset"] == "Nightingale_2024-08-16_1"

    def test_get_files_paths_doe_parsed(self, mock_env):
        """Should parse date of experiment."""
        result = get_files_paths("Nightingale_2024-08-16_1")

        assert result["doe"] is not None
        assert result["doe"].year == 2024
        assert result["doe"].month == 8
        assert result["doe"].day == 16

    def test_get_files_paths_teensy_path_structure(self, mock_env):
        """Should have correct teensy_path structure."""
        result = get_files_paths("Mouse_2024-01-01_1")

        assert "filename" in result["teensy_path"]
        assert "src" in result["teensy_path"]
        assert "dst" in result["teensy_path"]
        assert result["teensy_path"]["filename"] == "Mouse_2024-01-01_1.pickle"

    def test_get_files_paths_dlc_path_uses_img_src(self, mock_env):
        """Should use IMG_SRC env var in DLC filename."""
        result = get_files_paths("Mouse_2024-01-01_1")

        assert "Imagingsource" in result["dlc_path"]["filename"]
        assert result["dlc_path"]["filename"] == "Imagingsource_Mouse_2024-01-01_1_DLC.hdf5"

    def test_get_files_paths_camera_path_filename(self, mock_env):
        """Should generate correct camera timestamp filename."""
        result = get_files_paths("Mouse_2024-01-01_1")

        assert result["camera_path"]["filename"] == "Imagingsource_Mouse_2024-01-01_1_TS.npy"

    def test_get_files_paths_video_meta_structure(self, mock_env):
        """Should have video_meta with None values initially."""
        result = get_files_paths("Mouse_2024-01-01_1")

        assert result["video_meta"]["duration"] is None
        assert result["video_meta"]["fps"] is None
        assert result["video_meta"]["width"] is None
        assert result["video_meta"]["height"] is None

    def test_get_files_paths_custom_paths(self, mock_env):
        """Should use custom local_src and data paths."""
        result = get_files_paths(
            "Mouse_2024-01-01_1",
            local_src="/custom/path",
            data="/custom/data"
        )

        assert "/custom/path" in result["teensy_path"]["dst"]


# ==============================================================================
# Tests for check_keys
# ==============================================================================

class TestCheckKeys:
    """Tests for check_keys function - validates schema keys."""

    def test_check_keys_all_present_returns_true(self):
        """Should return True when all keys are present in raw_data."""
        raw_data = {"key1": "value1", "key2": "value2"}
        schema = {"local_def": {}, "transformer": {}}

        result, none_vals = check_keys(["key1", "key2"], raw_data, "test_table", schema)

        assert result is True

    def test_check_keys_missing_key_with_none_true(self):
        """Should return True with none_vals when key missing and none=True."""
        raw_data = {"key1": "value1"}
        schema = {"local_def": {}, "transformer": {}}

        result, none_vals = check_keys(
            ["key1", "missing_key"], raw_data, "test_table", schema, none=True
        )

        assert result is True
        assert "missing_key" in none_vals
        assert none_vals["missing_key"] is None

    def test_check_keys_missing_key_with_none_false(self):
        """Should return False when key missing and none=False."""
        raw_data = {"key1": "value1"}
        schema = {"local_def": {}, "transformer": {}}

        result, none_vals = check_keys(
            ["key1", "missing_key"], raw_data, "test_table", schema, none=False
        )

        assert result is False

    def test_check_keys_local_def_key(self):
        """Should accept keys defined in local_def."""
        raw_data = {"key1": "value1"}
        schema = {
            "local_def": {"key2": lambda: "generated"},
            "transformer": {}
        }

        result, none_vals = check_keys(["key1", "key2"], raw_data, "test_table", schema)

        assert result is True
        assert "key2" not in none_vals

    def test_check_keys_transformer_key(self):
        """Should accept keys that can be transformed from raw_data."""
        raw_data = {"original_key": "value"}
        schema = {
            "local_def": {},
            "transformer": {"transformed_key": "original_key"}
        }

        result, none_vals = check_keys(
            ["transformed_key"], raw_data, "test_table", schema
        )

        assert result is True

    def test_check_keys_empty_values_list(self):
        """Should return True for empty values list."""
        raw_data = {"key1": "value1"}
        schema = {"local_def": {}, "transformer": {}}

        result, none_vals = check_keys([], raw_data, "test_table", schema)

        assert result is True
        assert none_vals == {}


# ==============================================================================
# Tests with real test data
# ==============================================================================

class TestWithRealData:
    """Tests using the real test dataset."""

    def test_get_new_file_real_pickle_keys(self, pickle_path):
        """Real pickle should have expected keys."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        expected_keys = ["state", "episode", "step", "action", "reward"]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_get_new_file_real_pickle_state_shape(self, pickle_path):
        """Real pickle state array should have expected shape."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        assert data["state"].shape == (339045, 13)

    def test_parse_date_real_dataset(self):
        """Should parse date from real dataset name."""
        result = parse_date("Nightingale_2024-08-16_1")

        assert result == datetime(2024, 8, 16)
