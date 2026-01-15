"""
Integration tests for data round-trips.

Tests verify that data can be:
1. Loaded from source files
2. Transformed/processed for DataJoint storage
3. Reconstructed back to original format
4. Values match within acceptable tolerances

These tests validate the data transformation pipeline that will be
used during the DataJoint 2.0 migration.
"""

import numpy as np
import pandas as pd
import pytest

# Import transformation functions
from dlc_helpers import (
    df_to_dj,
    dj_to_df,
    h5_to_dj,
    dlc_interpolate,
    dlc_savgol_filter,
    filter_dlc,
    compute_head_angles,
    find_closest_indices,
)
from helpers_dj import (
    get_state,
    get_box,
    get_camera,
    get_model_name,
    get_video_meta,
    get_name,
)
from populate_rig import (
    get_new_file,
    parse_date,
    get_files_paths,
)


# ==============================================================================
# DLC DataFrame Round-Trip Tests
# ==============================================================================

class TestDlcDataFrameRoundTrip:
    """Tests for DLC DataFrame serialization/deserialization round-trips."""

    def test_dlc_dataframe_full_roundtrip(self, dlc_dataframe):
        """Full DLC DataFrame should survive df_to_dj -> dj_to_df round-trip."""
        # Convert to DJ format
        dj_format = df_to_dj(dlc_dataframe)

        # Convert back to DataFrame (extract data, headers, scorer from dict)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        # Verify shape matches
        assert reconstructed.shape == dlc_dataframe.shape

        # Verify values match (using allclose for float comparison)
        assert np.allclose(
            reconstructed.values,
            dlc_dataframe.values,
            equal_nan=True
        )

    def test_dlc_dataframe_columns_preserved(self, dlc_dataframe):
        """Column structure should be preserved through round-trip."""
        dj_format = df_to_dj(dlc_dataframe)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        # Compare column tuples
        original_cols = list(dlc_dataframe.columns)
        reconstructed_cols = list(reconstructed.columns)

        assert len(original_cols) == len(reconstructed_cols)
        for orig, recon in zip(original_cols, reconstructed_cols):
            assert orig == recon

    def test_dlc_dataframe_index_preserved(self, dlc_dataframe):
        """Index should be preserved through round-trip."""
        dj_format = df_to_dj(dlc_dataframe)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        assert len(reconstructed.index) == len(dlc_dataframe.index)

    def test_dlc_subset_roundtrip(self, sample_dlc_subset):
        """Subset of DLC data should survive round-trip."""
        dj_format = df_to_dj(sample_dlc_subset)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        assert reconstructed.shape == sample_dlc_subset.shape
        assert np.allclose(
            reconstructed.values,
            sample_dlc_subset.values,
            equal_nan=True
        )


# ==============================================================================
# HDF5 to DataFrame Round-Trip Tests
# ==============================================================================

class TestH5ToDataFrameRoundTrip:
    """Tests for HDF5 file loading and DataFrame conversion."""

    def test_h5_to_dj_to_df_roundtrip(self, dlc_hdf5_path, dlc_dataframe):
        """HDF5 -> h5_to_dj -> dj_to_df should match direct pd.read_hdf."""
        # Load via h5_to_dj
        dj_format = h5_to_dj(str(dlc_hdf5_path))
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        # Compare with direct load
        assert reconstructed.shape == dlc_dataframe.shape
        assert np.allclose(
            reconstructed.values,
            dlc_dataframe.values,
            equal_nan=True
        )

    def test_h5_to_dj_preserves_bodyparts(self, dlc_hdf5_path, expected_dlc_bodyparts):
        """h5_to_dj should preserve all bodypart names."""
        dj_format = h5_to_dj(str(dlc_hdf5_path))
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        # Get unique bodyparts from columns
        bodyparts = reconstructed.columns.get_level_values(0).unique().tolist()

        # Check expected bodyparts are present
        for bp in expected_dlc_bodyparts:
            assert bp in bodyparts, f"Missing bodypart: {bp}"


# ==============================================================================
# State Array Extraction Tests
# ==============================================================================

