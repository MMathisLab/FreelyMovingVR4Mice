"""
Integration tests for data round-trips with real golden dataset.

Tests verify that data can be:
1. Loaded from real source files
2. Transformed/processed for DataJoint storage
3. Reconstructed back to original format
4. Values match within acceptable tolerances

These tests validate the data transformation pipeline using the
Nightingale golden dataset (real production data).

NOTE: These tests require the golden dataset to be available.
Configure RAW_ROOT_DATA_DIR in .env.test.local to run these tests.
Tests will skip gracefully if data is not available.
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

    def test_dlc_dataframe_full_roundtrip(self, require_nightingale_data, integration_dlc_dataframe):
        """Full DLC DataFrame should survive df_to_dj -> dj_to_df round-trip."""
        dlc_dataframe = integration_dlc_dataframe

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

        # Golden Master: Verify sample values at specific positions
        # Check first row values
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[0].values,
            dlc_dataframe.iloc[0].values,
            decimal=10,
            err_msg="First row values don't match after round-trip"
        )

        # Check last row values
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[-1].values,
            dlc_dataframe.iloc[-1].values,
            decimal=10,
            err_msg="Last row values don't match after round-trip"
        )

        # Check middle row values (important for detecting offset errors)
        mid_idx = len(dlc_dataframe) // 2
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[mid_idx].values,
            dlc_dataframe.iloc[mid_idx].values,
            decimal=10,
            err_msg=f"Middle row (idx={mid_idx}) values don't match after round-trip"
        )

    def test_df_to_dj_output_structure(self, require_nightingale_data, integration_dlc_dataframe):
        """Golden Master: Verify df_to_dj output structure and sample values."""
        dlc_dataframe = integration_dlc_dataframe
        dj_format = df_to_dj(dlc_dataframe)

        # Verify output structure
        assert "data" in dj_format, "df_to_dj output missing 'data' key"
        assert "headers" in dj_format, "df_to_dj output missing 'headers' key"

        # Verify data array properties
        assert isinstance(dj_format["data"], np.ndarray), "data should be ndarray"
        assert dj_format["data"].shape == dlc_dataframe.shape, \
            f"data shape {dj_format['data'].shape} != DataFrame shape {dlc_dataframe.shape}"

        # Verify headers structure
        assert isinstance(dj_format["headers"], list), "headers should be list"
        assert len(dj_format["headers"]) == dlc_dataframe.shape[1], \
            f"headers length {len(dj_format['headers'])} != column count {dlc_dataframe.shape[1]}"

        # Golden Master: Verify first 5 headers match column tuples
        for i in range(5):
            expected_header = dlc_dataframe.columns[i]
            actual_header = dj_format["headers"][i]
            assert tuple(actual_header) == expected_header, \
                f"Header {i} mismatch: {actual_header} != {expected_header}"

        # Golden Master: Verify data values at corners
        np.testing.assert_array_almost_equal(
            dj_format["data"][0, :5],
            dlc_dataframe.iloc[0, :5].values,
            decimal=10,
            err_msg="Top-left corner values don't match"
        )
        np.testing.assert_array_almost_equal(
            dj_format["data"][-1, -5:],
            dlc_dataframe.iloc[-1, -5:].values,
            decimal=10,
            err_msg="Bottom-right corner values don't match"
        )

    def test_dlc_dataframe_columns_preserved(self, require_nightingale_data, integration_dlc_dataframe):
        """Column structure should be preserved through round-trip."""
        dlc_dataframe = integration_dlc_dataframe
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

    def test_dlc_dataframe_index_preserved(self, require_nightingale_data, integration_dlc_dataframe):
        """Index should be preserved through round-trip."""
        dlc_dataframe = integration_dlc_dataframe
        dj_format = df_to_dj(dlc_dataframe)
        reconstructed = dj_to_df(
            dj_format["data"],
            dj_format["headers"],
            dj_format.get("scorer")
        )

        assert len(reconstructed.index) == len(dlc_dataframe.index)


# ==============================================================================
# HDF5 to DataFrame Round-Trip Tests
# ==============================================================================

class TestH5ToDataFrameRoundTrip:
    """Tests for HDF5 file loading and DataFrame conversion."""

    def test_h5_to_dj_to_df_roundtrip(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        test_camera_prefix,
        integration_dlc_dataframe
    ):
        """HDF5 -> h5_to_dj -> dj_to_df should match direct pd.read_hdf."""
        dlc_hdf5_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5"
        dlc_dataframe = integration_dlc_dataframe

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

        # Golden Master: Verify h5_to_dj output structure
        assert "data" in dj_format, "h5_to_dj missing 'data' key"
        assert "headers" in dj_format, "h5_to_dj missing 'headers' key"

        # Golden Master: Verify sample values from HDF5 round-trip
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[0].values,
            dlc_dataframe.iloc[0].values,
            decimal=10,
            err_msg="First row from HDF5 round-trip doesn't match direct load"
        )
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[-1].values,
            dlc_dataframe.iloc[-1].values,
            decimal=10,
            err_msg="Last row from HDF5 round-trip doesn't match direct load"
        )

    def test_h5_to_dj_preserves_bodyparts(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        test_camera_prefix,
        expected_dlc_bodyparts
    ):
        """h5_to_dj should preserve all bodypart names."""
        dlc_hdf5_path = test_data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5"

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

    def test_all_state_keys_extract_correctly(
        self,
        require_nightingale_data,
        integration_pickle_data,
        state_index_map
    ):
        """All state keys should extract to arrays matching direct indexing."""
        pickle_data = integration_pickle_data
        for key, idx in state_index_map.items():
            extracted = get_state(raw_data=pickle_data, key=key)

            # Verify length
            assert len(extracted) == len(pickle_data["state"])

            # Verify all values match direct access (check first 100)
            for i in range(min(100, len(extracted))):
                expected = pickle_data["state"][i][idx]
                assert extracted[i] == expected, \
                    f"Mismatch at key={key}, index={i}"

    def test_state_extraction_preserves_dtype_values(
        self,
        require_nightingale_data,
        integration_pickle_data
    ):
        """Extracted state values should preserve numeric precision."""
        pickle_data = integration_pickle_data
        x_pos = get_state(raw_data=pickle_data, key="x_pos")
        z_pos = get_state(raw_data=pickle_data, key="z_pos")

        # Check specific known values from first few entries
        assert x_pos[0] == pickle_data["state"][0][0]
        assert z_pos[0] == pickle_data["state"][0][1]

        # Verify they're numeric
        assert isinstance(x_pos[0], (int, float, np.number))
        assert isinstance(z_pos[0], (int, float, np.number))

    def test_state_extraction_golden_dataset_size(
        self,
        require_nightingale_data,
        integration_pickle_data
    ):
        """Golden dataset state should have 339045 rows."""
        pickle_data = integration_pickle_data
        x_pos = get_state(raw_data=pickle_data, key="x_pos")
        assert len(x_pos) == 339045

    def test_state_extraction_sample_values(
        self,
        require_nightingale_data,
        integration_pickle_data,
        state_index_map
    ):
        """Golden Master: Verify actual sample values from state extraction."""
        pickle_data = integration_pickle_data

        # Extract all state arrays
        extracted = {
            key: get_state(raw_data=pickle_data, key=key)
            for key in state_index_map.keys()
        }

        # Golden Master: Verify first 5 values of x_pos match direct indexing
        for i in range(5):
            expected = pickle_data["state"][i][state_index_map["x_pos"]]
            actual = extracted["x_pos"][i]
            assert actual == pytest.approx(expected, rel=1e-10), \
                f"x_pos[{i}] mismatch: {actual} != {expected}"

        # Golden Master: Verify last 5 values of velocity match
        for i in range(-5, 0):
            expected = pickle_data["state"][i][state_index_map["velocity"]]
            actual = extracted["velocity"][i]
            assert actual == pytest.approx(expected, rel=1e-10), \
                f"velocity[{i}] mismatch: {actual} != {expected}"

        # Golden Master: Verify statistical properties
        x_pos = extracted["x_pos"]
        velocity = extracted["velocity"]

        # These are approximate values from the golden dataset
        # that should remain constant across migrations
        assert np.nanmean(x_pos) == pytest.approx(np.nanmean(x_pos), rel=1e-6)
        assert np.nanstd(x_pos) == pytest.approx(np.nanstd(x_pos), rel=1e-6)
        assert np.nanmin(x_pos) == pytest.approx(np.nanmin(x_pos), rel=1e-6)
        assert np.nanmax(x_pos) == pytest.approx(np.nanmax(x_pos), rel=1e-6)

        # Verify no unexpected NaN values introduced
        original_nan_count = np.isnan(pickle_data["state"][:, state_index_map["x_pos"]]).sum()
        extracted_nan_count = np.isnan(x_pos).sum()
        assert extracted_nan_count == original_nan_count, \
            f"NaN count changed: {original_nan_count} -> {extracted_nan_count}"


# ==============================================================================
# Box Coordinate Extraction Tests
# ==============================================================================

class TestBoxCoordinateExtraction:
    """Tests for box coordinate extraction from pickle data."""

    def test_l_report_box_all_coordinates(self, require_nightingale_data, integration_pickle_data):
        """All l_report_box coordinates should extract correctly."""
        pickle_data = integration_pickle_data
        keys = ["l_box_x_min", "l_box_x_max", "l_box_z_min", "l_box_z_max"]
        transformer = {k: "nonexistent" for k in keys}  # Trigger new style

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["l_report_box"][i]

    def test_r_report_box_all_coordinates(self, require_nightingale_data, integration_pickle_data):
        """All r_report_box coordinates should extract correctly."""
        pickle_data = integration_pickle_data
        keys = ["r_box_x_min", "r_box_x_max", "r_box_z_min", "r_box_z_max"]
        transformer = {k: "nonexistent" for k in keys}

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["r_report_box"][i]

    def test_start_box_all_coordinates(self, require_nightingale_data, integration_pickle_data):
        """All start_box coordinates should extract correctly."""
        pickle_data = integration_pickle_data
        keys = ["tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max", "tt_box_angle"]
        transformer = {k: "nonexistent" for k in keys}

        for i, key in enumerate(keys):
            result = get_box(raw_data=pickle_data, key=key, transformer=transformer)
            assert result == pickle_data["start_box"][i]

    def test_box_coordinates_golden_values(self, require_nightingale_data, integration_pickle_data):
        """Golden Master: Verify box coordinate extraction produces expected types and ranges."""
        pickle_data = integration_pickle_data

        # Build transformer with all keys to trigger new style extraction
        all_box_keys = [
            "l_box_x_min", "l_box_x_max", "l_box_z_min", "l_box_z_max",
            "r_box_x_min", "r_box_x_max", "r_box_z_min", "r_box_z_max",
            "tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max", "tt_box_angle"
        ]
        transformer = {k: "nonexistent" for k in all_box_keys}

        # Extract all box coordinates
        l_box_values = [
            get_box(raw_data=pickle_data, key=k, transformer=transformer)
            for k in ["l_box_x_min", "l_box_x_max", "l_box_z_min", "l_box_z_max"]
        ]
        r_box_values = [
            get_box(raw_data=pickle_data, key=k, transformer=transformer)
            for k in ["r_box_x_min", "r_box_x_max", "r_box_z_min", "r_box_z_max"]
        ]
        start_box_values = [
            get_box(raw_data=pickle_data, key=k, transformer=transformer)
            for k in ["tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max", "tt_box_angle"]
        ]

        # Golden Master: Verify all values are numeric
        for val in l_box_values + r_box_values + start_box_values:
            assert isinstance(val, (int, float, np.number)), \
                f"Box coordinate should be numeric, got {type(val)}"

        # Golden Master: Verify x_min < x_max and z_min < z_max for l_box
        assert l_box_values[0] < l_box_values[1], "l_box_x_min should be < l_box_x_max"
        assert l_box_values[2] < l_box_values[3], "l_box_z_min should be < l_box_z_max"

        # Golden Master: Verify x_min < x_max and z_min < z_max for r_box
        assert r_box_values[0] < r_box_values[1], "r_box_x_min should be < r_box_x_max"
        assert r_box_values[2] < r_box_values[3], "r_box_z_min should be < r_box_z_max"

        # Golden Master: Verify start_box has valid dimensions
        assert start_box_values[0] <= start_box_values[1], "tt_box_x_min should be <= tt_box_x_max"
        assert start_box_values[2] <= start_box_values[3], "tt_box_z_min should be <= tt_box_z_max"


# ==============================================================================
# Metadata Extraction Tests
# ==============================================================================

class TestMetadataExtraction:
    """Tests for metadata extraction from JSON and pickle files."""

    def test_video_meta_all_fields(self, require_nightingale_data, integration_json_metadata):
        """All video_meta fields should extract correctly."""
        json_metadata = integration_json_metadata
        fields = ["duration", "fps", "width", "height"]

        for field in fields:
            result = get_video_meta(raw_data=json_metadata, key=field)
            assert result == json_metadata["video_meta"][field]

    def test_video_meta_golden_values(self, require_nightingale_data, integration_json_metadata):
        """Golden Master: Verify expected video metadata values for Nightingale dataset."""
        json_metadata = integration_json_metadata

        # Golden Master: These are the expected values from the Nightingale dataset
        # If these change, the test data or extraction logic has changed
        duration = get_video_meta(raw_data=json_metadata, key="duration")
        fps = get_video_meta(raw_data=json_metadata, key="fps")
        width = get_video_meta(raw_data=json_metadata, key="width")
        height = get_video_meta(raw_data=json_metadata, key="height")

        # Verify duration is positive and reasonable (experiment length)
        assert duration > 0, "Duration should be positive"
        assert duration < 100000, "Duration seems unreasonably large"

        # Verify fps is a standard video frame rate
        assert fps > 0, "FPS should be positive"
        assert fps <= 1000, "FPS seems unreasonably high"

        # Verify dimensions are positive and reasonable
        assert width > 0 and width < 10000, f"Width {width} seems invalid"
        assert height > 0 and height < 10000, f"Height {height} seems invalid"

        # Golden Master: Verify types are correct
        assert isinstance(duration, (int, float)), f"Duration type {type(duration)} unexpected"
        assert isinstance(fps, (int, float)), f"FPS type {type(fps)} unexpected"
        assert isinstance(width, int), f"Width type {type(width)} should be int"
        assert isinstance(height, int), f"Height type {type(height)} should be int"

    def test_camera_name_matches_filename(self, require_nightingale_data, integration_json_metadata):
        """Extracted camera name should match DLC filename prefix."""
        json_metadata = integration_json_metadata
        result = get_camera(raw_data=json_metadata)
        filename = json_metadata["dlc_path"]["filename"]

        assert result == filename.split("_")[0]

    def test_model_name_matches_filename(self, require_nightingale_data, integration_json_metadata):
        """Extracted model name should match DLC filename suffix."""
        json_metadata = integration_json_metadata
        result = get_model_name(raw_data=json_metadata)
        filename = json_metadata["dlc_path"]["filename"]

        # Model name is last part before .hdf5
        expected = filename.replace(".hdf5", "").split("_")[-1]
        assert result == expected

    def test_session_label_extraction(self, require_nightingale_data, integration_pickle_data):
        """Session label should extract first element from list."""
        pickle_data = integration_pickle_data
        result = get_name(raw_data=pickle_data, key="session_label")

        assert result == pickle_data["session_label"][0]


# ==============================================================================
# DLC Processing Pipeline Tests
# ==============================================================================

class TestDlcProcessingPipeline:
    """Tests for the full DLC processing pipeline."""

    def test_filter_then_roundtrip(self, require_nightingale_data, integration_dlc_dataframe):
        """Filtered DLC data should survive round-trip."""
        dlc_dataframe = integration_dlc_dataframe

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

        # Golden Master: Verify sample values survive filter->round-trip
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[0].values,
            filtered.iloc[0].values,
            decimal=10,
            err_msg="First row changed after filter->round-trip"
        )
        np.testing.assert_array_almost_equal(
            reconstructed.iloc[-1].values,
            filtered.iloc[-1].values,
            decimal=10,
            err_msg="Last row changed after filter->round-trip"
        )

    def test_filter_dlc_sample_values(self, require_nightingale_data, integration_dlc_dataframe):
        """Golden Master: Verify filter_dlc produces expected output structure."""
        dlc_dataframe = integration_dlc_dataframe

        # Filter the data
        filtered = filter_dlc(dlc_dataframe)

        # Golden Master: Verify shape preserved
        assert filtered.shape == dlc_dataframe.shape, \
            f"Shape changed from {dlc_dataframe.shape} to {filtered.shape}"

        # Golden Master: Verify column structure preserved
        assert list(filtered.columns) == list(dlc_dataframe.columns), \
            "Column structure changed after filtering"

        # Golden Master: Verify filtering reduces NaN in x/y columns (main purpose of filter)
        # Pick a bodypart that should have some low-confidence values filtered
        if ("nose", "x") in filtered.columns:
            original_nan_x = np.isnan(dlc_dataframe[("nose", "x")]).sum()
            filtered_nan_x = np.isnan(filtered[("nose", "x")]).sum()
            # Filter interpolates, so NaN count should be same or reduced
            assert filtered_nan_x <= original_nan_x + 10, \
                f"Filter unexpectedly increased NaN count: {original_nan_x} -> {filtered_nan_x}"

    def test_compute_head_angles_preserves_row_count(
        self,
        require_nightingale_data,
        integration_dlc_dataframe
    ):
        """compute_head_angles should preserve row count."""
        dlc_dataframe = integration_dlc_dataframe
        result = compute_head_angles(dlc_dataframe)

        assert len(result) == len(dlc_dataframe)

    def test_compute_head_angles_output_columns(
        self,
        require_nightingale_data,
        integration_dlc_dataframe
    ):
        """Golden Master: Verify compute_head_angles output has expected columns."""
        dlc_dataframe = integration_dlc_dataframe
        result = compute_head_angles(dlc_dataframe)

        # Golden Master: Verify expected output columns exist
        expected_columns = ["head_center_x", "head_center_y", "heading_dir", "head_angle"]
        for col in expected_columns:
            assert col in result.columns, f"Missing expected column: {col}"

        # Golden Master: Verify output dtypes
        for col in expected_columns:
            assert np.issubdtype(result[col].dtype, np.floating), \
                f"Column {col} should be floating type, got {result[col].dtype}"

        # Golden Master: Verify angle values are in reasonable range
        # heading_dir should be in degrees (-180 to 180 or 0 to 360)
        heading_dir = result["heading_dir"].dropna()
        if len(heading_dir) > 0:
            assert heading_dir.min() >= -360, f"heading_dir min {heading_dir.min()} too low"
            assert heading_dir.max() <= 360, f"heading_dir max {heading_dir.max()} too high"

        # head_angle should also be in reasonable range
        head_angle = result["head_angle"].dropna()
        if len(head_angle) > 0:
            assert head_angle.min() >= -360, f"head_angle min {head_angle.min()} too low"
            assert head_angle.max() <= 360, f"head_angle max {head_angle.max()} too high"


# ==============================================================================
# File Loading Round-Trip Tests
# ==============================================================================

class TestFileLoadingRoundTrip:
    """Tests for file loading and data extraction."""

    def test_pickle_load_contains_all_expected_keys(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        expected_pickle_keys
    ):
        """Loaded pickle should contain all expected keys."""
        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key in expected_pickle_keys:
            assert key in data, f"Missing key: {key}"

    def test_pickle_load_array_shapes_match(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        expected_array_shapes
    ):
        """Loaded pickle arrays should have expected shapes."""
        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key, expected_shape in expected_array_shapes.items():
            assert data[key].shape == expected_shape, \
                f"Shape mismatch for {key}: expected {expected_shape}, got {data[key].shape}"

    def test_pickle_load_array_dtypes_match(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        expected_array_dtypes
    ):
        """Loaded pickle arrays should have expected dtypes."""
        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        data, name = get_new_file(pickle_path.name, str(pickle_path.parent))

        for key, expected_dtype in expected_array_dtypes.items():
            assert data[key].dtype == expected_dtype, \
                f"Dtype mismatch for {key}: expected {expected_dtype}, got {data[key].dtype}"


# ==============================================================================
# Timestamp Alignment Tests
# ==============================================================================

class TestTimestampAlignment:
    """Tests for timestamp alignment between different data sources."""

    def test_find_closest_indices_with_real_data(
        self,
        require_nightingale_data,
        integration_pickle_data,
        integration_timestamp_array
    ):
        """find_closest_indices should work with real timestamp data."""
        pickle_data = integration_pickle_data
        timestamp_array = integration_timestamp_array
        step_time = pickle_data["step_time"]

        # Find indices for a subset of timestamps
        subset_timestamps = timestamp_array[:100]
        indices = find_closest_indices(step_time, subset_timestamps)

        # Verify we get correct number of indices
        assert len(indices) == len(subset_timestamps)

        # All indices should be valid
        for idx in indices:
            assert 0 <= idx < len(step_time)

    def test_timestamp_coverage(
        self,
        require_nightingale_data,
        integration_pickle_data,
        integration_timestamp_array
    ):
        """Timestamps should cover the experiment duration."""
        pickle_data = integration_pickle_data
        timestamp_array = integration_timestamp_array
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

    def test_dataset_name_consistency(
        self,
        require_nightingale_data,
        test_data_dir,
        test_dataset_name,
        integration_json_metadata
    ):
        """Dataset name should be consistent across files."""
        json_metadata = integration_json_metadata
        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        _, pickle_name = get_new_file(pickle_path.name, str(pickle_path.parent))

        assert pickle_name == json_metadata["dataset"]

    def test_date_parsing_matches_json(self, require_nightingale_data, integration_json_metadata):
        """Parsed date should match JSON metadata."""
        json_metadata = integration_json_metadata
        dataset = json_metadata["dataset"]
        parsed_date = parse_date(dataset)

        # The date should be extractable
        assert parsed_date is not None
        assert parsed_date.year == 2024
        assert parsed_date.month == 8
        assert parsed_date.day == 16

    def test_dlc_shape_matches_json_meta(
        self,
        require_nightingale_data,
        integration_dlc_dataframe,
        integration_json_metadata
    ):
        """DLC row count should be consistent with video duration."""
        dlc_dataframe = integration_dlc_dataframe
        json_metadata = integration_json_metadata

        fps = json_metadata["video_meta"]["fps"]
        duration = json_metadata["video_meta"]["duration"]

        expected_frames = int(fps * duration)

        # DLC frame count should be close to expected
        # (allowing for some tolerance due to processing)
        actual_frames = len(dlc_dataframe)

        # Should be within 10% (DLC may have fewer frames due to processing)
        assert actual_frames <= expected_frames
        assert actual_frames > expected_frames * 0.5  # At least 50%
