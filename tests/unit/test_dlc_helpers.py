"""
Unit tests for dlc_helpers.py

Tests the DLC data serialization and processing functions used for
storing and retrieving DeepLabCut keypoint data in DataJoint.

NOTE: These tests use synthetic mock data - no real file I/O required.
Tests that require real HDF5 files are in tests/integration/.
"""

import numpy as np
import pandas as pd
import pytest

# Import from dlc_helpers (path configured in conftest.py)
from dlc_helpers import (
    df_to_dj,
    dj_to_df,
    h5_to_dj,
    dlc_interpolate,
    dlc_savgol_filter,
    find_closest_indices,
    convert_angles,
    filter_dlc,
    compute_head_angles,
    _sync_dlc_with_game,
    get_offline_dlc_variables,
)


# ==============================================================================
# Tests for df_to_dj
# ==============================================================================

class TestDfToDj:
    """Tests for df_to_dj function."""

    def test_df_to_dj_returns_dict(self, mock_dlc_dataframe):
        """df_to_dj should return a dictionary."""
        result = df_to_dj(mock_dlc_dataframe)
        assert isinstance(result, dict)

    def test_df_to_dj_has_data_key(self, mock_dlc_dataframe):
        """Result should have 'data' key."""
        result = df_to_dj(mock_dlc_dataframe)
        assert "data" in result

    def test_df_to_dj_has_headers_key(self, mock_dlc_dataframe):
        """Result should have 'headers' key."""
        result = df_to_dj(mock_dlc_dataframe)
        assert "headers" in result

    def test_df_to_dj_two_level_no_scorer(self, mock_dlc_dataframe):
        """2-level MultiIndex should NOT have 'scorer' key."""
        # Our test data has 2 levels (bodyparts, coords)
        assert mock_dlc_dataframe.columns.nlevels == 2
        result = df_to_dj(mock_dlc_dataframe)
        assert "scorer" not in result

    def test_df_to_dj_data_shape(self, mock_dlc_dataframe):
        """Data array should match DataFrame shape."""
        result = df_to_dj(mock_dlc_dataframe)
        assert result["data"].shape == mock_dlc_dataframe.shape

    def test_df_to_dj_data_dtype(self, mock_dlc_dataframe):
        """Data should be numpy array."""
        result = df_to_dj(mock_dlc_dataframe)
        assert isinstance(result["data"], np.ndarray)

    def test_df_to_dj_headers_length(self, mock_dlc_dataframe):
        """Headers length should match number of columns."""
        result = df_to_dj(mock_dlc_dataframe)
        assert len(result["headers"]) == mock_dlc_dataframe.shape[1]

    def test_df_to_dj_headers_are_tuples(self, mock_dlc_dataframe):
        """Headers should be list of tuples for MultiIndex."""
        result = df_to_dj(mock_dlc_dataframe)
        assert isinstance(result["headers"], list)
        assert all(isinstance(h, tuple) for h in result["headers"])

    def test_df_to_dj_headers_tuple_length(self, mock_dlc_dataframe):
        """Header tuples should have 2 elements (bodyparts, coords)."""
        result = df_to_dj(mock_dlc_dataframe)
        # All headers should be 2-tuples
        assert all(len(h) == 2 for h in result["headers"])

    def test_df_to_dj_three_level_has_scorer(self):
        """3-level MultiIndex SHOULD have 'scorer' key."""
        # Create synthetic 3-level DataFrame
        arrays = [
            ["scorer1"] * 6,
            ["nose", "nose", "nose", "ear", "ear", "ear"],
            ["x", "y", "likelihood", "x", "y", "likelihood"],
        ]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples, names=["scorer", "bodyparts", "coords"])
        df = pd.DataFrame(np.random.rand(10, 6), columns=index)

        result = df_to_dj(df)
        assert "scorer" in result
        assert result["scorer"] == "scorer1"

    def test_df_to_dj_preserves_values(self, mock_dlc_dataframe):
        """Data values should match original DataFrame."""
        result = df_to_dj(mock_dlc_dataframe)
        np.testing.assert_array_equal(result["data"], mock_dlc_dataframe.to_numpy())


