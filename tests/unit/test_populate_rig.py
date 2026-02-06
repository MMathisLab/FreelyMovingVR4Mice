"""
Unit tests for populate_rig.py

Tests the pure/semi-pure functions used for file discovery and data loading
during database population. Database-dependent functions (populate, populate_rig)
are tested separately in integration tests.

NOTE: These tests use temporary files and synthetic data - no real file I/O
to external datasets required. Tests that require real data files are in
tests/integration/.

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
    populate,
    populate_rig,
)
from unittest.mock import MagicMock, patch


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

    def test_get_new_file_with_mock_pickle(self, tmp_path, mock_pickle_data):
        """Should load a pickle file with mock data structure."""
        # Write mock pickle data to temp file
        pickle_path = tmp_path / "MockMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(mock_pickle_data, f)

        data, name = get_new_file("MockMouse_2024-01-01_1.pickle", str(tmp_path))

        assert name == "MockMouse_2024-01-01_1"
        assert isinstance(data, dict)
        assert "state" in data
        assert data["state"].shape[1] == 13  # 13 state columns


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
# Tests with mock pickle data
# ==============================================================================

class TestWithMockData:
    """Tests using mock synthetic data."""

    def test_get_new_file_mock_pickle_keys(self, tmp_path, mock_pickle_data):
        """Mock pickle should have expected keys."""
        # Write mock data to temp file
        pickle_path = tmp_path / "MockMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(mock_pickle_data, f)

        data, name = get_new_file("MockMouse_2024-01-01_1.pickle", str(tmp_path))

        expected_keys = ["state", "episode", "step", "action", "reward"]
        for key in expected_keys:
            assert key in data, f"Missing key: {key}"

    def test_get_new_file_mock_pickle_state_shape(self, tmp_path, mock_pickle_data):
        """Mock pickle state array should have expected structure."""
        # Write mock data to temp file
        pickle_path = tmp_path / "MockMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(mock_pickle_data, f)

        data, name = get_new_file("MockMouse_2024-01-01_1.pickle", str(tmp_path))

        # Mock data has shape (1000, 13)
        assert data["state"].shape == (1000, 13)

    def test_parse_date_dataset_name_format(self):
        """Should parse date from standard dataset name format."""
        result = parse_date("Nightingale_2024-08-16_1")

        assert result == datetime(2024, 8, 16)


# ==============================================================================
# Tests for check_keys edge cases
# ==============================================================================

class TestCheckKeysEdgeCases:
    """Tests for edge cases in check_keys function."""

    def test_check_keys_transformer_found_after_flagged_missing(self):
        """Test when a key is found via transformer after being flagged missing.

        This tests lines 135-137 where a key is removed from none_vals
        when found through a transformer.
        """
        raw_data = {"source_key": "value"}
        schema = {
            "local_def": {},
            "transformer": {"target_key": "source_key"}
        }

        # Call with a key that will be found via transformer
        result, none_vals = check_keys(
            ["target_key"], raw_data, "test_table", schema, none=True
        )

        assert result is True
        # Key should NOT be in none_vals since it was found via transformer
        assert "target_key" not in none_vals

    def test_check_keys_multiple_transformers(self):
        """Test with multiple keys, some transformable, some not."""
        raw_data = {
            "source1": "value1",
            "source2": "value2",
        }
        schema = {
            "local_def": {},
            "transformer": {
                "transformed1": "source1",
                "transformed2": "source2",
                "missing_transform": "nonexistent_source",
            }
        }

        result, none_vals = check_keys(
            ["transformed1", "transformed2", "missing_transform"],
            raw_data, "test_table", schema, none=True
        )

        assert result is True
        assert "transformed1" not in none_vals
        assert "transformed2" not in none_vals
        assert "missing_transform" in none_vals


# ==============================================================================
# Tests for populate function
# ==============================================================================

class TestPopulate:
    """Tests for populate function - inserts data into database tables.

    These tests mock the database tables to test the data transformation
    and insertion logic without requiring a real database connection.
    """

    @pytest.fixture
    def mock_table(self):
        """Create a mock database table."""
        table = MagicMock()
        table.insert1 = MagicMock()
        return table

    @pytest.fixture
    def simple_schema(self, mock_table):
        """Create a simple schema with mock table and no transformations."""
        return {
            "dj_tables": {"TestTable": mock_table},
            "local_def": {},
            "transformer": {},
        }

    def test_populate_inserts_data_from_raw_data(self, simple_schema, mock_table):
        """populate should insert data from raw_data into table."""
        raw_data = {"attr1": "value1", "attr2": "value2"}
        attributes = ["attr1", "attr2"]

        populate("TestTable", attributes, raw_data, simple_schema)

        mock_table.insert1.assert_called_once()
        inserted_data = mock_table.insert1.call_args[0][0]
        assert inserted_data["attr1"] == "value1"
        assert inserted_data["attr2"] == "value2"

    def test_populate_uses_local_def_function(self, mock_table):
        """populate should use local_def functions to generate values."""
        def custom_generator(raw_data=None, key=None, **kwargs):
            return f"generated_{key}"

        schema = {
            "dj_tables": {"TestTable": mock_table},
            "local_def": {"custom_attr": custom_generator},
            "transformer": {},
        }
        raw_data = {"other_attr": "value"}
        attributes = ["other_attr", "custom_attr"]

        populate("TestTable", attributes, raw_data, schema)

        mock_table.insert1.assert_called_once()
        inserted_data = mock_table.insert1.call_args[0][0]
        assert inserted_data["custom_attr"] == "generated_custom_attr"
        assert inserted_data["other_attr"] == "value"

    def test_populate_uses_transformer_mapping(self, mock_table):
        """populate should use transformer to map attribute names."""
        schema = {
            "dj_tables": {"TestTable": mock_table},
            "local_def": {},
            "transformer": {"db_attr": "raw_attr"},
        }
        raw_data = {"raw_attr": "raw_value"}
        attributes = ["db_attr"]

        populate("TestTable", attributes, raw_data, schema)

        mock_table.insert1.assert_called_once()
        inserted_data = mock_table.insert1.call_args[0][0]
        assert inserted_data["db_attr"] == "raw_value"

    def test_populate_skips_duplicates(self, simple_schema, mock_table):
        """populate should pass skip_duplicates=True to insert1."""
        raw_data = {"attr1": "value1"}
        attributes = ["attr1"]

        populate("TestTable", attributes, raw_data, simple_schema)

        # Check that skip_duplicates=True was passed
        call_kwargs = mock_table.insert1.call_args[1]
        assert call_kwargs.get("skip_duplicates") is True

    def test_populate_with_numpy_array(self, simple_schema, mock_table):
        """populate should handle numpy arrays in raw_data."""
        raw_data = {
            "scalar": 42,
            "array": np.array([1, 2, 3, 4, 5]),
            "matrix": np.zeros((10, 5)),
        }
        attributes = ["scalar", "array", "matrix"]

        populate("TestTable", attributes, raw_data, simple_schema)

        mock_table.insert1.assert_called_once()
        inserted_data = mock_table.insert1.call_args[0][0]
        assert inserted_data["scalar"] == 42
        assert np.array_equal(inserted_data["array"], np.array([1, 2, 3, 4, 5]))
        assert inserted_data["matrix"].shape == (10, 5)

    def test_populate_local_def_receives_all_parameters(self, mock_table):
        """local_def function should receive raw_data, key, transformer, srcf, dstf, move."""
        received_params = {}

        def capture_params(**kwargs):
            received_params.update(kwargs)
            return "captured"

        schema = {
            "dj_tables": {"TestTable": mock_table},
            "local_def": {"test_attr": capture_params},
            "transformer": {"some": "mapping"},
        }
        raw_data = {"data_key": "data_value"}
        attributes = ["test_attr"]

        populate("TestTable", attributes, raw_data, schema)

        assert "raw_data" in received_params
        assert "key" in received_params
        assert "transformer" in received_params
        assert received_params["key"] == "test_attr"
        assert received_params["raw_data"] == raw_data


# ==============================================================================
# Tests for populate_rig function
# ==============================================================================

class TestPopulateRig:
    """Tests for populate_rig function - main workflow orchestration.

    These tests mock file operations and database calls to test the
    workflow logic without requiring real files or database connection.
    """

    @pytest.fixture
    def mock_dj_schema(self):
        """Mock the dj_schema module."""
        mock_schema = MagicMock()
        mock_schema.vr4mice.Dataset.return_value.fetch.return_value = []
        return mock_schema

    @pytest.fixture
    def sample_pickle_data(self):
        """Create minimal valid pickle data structure."""
        return {
            "state": np.random.rand(100, 13).astype(np.float32),
            "episode": np.arange(100, dtype=np.int32),
            "step": np.arange(100, dtype=np.int32),
            "step_time": np.linspace(0, 10, 100),
            "session_label": ["test_session"],
            "start_time": "2024-01-01_12-00-00",
        }

    def test_populate_rig_finds_pickle_files(self, tmp_path, sample_pickle_data):
        """populate_rig should discover and process pickle files."""
        # Create test pickle file
        pickle_path = tmp_path / "TestMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(sample_pickle_data, f)

        # Mock the schema and populate to isolate file discovery logic
        with patch("populate_rig.dj_schema") as mock_schema:
            # Simulate dataset not in database
            mock_schema.vr4mice.Dataset.return_value.__and__.return_value.fetch.return_value = []

            # Mock vr4mice schema to prevent actual population
            with patch("populate_rig.vr4mice", {"tables": {}}):
                with patch("populate_rig.base", {"tables": {}}):
                    # This should not raise an error - it processes the file
                    populate_rig(path=str(tmp_path), gui="false")

    def test_populate_rig_skips_existing_dataset(self, tmp_path, sample_pickle_data):
        """populate_rig should skip datasets already in database."""
        # Create test pickle file
        pickle_path = tmp_path / "ExistingMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(sample_pickle_data, f)

        with patch("populate_rig.dj_schema") as mock_schema:
            # Simulate dataset ALREADY in database
            mock_schema.vr4mice.Dataset.return_value.__and__.return_value.fetch.return_value = [
                {"dataset": "ExistingMouse_2024-01-01_1"}
            ]

            # Run should complete without populating
            populate_rig(path=str(tmp_path), gui="false")

            # Dataset.fetch should have been called to check existence
            mock_schema.vr4mice.Dataset.return_value.__and__.return_value.fetch.assert_called()

    def test_populate_rig_handles_empty_directory(self, tmp_path):
        """populate_rig should handle empty directories gracefully."""
        # Empty directory - no pickle files
        with patch("populate_rig.dj_schema"):
            # Should not raise an error
            populate_rig(path=str(tmp_path), gui="false")

    def test_populate_rig_gui_mode_requires_npy(self, tmp_path, sample_pickle_data):
        """populate_rig in GUI mode should require .npy files."""
        # Create only pickle file, no npy
        pickle_path = tmp_path / "TestMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(sample_pickle_data, f)

        with patch("populate_rig.dj_schema") as mock_schema:
            mock_schema.vr4mice.Dataset.return_value.__and__.return_value.fetch.return_value = []

            # In GUI mode, should return None when npy is missing (early return)
            with patch.dict(os.environ, {"GUI": "true"}):
                result = populate_rig(path=str(tmp_path), gui="true")
                assert result is None

    def test_populate_rig_processes_npy_only(self, tmp_path):
        """populate_rig should process .npy files when no pickle files exist."""
        # Create test npy file (dict saved as npy)
        npy_data = {
            "state": np.random.rand(100, 13).astype(np.float32),
            "episode": np.arange(100, dtype=np.int32),
            "rig_id": 12,
            "license": "N/A",
        }
        npy_path = tmp_path / "TestMouse_2024-01-01_1.npy"
        np.save(str(npy_path), npy_data)

        with patch("populate_rig.dj_schema") as mock_schema:
            with patch("populate_rig.base", {"tables": {}}):
                # Should process npy file
                populate_rig(path=str(tmp_path), gui="false")

    def test_populate_rig_generates_file_paths_without_gui(self, tmp_path, sample_pickle_data):
        """populate_rig should generate file paths when GUI npy is missing."""
        # Create pickle file without corresponding npy
        pickle_path = tmp_path / "NoGuiMouse_2024-01-01_1.pickle"
        with open(pickle_path, "wb") as f:
            pickle.dump(sample_pickle_data, f)

        with patch("populate_rig.dj_schema") as mock_schema:
            mock_schema.vr4mice.Dataset.return_value.__and__.return_value.fetch.return_value = []

            # Mock vr4mice to verify it receives generated file paths
            with patch("populate_rig.vr4mice") as mock_vr4mice:
                mock_vr4mice.__getitem__ = MagicMock(return_value={})
                mock_vr4mice.get = MagicMock(return_value={})

                populate_rig(path=str(tmp_path), gui="false")

    def test_populate_rig_handles_exception_gracefully(self, tmp_path):
        """populate_rig should catch and log exceptions during processing."""
        # Create a malformed pickle file that will cause an error
        bad_pickle_path = tmp_path / "BadFile_2024-01-01_1.pickle"
        bad_pickle_path.write_text("not a valid pickle")

        with patch("populate_rig.dj_schema"):
            # Should not raise - should catch and log the error
            populate_rig(path=str(tmp_path), gui="false")


# ==============================================================================
# Note: Tests that require real test data files (e.g., verifying 339045 rows)
# are in tests/integration/ where they use the golden dataset.
# ==============================================================================