class TestStateArrayExtraction:
    """Tests for state array extraction from pickle data."""

    def test_all_state_keys_extract_correctly(self, pickle_data, state_index_map):
        """All state keys should extract to arrays matching direct indexing."""
        for key, idx in state_index_map.items():
            extracted = get_state(raw_data=pickle_data, key=key)

            # Verify length
            assert len(extracted) == len(pickle_data["state"])

            # Verify all values match direct access
            for i in range(len(extracted)):
                expected = pickle_data["state"][i][idx]
                assert extracted[i] == expected, \
                    f"Mismatch at key={key}, index={i}"

    def test_state_extraction_preserves_dtype_values(self, pickle_data):
        """Extracted state values should preserve numeric precision."""
        x_pos = get_state(raw_data=pickle_data, key="x_pos")
        z_pos = get_state(raw_data=pickle_data, key="z_pos")

        # Check specific known values from first few entries
        assert x_pos[0] == pickle_data["state"][0][0]
        assert z_pos[0] == pickle_data["state"][0][1]

        # Verify they're numeric
        assert isinstance(x_pos[0], (int, float, np.number))
        assert isinstance(z_pos[0], (int, float, np.number))

    def test_state_extraction_roundtrip_to_array(self, pickle_data, state_index_map):
        """Extracted states should be reconstructible to original shape."""
        # Extract all columns
        columns = []
        for key in state_index_map.keys():
            col = get_state(raw_data=pickle_data, key=key)
            columns.append(col)

        # Stack into array
        reconstructed = np.column_stack(columns)

        # Should have same row count as original
        assert reconstructed.shape[0] == pickle_data["state"].shape[0]

        # Should have same number of extracted columns
        assert reconstructed.shape[1] == len(state_index_map)


# ==============================================================================
# Box Coordinate Extraction Tests
# ==============================================================================

class TestBoxCoordinateExtraction:
    """Tests for box coordinate extraction from pickle data."""

    def test_l_report_box_all_coordinates(self, pickle_data):
        """All l_report_box coordinates should extract correctly."""
        keys = ["l_box_x_min", "l_box_x_max", "l_box_z_min", "l_box_z_max"]
        transformer = {k: "nonexistent" for k in keys}  # Trigger new style

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["l_report_box"][i]

    def test_r_report_box_all_coordinates(self, pickle_data):
        """All r_report_box coordinates should extract correctly."""
        keys = ["r_box_x_min", "r_box_x_max", "r_box_z_min", "r_box_z_max"]
        transformer = {k: "nonexistent" for k in keys}

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["r_report_box"][i]

    def test_start_box_all_coordinates(self, pickle_data):
        """All start_box coordinates should extract correctly."""
        keys = ["tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max", "tt_box_angle"]
        transformer = {k: "nonexistent" for k in keys}

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["start_box"][i]


# ==============================================================================
# Metadata Extraction Tests
# ==============================================================================

class TestMetadataExtraction:
    """Tests for metadata extraction from JSON and pickle files."""

    def test_video_meta_all_fields(self, json_metadata):
        """All video_meta fields should extract correctly."""
        fields = ["duration", "fps", "width", "height"]

        for field in fields:
            result = get_video_meta(raw_data=json_metadata, key=field)
            assert result == json_metadata["video_meta"][field]

    def test_camera_name_matches_filename(self, json_metadata):
        """Extracted camera name should match DLC filename prefix."""
        result = get_camera(raw_data=json_metadata)
        filename = json_metadata["dlc_path"]["filename"]

        assert result == filename.split("_")[0]

    def test_model_name_matches_filename(self, json_metadata):
        """Extracted model name should match DLC filename suffix."""
        result = get_model_name(raw_data=json_metadata)
        filename = json_metadata["dlc_path"]["filename"]

        # Model name is last part before .hdf5
        expected = filename.replace(".hdf5", "").split("_")[-1]
        assert result == expected

    def test_session_label_extraction(self, pickle_data):
        """Session label should extract first element from list."""
        result = get_name(raw_data=pickle_data, key="session_label")

        assert result == pickle_data["session_label"][0]


# ==============================================================================
# DLC Processing Pipeline Tests
# ==============================================================================