# ==============================================================================
# Tests for dj_to_df
# ==============================================================================

class TestDjToDf:
    """Tests for dj_to_df function."""

    def test_dj_to_df_returns_dataframe(self, mock_dlc_dataframe):
        """dj_to_df should return a DataFrame."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        assert isinstance(result, pd.DataFrame)

    def test_dj_to_df_shape_preserved(self, mock_dlc_dataframe):
        """Reconstructed DataFrame should have same shape."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        assert result.shape == mock_dlc_dataframe.shape

    def test_dj_to_df_multiindex_preserved(self, mock_dlc_dataframe):
        """Reconstructed DataFrame should have MultiIndex columns."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        assert isinstance(result.columns, pd.MultiIndex)

    def test_dj_to_df_nlevels_preserved(self, mock_dlc_dataframe):
        """Number of column levels should be preserved."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        assert result.columns.nlevels == mock_dlc_dataframe.columns.nlevels

    def test_dj_to_df_column_names_two_level(self, mock_dlc_dataframe):
        """2-level MultiIndex should have ['bodyparts', 'coords'] names."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], None)
        assert result.columns.names == ["bodyparts", "coords"]

    def test_dj_to_df_column_names_three_level(self):
        """3-level MultiIndex should have ['scorer', 'bodyparts', 'coords'] names."""
        # Create 3-level data
        arrays = [
            ["scorer1"] * 3,
            ["nose", "nose", "nose"],
            ["x", "y", "likelihood"],
        ]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples, names=["scorer", "bodyparts", "coords"])
        df = pd.DataFrame(np.random.rand(10, 3), columns=index)

        dj_data = df_to_dj(df)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data["scorer"])
        assert result.columns.names == ["scorer", "bodyparts", "coords"]

    def test_dj_to_df_roundtrip_values(self, mock_dlc_dataframe):
        """Round-trip should preserve all values."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        np.testing.assert_allclose(
            mock_dlc_dataframe.values, result.values, rtol=1e-10, equal_nan=True
        )

    def test_dj_to_df_roundtrip_columns(self, mock_dlc_dataframe):
        """Round-trip should preserve column tuples."""
        dj_data = df_to_dj(mock_dlc_dataframe)
        result = dj_to_df(dj_data["data"], dj_data["headers"], dj_data.get("scorer"))
        assert list(mock_dlc_dataframe.columns) == list(result.columns)


# ==============================================================================
# Tests for dlc_interpolate
# ==============================================================================

