"""
Smoke tests to verify integration test fixtures work correctly.
These tests validate the test infrastructure itself using real golden dataset.

NOTE: These tests require the golden dataset to be available.
Run `git lfs pull` to download test data.
"""

import numpy as np
import pandas as pd


class TestFixturesPaths:
    """Test that path fixtures resolve correctly."""

    def test_test_data_dir_exists(self, test_data_dir):
        """Test data directory should exist."""
        assert test_data_dir.exists()
        assert test_data_dir.is_dir()

    def test_required_files_exist(self, require_golden_data, test_dataset_name, test_camera_prefix):
        """All required golden dataset files should exist."""
        data_dir = require_golden_data

        files_to_check = [
            f"{test_dataset_name}.pickle",
            f"{test_dataset_name}.npy",
            f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5",
            f"{test_camera_prefix}_{test_dataset_name}_TS.npy",
            f"{test_camera_prefix}_{test_dataset_name}_PROC",
        ]

        for filename in files_to_check:
            path = data_dir / filename
            assert path.exists(), f"File not found: {path}"


class TestFixturesDataLoading:
    """Test that data fixtures load correctly."""

    def test_pickle_data_is_dict(self, require_golden_data, integration_pickle_data):
        """Pickle data should be a dict."""
        assert isinstance(integration_pickle_data, dict)

    def test_pickle_data_has_keys(self, require_golden_data, integration_pickle_data, expected_pickle_keys):
        """Pickle data should have expected keys."""
        assert len(integration_pickle_data) == 53
        for key in expected_pickle_keys:
            assert key in integration_pickle_data, f"Missing key: {key}"

    def test_json_metadata_is_dict(self, require_golden_data, integration_json_metadata):
        """JSON metadata should be a dict."""
        assert isinstance(integration_json_metadata, dict)

    def test_json_metadata_has_dataset(self, require_golden_data, integration_json_metadata):
        """JSON should have dataset key."""
        assert "dataset" in integration_json_metadata
        assert integration_json_metadata["dataset"] == "Flamingo_2026-02-05_1"

    def test_dlc_dataframe_is_dataframe(self, require_golden_data, integration_dlc_dataframe):
        """DLC data should be a DataFrame."""
        assert isinstance(integration_dlc_dataframe, pd.DataFrame)

    def test_dlc_dataframe_shape(self, require_golden_data, integration_dlc_dataframe, expected_dlc_shape):
        """DLC DataFrame should have expected shape."""
        assert integration_dlc_dataframe.shape == expected_dlc_shape

    def test_dlc_dataframe_multiindex(self, require_golden_data, integration_dlc_dataframe):
        """DLC DataFrame should have MultiIndex columns."""
        assert isinstance(integration_dlc_dataframe.columns, pd.MultiIndex)
        assert integration_dlc_dataframe.columns.nlevels == 2
        assert integration_dlc_dataframe.columns.names == ["bodyparts", "coords"]

    def test_timestamp_array_is_ndarray(self, require_golden_data, integration_timestamp_array):
        """Timestamp should be a numpy array."""
        assert isinstance(integration_timestamp_array, np.ndarray)

    def test_timestamp_array_shape(self, require_golden_data, integration_timestamp_array):
        """Timestamp array should have expected shape."""
        assert integration_timestamp_array.shape == (202972,)
        assert integration_timestamp_array.dtype == np.float64

    def test_proc_data_is_dict(self, require_golden_data, integration_proc_data):
        """PROC data should be a dict-like object."""
        # PROC data is loaded with allow_pickle=True and may be 0-d array containing dict
        proc = integration_proc_data
        if isinstance(proc, np.ndarray) and proc.ndim == 0:
            proc = proc.item()
        assert isinstance(proc, dict)

    def test_proc_data_has_keys(self, require_golden_data, integration_proc_data):
        """PROC data should have expected keys."""
        proc = integration_proc_data
        if isinstance(proc, np.ndarray) and proc.ndim == 0:
            proc = proc.item()

        expected_keys = [
            "start_time", "frame_time", "time_stamp", "step", "signal",
            "photodiode_read", "photodiode_time", "x_pos", "y_pos",
            "heading_direction", "head_angle"
        ]
        for key in expected_keys:
            assert key in proc, f"Missing key: {key}"


class TestFixturesArrayShapes:
    """Test that array shapes match expected values."""

    def test_state_array_shape(self, require_golden_data, integration_pickle_data, expected_array_shapes):
        """State array should have expected shape."""
        assert integration_pickle_data["state"].shape == expected_array_shapes["state"]

    def test_key_array_shapes(self, require_golden_data, integration_pickle_data, expected_array_shapes):
        """Key arrays should have expected shapes."""
        for key, expected_shape in expected_array_shapes.items():
            if key in integration_pickle_data:
                actual_shape = integration_pickle_data[key].shape
                assert actual_shape == expected_shape, \
                    f"{key}: expected {expected_shape}, got {actual_shape}"


class TestFixturesArrayDtypes:
    """Test that array dtypes match expected values."""

    def test_state_array_dtype(self, require_golden_data, integration_pickle_data, expected_array_dtypes):
        """State array should have object dtype."""
        assert integration_pickle_data["state"].dtype == expected_array_dtypes["state"]

    def test_key_array_dtypes(self, require_golden_data, integration_pickle_data, expected_array_dtypes):
        """Key arrays should have expected dtypes."""
        for key, expected_dtype in expected_array_dtypes.items():
            if key in integration_pickle_data:
                actual_dtype = integration_pickle_data[key].dtype
                assert actual_dtype == expected_dtype, \
                    f"{key}: expected {expected_dtype}, got {actual_dtype}"


class TestFixturesKeys:
    """Test that key fixtures have correct structure."""

    def test_dataset_key_structure(self, dataset_key):
        """Dataset key should have dataset field."""
        assert "dataset" in dataset_key
        assert dataset_key["dataset"] == "Flamingo_2026-02-05_1"

    def test_video_key_structure(self, video_key):
        """Video key should have dataset, camera, doe fields."""
        assert "dataset" in video_key
        assert "camera" in video_key
        assert "doe" in video_key

    def test_dlc_key_structure(self, dlc_key):
        """DLC key should have dataset, camera, doe, model_name fields."""
        assert "dataset" in dlc_key
        assert "camera" in dlc_key
        assert "doe" in dlc_key
        assert "model_name" in dlc_key
