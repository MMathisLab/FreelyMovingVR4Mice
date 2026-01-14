"""
Smoke tests to verify test fixtures work correctly.
These tests validate the test infrastructure itself.
"""

import numpy as np
import pandas as pd
import pytest


class TestFixturesPaths:
    """Test that path fixtures resolve correctly."""

    def test_test_data_path_exists(self, test_data_path):
        """Test data directory should exist."""
        assert test_data_path.exists()
        assert test_data_path.is_dir()

    def test_pickle_path_exists(self, pickle_path):
        """Pickle file should exist."""
        assert pickle_path.exists()
        assert pickle_path.suffix == ".pickle"

    def test_json_path_exists(self, json_path):
        """JSON file should exist."""
        assert json_path.exists()
        assert json_path.suffix == ".json"

    def test_dlc_hdf5_path_exists(self, dlc_hdf5_path):
        """DLC HDF5 file should exist."""
        assert dlc_hdf5_path.exists()
        assert dlc_hdf5_path.suffix == ".hdf5"

    def test_timestamp_path_exists(self, timestamp_path):
        """Timestamp file should exist."""
        assert timestamp_path.exists()
        assert timestamp_path.suffix == ".npy"

    def test_proc_path_exists(self, proc_path):
        """PROC file should exist."""
        assert proc_path.exists()


class TestFixturesDataLoading:
    """Test that data fixtures load correctly."""

    def test_pickle_data_is_dict(self, pickle_data):
        """Pickle data should be a dict."""
        assert isinstance(pickle_data, dict)

    def test_pickle_data_has_keys(self, pickle_data, expected_pickle_keys):
        """Pickle data should have expected keys."""
        assert len(pickle_data) == 53
        for key in expected_pickle_keys:
            assert key in pickle_data, f"Missing key: {key}"

    def test_json_metadata_is_dict(self, json_metadata):
        """JSON metadata should be a dict."""
        assert isinstance(json_metadata, dict)

    def test_json_metadata_has_dataset(self, json_metadata):
        """JSON should have dataset key."""
        assert "dataset" in json_metadata
        assert json_metadata["dataset"] == "Nightingale_2024-08-16_1"

    def test_dlc_dataframe_is_dataframe(self, dlc_dataframe):
        """DLC data should be a DataFrame."""
        assert isinstance(dlc_dataframe, pd.DataFrame)

    def test_dlc_dataframe_shape(self, dlc_dataframe, expected_dlc_shape):
        """DLC DataFrame should have expected shape."""
        assert dlc_dataframe.shape == expected_dlc_shape

    def test_dlc_dataframe_multiindex(self, dlc_dataframe):
        """DLC DataFrame should have MultiIndex columns."""
        assert isinstance(dlc_dataframe.columns, pd.MultiIndex)
        assert dlc_dataframe.columns.nlevels == 2
        assert dlc_dataframe.columns.names == ["bodyparts", "coords"]

    def test_timestamp_array_is_ndarray(self, timestamp_array):
        """Timestamp should be a numpy array."""
        assert isinstance(timestamp_array, np.ndarray)

    def test_timestamp_array_shape(self, timestamp_array):
        """Timestamp array should have expected shape."""
        assert timestamp_array.shape == (455965,)
        assert timestamp_array.dtype == np.float64

    def test_proc_data_is_dict(self, proc_data):
        """PROC data should be a dict."""
        assert isinstance(proc_data, dict)

    def test_proc_data_has_keys(self, proc_data):
        """PROC data should have expected keys."""
        expected_keys = [
            "start_time", "frame_time", "time_stamp", "step", "signal",
            "photodiode_read", "photodiode_time", "x_pos", "y_pos",
            "heading_direction", "head_angle"
        ]
        for key in expected_keys:
            assert key in proc_data, f"Missing key: {key}"


class TestFixturesArrayShapes:
    """Test that array shapes match expected values."""

    def test_state_array_shape(self, state_array, expected_array_shapes):
        """State array should have expected shape."""
        assert state_array.shape == expected_array_shapes["state"]

    def test_key_array_shapes(self, pickle_data, expected_array_shapes):
        """Key arrays should have expected shapes."""
        for key, expected_shape in expected_array_shapes.items():
            if key in pickle_data:
                actual_shape = pickle_data[key].shape
                assert actual_shape == expected_shape, \
                    f"{key}: expected {expected_shape}, got {actual_shape}"


class TestFixturesArrayDtypes:
    """Test that array dtypes match expected values."""

    def test_state_array_dtype(self, state_array, expected_array_dtypes):
        """State array should be float32."""
        assert state_array.dtype == expected_array_dtypes["state"]

    def test_key_array_dtypes(self, pickle_data, expected_array_dtypes):
        """Key arrays should have expected dtypes."""
        for key, expected_dtype in expected_array_dtypes.items():
            if key in pickle_data:
                actual_dtype = pickle_data[key].dtype
                assert actual_dtype == expected_dtype, \
                    f"{key}: expected {expected_dtype}, got {actual_dtype}"


class TestFixturesKeys:
    """Test that key fixtures have correct structure."""

    def test_dataset_key_structure(self, dataset_key):
        """Dataset key should have dataset field."""
        assert "dataset" in dataset_key
        assert dataset_key["dataset"] == "Nightingale_2024-08-16_1"

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