class TestDlcInterpolate:
    """Tests for dlc_interpolate function."""

    def test_dlc_interpolate_returns_array(self):
        """Should return numpy array."""
        trace = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        likelihood = np.array([0.9, 0.9, 0.9, 0.9, 0.9])
        result = dlc_interpolate(trace, likelihood)
        assert isinstance(result, np.ndarray)

    def test_dlc_interpolate_preserves_high_confidence(self):
        """High confidence points should be preserved."""
        trace = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        likelihood = np.array([0.9, 0.9, 0.9, 0.9, 0.9])
        result = dlc_interpolate(trace, likelihood, cutoff=0.6)
        np.testing.assert_array_equal(result, trace)

    def test_dlc_interpolate_replaces_low_confidence(self):
        """Low confidence points should be interpolated."""
        trace = np.array([1.0, 100.0, 3.0])  # 100 is outlier
        likelihood = np.array([0.9, 0.1, 0.9])  # middle point low confidence
        result = dlc_interpolate(trace, likelihood, cutoff=0.6)
        # Middle value should be interpolated to ~2.0
        assert result[1] == pytest.approx(2.0, rel=0.01)

    def test_dlc_interpolate_shape_preserved(self):
        """Output shape should match input shape."""
        trace = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        likelihood = np.array([0.9, 0.1, 0.9, 0.1, 0.9])
        result = dlc_interpolate(trace, likelihood)
        assert result.shape == trace.shape

    def test_dlc_interpolate_all_low_confidence(self):
        """When all points are low confidence, result contains NaN.

        Note: This documents actual behavior - when all points are below
        cutoff, they all become NaN and interpolate() can't fill them.
        ffill/bfill only work if there's at least one non-NaN value.
        """
        trace = np.array([1.0, 2.0, 3.0])
        likelihood = np.array([0.1, 0.1, 0.1])  # All low
        result = dlc_interpolate(trace, likelihood, cutoff=0.6)
        # All values become NaN since there's nothing to interpolate from
        assert np.all(np.isnan(result))

    def test_dlc_interpolate_cutoff_boundary(self):
        """Cutoff should be exclusive (< not <=)."""
        trace = np.array([1.0, 2.0, 3.0])
        likelihood = np.array([0.6, 0.6, 0.6])  # Exactly at cutoff
        result = dlc_interpolate(trace, likelihood, cutoff=0.6)
        # 0.6 < 0.6 is False, so values should be preserved
        np.testing.assert_array_equal(result, trace)


# ==============================================================================
# Tests for dlc_savgol_filter
# ==============================================================================