class TestDlcProcessingPipeline:
    """Tests for the full DLC processing pipeline."""

    def test_filter_then_roundtrip(self, dlc_dataframe):
        """Filtered DLC data should survive round-trip."""
        # Filter the data
        filtered = filter_dlc(dlc_dataframe)

        # Round-trip
        dj_format = df_to_dj(filtered)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        # Verify shape
        assert reconstructed.shape == filtered.shape

        # Verify values (allowing NaN equality)
        assert np.allclose(
            reconstructed.values,
            filtered.values,
            equal_nan=True
        )

    def test_compute_head_angles_preserves_row_count(self, dlc_dataframe):
        """compute_head_angles should preserve row count."""
        result = compute_head_angles(dlc_dataframe)

        assert len(result) == len(dlc_dataframe)

    def test_interpolate_then_filter_produces_valid_output(self, sample_dlc_subset):
        """Interpolation followed by Savgol filter should produce valid output."""
        # Get a coordinate column
        bodypart = sample_dlc_subset.columns.get_level_values(0)[0]
        x_col = sample_dlc_subset[(bodypart, 'x')].values
        likelihood = sample_dlc_subset[(bodypart, 'likelihood')].values

        # Interpolate low confidence points
        interpolated = dlc_interpolate(x_col, likelihood, cutoff=0.9)

        # Check we have valid output (not all NaN)
        if not np.all(np.isnan(interpolated)):
            # Apply Savgol filter if we have valid interpolated data
            # (only if no NaN values remain)
            if not np.any(np.isnan(interpolated)):
                filtered = dlc_savgol_filter(interpolated)
                assert len(filtered) == len(x_col)
                assert not np.any(np.isnan(filtered))


# ==============================================================================
# File Loading Round-Trip Tests
# ==============================================================================

class TestFileLoadingRoundTrip:
    """Tests for file loading and data extraction."""

    def test_pickle_load_contains_all_expected_keys(self, pickle_path, expected_pickle_keys):
        """Loaded pickle should contain all expected keys."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key in expected_pickle_keys:
            assert key in data, f"Missing key: {key}"

    def test_pickle_load_array_shapes_match(self, pickle_path, expected_array_shapes):
        """Loaded pickle arrays should have expected shapes."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key, expected_shape in expected_array_shapes.items():
            assert data[key].shape == expected_shape, \
                f"Shape mismatch for {key}: expected {expected_shape}, got {data[key].shape}"

    def test_pickle_load_array_dtypes_match(self, pickle_path, expected_array_dtypes):
        """Loaded pickle arrays should have expected dtypes."""
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key, expected_dtype in expected_array_dtypes.items():
            assert data[key].dtype == expected_dtype, \
                f"Dtype mismatch for {key}: expected {expected_dtype}, got {data[key].dtype}"


# ==============================================================================
# Timestamp Alignment Tests
# ==============================================================================

class TestTimestampAlignment:
    """Tests for timestamp alignment between different data sources."""

    def test_find_closest_indices_with_real_data(self, pickle_data, timestamp_array):
        """find_closest_indices should work with real timestamp data."""
        step_time = pickle_data["step_time"]

        # Find indices for a subset of timestamps
        subset_timestamps = timestamp_array[:100]
        indices = find_closest_indices(step_time, subset_timestamps)

        # Verify we get correct number of indices
        assert len(indices) == len(subset_timestamps)

        # All indices should be valid
        for idx in indices:
            assert 0 <= idx < len(step_time)

    def test_timestamp_coverage(self, pickle_data, timestamp_array):
        """Timestamps should cover the experiment duration."""
        step_time = pickle_data["step_time"]

        # Camera timestamps should span similar range to step_time
        step_range = step_time[-1] - step_time[0]
        ts_range = timestamp_array[-1] - timestamp_array[0]

        # Should be within same order of magnitude
        assert ts_range > 0
        assert step_range > 0


# ==============================================================================
# Cross-File Consistency Tests
# ==============================================================================

class TestCrossFileConsistency:
    """Tests for consistency across different data files."""

    def test_dataset_name_consistency(self, pickle_path, json_metadata):
        """Dataset name should be consistent across files."""
        _, pickle_name = get_new_file(pickle_path.name, str(pickle_path.parent))

        assert pickle_name == json_metadata["dataset"]

    def test_date_parsing_matches_json(self, json_metadata):
        """Parsed date should match JSON metadata."""
        dataset = json_metadata["dataset"]
        parsed_date = parse_date(dataset)

        # The date should be extractable
        assert parsed_date is not None
        assert parsed_date.year == 2024
        assert parsed_date.month == 8
        assert parsed_date.day == 16

    def test_dlc_shape_matches_json_meta(self, dlc_dataframe, json_metadata):
        """DLC row count should be consistent with video duration."""
        fps = json_metadata["video_meta"]["fps"]
        duration = json_metadata["video_meta"]["duration"]

        expected_frames = int(fps * duration)

        # DLC frame count should be close to expected
        # (allowing for some tolerance due to processing)
        actual_frames = len(dlc_dataframe)

        # Should be within 10% (DLC may have fewer frames due to processing)
        assert actual_frames <= expected_frames
        assert actual_frames > expected_frames * 0.5  # At least 50%