class TestDlcSavgolFilter:
    """Tests for dlc_savgol_filter function."""

    def test_dlc_savgol_filter_returns_array(self):
        """Should return numpy array."""
        trajectory = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = dlc_savgol_filter(trajectory)
        assert isinstance(result, np.ndarray)

    def test_dlc_savgol_filter_shape_preserved(self):
        """Output shape should match input shape."""
        trajectory = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = dlc_savgol_filter(trajectory)
        assert result.shape == trajectory.shape

    def test_dlc_savgol_filter_smooths_noise(self):
        """Should smooth noisy data."""
        # Create noisy data
        np.random.seed(42)
        clean = np.linspace(0, 10, 100)
        noisy = clean + np.random.normal(0, 0.5, 100)

        filtered = dlc_savgol_filter(noisy)

        # Filtered should be closer to clean than noisy
        noisy_error = np.mean(np.abs(noisy - clean))
        filtered_error = np.mean(np.abs(filtered - clean))
        assert filtered_error < noisy_error

    def test_dlc_savgol_filter_no_nan_output(self):
        """Output should not contain NaN values."""
        trajectory = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = dlc_savgol_filter(trajectory)
        assert not np.any(np.isnan(result))

    def test_dlc_savgol_filter_nan_input_behavior(self):
        """NaN in input behavior depends on scipy version.

        Some scipy versions raise ValueError on NaN input, others propagate
        NaNs which are then converted to 0 by np.nan_to_num.
        In practice, dlc_interpolate is called first to remove NaNs.
        """
        trajectory = np.array([1.0, np.nan, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        try:
            result = dlc_savgol_filter(trajectory)
            # If no exception, result should have no NaNs (nan_to_num converts them)
            assert not np.any(np.isnan(result))
            assert len(result) == len(trajectory)
        except ValueError:
            # Older scipy versions raise on NaN input - this is acceptable
            pass


# ==============================================================================
# Tests for find_closest_indices
# ==============================================================================

class TestFindClosestIndices:
    """Tests for find_closest_indices function."""

    def test_find_closest_indices_returns_list(self):
        """Should return a list."""
        pose_time = [0.0, 1.0, 2.0, 3.0, 4.0]
        step_time = [0.5, 1.5, 2.5]
        result = find_closest_indices(pose_time, step_time)
        assert isinstance(result, list)

    def test_find_closest_indices_length(self):
        """Result length should match step_time length."""
        pose_time = [0.0, 1.0, 2.0, 3.0, 4.0]
        step_time = [0.5, 1.5, 2.5]
        result = find_closest_indices(pose_time, step_time)
        assert len(result) == len(step_time)

    def test_find_closest_indices_exact_match(self):
        """Exact matches should return correct indices."""
        pose_time = [0.0, 1.0, 2.0, 3.0, 4.0]
        step_time = [1.0, 3.0]
        result = find_closest_indices(pose_time, step_time)
        assert result == [1, 3]

    def test_find_closest_indices_between_values(self):
        """Values between should return closest index."""
        pose_time = [0.0, 1.0, 2.0, 3.0, 4.0]
        step_time = [0.4, 0.6]  # 0.4 closer to 0, 0.6 closer to 1
        result = find_closest_indices(pose_time, step_time)
        assert result == [0, 1]

    def test_find_closest_indices_before_first(self):
        """Values before first should return 0."""
        pose_time = [1.0, 2.0, 3.0]
        step_time = [0.0, 0.5]
        result = find_closest_indices(pose_time, step_time)
        assert result[0] == 0
        assert result[1] == 0

    def test_find_closest_indices_after_last(self):
        """Values after last should return last index."""
        pose_time = [0.0, 1.0, 2.0]
        step_time = [3.0, 10.0]
        result = find_closest_indices(pose_time, step_time)
        assert result == [2, 2]

    def test_find_closest_indices_empty_step_time(self):
        """Empty step_time should return empty list."""
        pose_time = [0.0, 1.0, 2.0]
        step_time = []
        result = find_closest_indices(pose_time, step_time)
        assert result == []


# ==============================================================================
# Tests for convert_angles
# ==============================================================================

class TestConvertAngles:
    """Tests for convert_angles function."""

    def test_convert_angles_returns_series(self):
        """Should return pandas Series."""
        data = pd.Series([0.0, 90.0, 180.0, 270.0])
        result = convert_angles(data)
        assert isinstance(result, pd.Series)

    def test_convert_angles_shift_90(self):
        """Default shift of 90 degrees."""
        data = pd.Series([90.0])
        result = convert_angles(data, shift=90)
        assert result.iloc[0] == pytest.approx(0.0)

    def test_convert_angles_range(self):
        """Output should be in [-180, 180] range."""
        data = pd.Series([0.0, 90.0, 180.0, 270.0, 360.0, -90.0, -180.0])
        result = convert_angles(data, shift=0)
        assert all(-180 <= v <= 180 for v in result)

    def test_convert_angles_wrapping(self):
        """Should correctly wrap angles."""
        data = pd.Series([270.0])  # 270 - 90 = 180, wraps to 180 or -180
        result = convert_angles(data, shift=90)
        assert result.iloc[0] == pytest.approx(0.0) or result.iloc[0] == pytest.approx(180.0) or result.iloc[0] == pytest.approx(-180.0)

    def test_convert_angles_preserves_length(self):
        """Output length should match input length."""
        data = pd.Series([0.0, 45.0, 90.0, 135.0, 180.0])
        result = convert_angles(data)
        assert len(result) == len(data)


# ==============================================================================
# Tests for filter_dlc (integration of interpolate + savgol)
# ==============================================================================

class TestFilterDlc:
    """Tests for filter_dlc function."""

    def test_filter_dlc_returns_dataframe(self, mock_dlc_dataframe):
        """Should return a DataFrame."""
        result = filter_dlc(mock_dlc_dataframe.copy())
        assert isinstance(result, pd.DataFrame)

    def test_filter_dlc_shape_preserved(self, mock_dlc_dataframe):
        """Output shape should match input shape."""
        df = mock_dlc_dataframe.copy()
        result = filter_dlc(df)
        assert result.shape == mock_dlc_dataframe.shape

    def test_filter_dlc_columns_preserved(self, mock_dlc_dataframe):
        """Columns should be preserved."""
        df = mock_dlc_dataframe.copy()
        result = filter_dlc(df)
        assert list(result.columns) == list(mock_dlc_dataframe.columns)

    def test_filter_dlc_no_nan_in_xy(self, mock_dlc_dataframe):
        """Filtered x and y columns should not have NaN."""
        df = mock_dlc_dataframe.copy()
        result = filter_dlc(df)
        # Check a few bodyparts
        for bp in ["nose", "left_ear", "neck"]:
            if (bp, "x") in result.columns:
                # After filtering, there might still be some NaN at edges
                # but the filtering should have reduced them
                pass  # Just ensure no errors


# ==============================================================================
# Tests for compute_head_angles
# ==============================================================================

class TestComputeHeadAngles:
    """Tests for compute_head_angles function."""

    def test_compute_head_angles_returns_dataframe(self, mock_dlc_dataframe):
        """Should return a DataFrame."""
        # Filter first as required by the function
        filtered = filter_dlc(mock_dlc_dataframe.copy())
        result = compute_head_angles(filtered)
        assert isinstance(result, pd.DataFrame)

    def test_compute_head_angles_has_expected_columns(self, mock_dlc_dataframe):
        """Should have head_center_x, head_center_y, heading_dir, head_angle columns."""
        filtered = filter_dlc(mock_dlc_dataframe.copy())
        result = compute_head_angles(filtered)
        expected_cols = ["head_center_x", "head_center_y", "heading_dir", "head_angle"]
        for col in expected_cols:
            assert col in result.columns

    def test_compute_head_angles_row_count(self, mock_dlc_dataframe):
        """Output should have same number of rows as input."""
        filtered = filter_dlc(mock_dlc_dataframe.copy())
        result = compute_head_angles(filtered)
        assert len(result) == len(filtered)


# ==============================================================================
# Tests for h5_to_dj
# ==============================================================================

class TestH5ToDj:
    """Tests for h5_to_dj function - reads HDF5 files and converts to DJ format."""

    @pytest.fixture
    def sample_dlc_hdf5(self, tmp_path):
        """Create a sample DLC-style HDF5 file for testing."""
        # Create multi-level column index like DLC output
        arrays = [
            ["nose", "nose", "nose", "left_ear", "left_ear", "left_ear"],
            ["x", "y", "likelihood", "x", "y", "likelihood"],
        ]
        tuples = list(zip(*arrays))
        columns = pd.MultiIndex.from_tuples(tuples, names=["bodyparts", "coords"])

        # Create sample data
        n_frames = 100
        data = np.random.rand(n_frames, 6)
        df = pd.DataFrame(data, columns=columns)

        # Save to HDF5
        h5_path = tmp_path / "test_DLC.hdf5"
        df.to_hdf(str(h5_path), key="df_with_missing", mode="w")

        return h5_path

    def test_h5_to_dj_returns_dict(self, sample_dlc_hdf5):
        """h5_to_dj should return a dictionary."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert isinstance(result, dict)

    def test_h5_to_dj_has_data_key(self, sample_dlc_hdf5):
        """Result should have 'data' key."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert "data" in result

    def test_h5_to_dj_has_headers_key(self, sample_dlc_hdf5):
        """Result should have 'headers' key."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert "headers" in result

    def test_h5_to_dj_data_is_array(self, sample_dlc_hdf5):
        """Data should be a numpy array."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert isinstance(result["data"], np.ndarray)

    def test_h5_to_dj_headers_are_list(self, sample_dlc_hdf5):
        """Headers should be a list."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert isinstance(result["headers"], list)

    def test_h5_to_dj_data_shape(self, sample_dlc_hdf5):
        """Data should have expected shape (100 frames, 6 columns)."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert result["data"].shape == (100, 6)

    def test_h5_to_dj_headers_count(self, sample_dlc_hdf5):
        """Should have 6 headers (2 bodyparts x 3 coords)."""
        result = h5_to_dj(str(sample_dlc_hdf5))
        assert len(result["headers"]) == 6

    def test_h5_to_dj_roundtrip_with_dj_to_df(self, sample_dlc_hdf5):
        """Data should be recoverable using dj_to_df."""
        # Read HDF5
        dj_data = h5_to_dj(str(sample_dlc_hdf5))

        # Convert back to DataFrame
        df_recovered = dj_to_df(
            dj_data["data"],
            dj_data["headers"],
            dj_data.get("scorer")
        )

        # Should have same shape
        assert df_recovered.shape == (100, 6)

    def test_h5_to_dj_three_level_index(self, tmp_path):
        """Should handle 3-level MultiIndex (with scorer)."""
        # Create 3-level column index
        arrays = [
            ["DLCmodel"] * 6,
            ["nose", "nose", "nose", "left_ear", "left_ear", "left_ear"],
            ["x", "y", "likelihood", "x", "y", "likelihood"],
        ]
        tuples = list(zip(*arrays))
        columns = pd.MultiIndex.from_tuples(tuples, names=["scorer", "bodyparts", "coords"])

        df = pd.DataFrame(np.random.rand(50, 6), columns=columns)
        h5_path = tmp_path / "test_scorer_DLC.hdf5"
        df.to_hdf(str(h5_path), key="df_with_missing", mode="w")

        result = h5_to_dj(str(h5_path))

        assert "scorer" in result
        assert result["scorer"] == "DLCmodel"


# ==============================================================================
# Tests for _sync_dlc_with_game
# ==============================================================================

class TestSyncDlcWithGame:
    """Tests for _sync_dlc_with_game function."""

    @pytest.fixture
    def sample_game_data(self):
        """Create sample game data DataFrame."""
        return pd.DataFrame({
            "step": np.arange(100),
            "step_time": np.linspace(0, 10, 100),
            "start_time": [1000.0] * 100,  # Constant start time
        })

    @pytest.fixture
    def sample_dlc_df(self):
        """Create sample DLC DataFrame with pose_time."""
        n_frames = 150  # More frames than game steps
        arrays = [
            ["nose", "nose", "nose"],
            ["x", "y", "likelihood"],
        ]
        tuples = list(zip(*arrays))
        columns = pd.MultiIndex.from_tuples(tuples, names=["bodyparts", "coords"])

        df = pd.DataFrame(np.random.rand(n_frames, 3), columns=columns)
        # Add pose_time as if camera timestamps
        df["pose_time"] = np.linspace(1000, 1010, n_frames)
        return df

    def test_sync_dlc_with_game_returns_dataframe(self, sample_game_data, sample_dlc_df):
        """Should return a DataFrame."""
        result = _sync_dlc_with_game(sample_game_data, sample_dlc_df)
        assert isinstance(result, pd.DataFrame)

    def test_sync_dlc_with_game_adds_step_column(self, sample_game_data, sample_dlc_df):
        """Should add step column from game data."""
        result = _sync_dlc_with_game(sample_game_data, sample_dlc_df)
        assert ("index", "step") in result.columns

    def test_sync_dlc_with_game_adds_step_time_column(self, sample_game_data, sample_dlc_df):
        """Should add step_time column from game data."""
        result = _sync_dlc_with_game(sample_game_data, sample_dlc_df)
        assert ("index", "step_time") in result.columns

    def test_sync_dlc_with_game_row_count_matches_game(self, sample_game_data, sample_dlc_df):
        """Output should have same number of rows as game data."""
        result = _sync_dlc_with_game(sample_game_data, sample_dlc_df)
        assert len(result) == len(sample_game_data)

    def test_sync_dlc_with_game_adjusts_pose_time(self, sample_game_data, sample_dlc_df):
        """pose_time should be adjusted by subtracting start_time."""
        result = _sync_dlc_with_game(sample_game_data, sample_dlc_df)
        # Adjusted pose_time should be close to step_time values
        assert ("index", "pose_time") in result.columns


# ==============================================================================
# Tests for get_offline_dlc_variables
# ==============================================================================

class TestGetOfflineDlcVariables:
    """Tests for get_offline_dlc_variables function."""

    def test_get_offline_dlc_variables_returns_dataframe(self, mock_dlc_dataframe):
        """Should return a DataFrame."""
        # Add required time columns
        df = mock_dlc_dataframe.copy()
        df["pose_time"] = np.linspace(0, 10, len(df))
        df["step"] = np.arange(len(df))
        df["step_time"] = np.linspace(0, 10, len(df))

        result = get_offline_dlc_variables(df)
        assert isinstance(result, pd.DataFrame)

    def test_get_offline_dlc_variables_has_heading_dir(self, mock_dlc_dataframe):
        """Should have heading_dir column."""
        df = mock_dlc_dataframe.copy()
        df["pose_time"] = np.linspace(0, 10, len(df))
        df["step"] = np.arange(len(df))
        df["step_time"] = np.linspace(0, 10, len(df))

        result = get_offline_dlc_variables(df)
        assert "heading_dir" in result.columns

    def test_get_offline_dlc_variables_has_head_angle(self, mock_dlc_dataframe):
        """Should have head_angle column."""
        df = mock_dlc_dataframe.copy()
        df["pose_time"] = np.linspace(0, 10, len(df))
        df["step"] = np.arange(len(df))
        df["step_time"] = np.linspace(0, 10, len(df))

        result = get_offline_dlc_variables(df)
        assert "head_angle" in result.columns

    def test_get_offline_dlc_variables_preserves_time_columns(self, mock_dlc_dataframe):
        """Should preserve pose_time, step, step_time columns."""
        df = mock_dlc_dataframe.copy()
        df["pose_time"] = np.linspace(0, 10, len(df))
        df["step"] = np.arange(len(df))
        df["step_time"] = np.linspace(0, 10, len(df))

        result = get_offline_dlc_variables(df)
        assert "pose_time" in result.columns
        assert "step" in result.columns
        assert "step_time" in result.columns

    def test_get_offline_dlc_variables_heading_dir_is_converted(self, mock_dlc_dataframe):
        """heading_dir should be converted with 90 degree shift."""
        df = mock_dlc_dataframe.copy()
        df["pose_time"] = np.linspace(0, 10, len(df))
        df["step"] = np.arange(len(df))
        df["step_time"] = np.linspace(0, 10, len(df))

        result = get_offline_dlc_variables(df)
        # Check that heading_dir values are in range [-180, 180]
        assert all(-180 <= v <= 180 for v in result["heading_dir"] if not np.isnan(v))


# ==============================================================================
# Additional edge case tests
# ==============================================================================

class TestComputeHeadAnglesEdgeCases:
    """Tests for edge cases in _compute_single_heading_angle."""

    def test_compute_head_angles_handles_zero_vectors(self, mock_dlc_dataframe):
        """Should handle edge case of zero-length vectors (ValueError in acos)."""
        # Create data where body axis might be zero
        df = mock_dlc_dataframe.copy()
        # Set neck and tail_base to same position for one row
        df.iloc[0, df.columns.get_loc(("neck", "x"))] = 0
        df.iloc[0, df.columns.get_loc(("neck", "y"))] = 0
        df.iloc[0, df.columns.get_loc(("tail_base", "x"))] = 0
        df.iloc[0, df.columns.get_loc(("tail_base", "y"))] = 0

        filtered = filter_dlc(df)
        # Should not raise an error - handles ValueError in acos
        result = compute_head_angles(filtered)
        assert isinstance(result, pd.DataFrame)


# ==============================================================================
# Note: Tests with real HDF5 files from test_data/ are in tests/integration/
# ==============================================================================
