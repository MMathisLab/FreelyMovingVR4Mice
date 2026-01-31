"""
Database integration tests for table population.

These tests require Docker to be running and will spin up a MySQL container.
They test the full populate_rig pipeline against a real database.

Run with: pytest integration/test_db_populate.py -v
"""

import os
import pickle
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

# DB fixtures are loaded automatically from conftest.py:
# - mysql_container: MySQL container instance
# - dj_config: DataJoint configuration connected to test DB
# - clean_schemas: Ensures clean schemas per test
# - test_data_dir: Path to test data
# - test_dataset_name: Name of test dataset


# ==============================================================================
# Schema Import Tests
# ==============================================================================

class TestSchemaCreation:
    """Tests for schema/table creation on import."""

    def test_vr4mice_schema_creates_tables(self, dj_config):
        """Importing vr4mice schema should create tables."""
        import datajoint as dj
        from vr4mice.schema import vr4mice

        # Check that tables were created
        assert hasattr(vr4mice, 'Dataset')
        assert hasattr(vr4mice, 'Camera')
        assert hasattr(vr4mice, 'Video')
        assert hasattr(vr4mice, 'DLC')
        assert hasattr(vr4mice, 'MouseState')

    def test_schema_has_correct_prefix(self, dj_config):
        """Schema should use test_ prefix."""
        import datajoint as dj

        schemas = dj.list_schemas()
        test_schemas = [s for s in schemas if s.startswith("test_")]

        assert len(test_schemas) > 0, "No test schemas created"

    def test_lookup_tables_have_contents(self, dj_config):
        """Lookup tables should be populated with default contents."""
        from vr4mice.schema import vr4mice

        # Camera lookup should have default contents
        cameras = vr4mice.Camera().fetch()
        assert len(cameras) > 0

        # ModelName lookup should have default contents
        models = vr4mice.ModelName().fetch()
        assert len(models) > 0

        # Golden Master: Verify expected lookup values exist
        # These are the values used in the Nightingale golden dataset
        camera_names = vr4mice.Camera().fetch("camera")
        assert "Imagingsource" in camera_names, "Expected camera 'Imagingsource' not found"

        model_names = vr4mice.ModelName().fetch("model_name")
        assert "DLC" in model_names, "Expected model 'DLC' not found"


# ==============================================================================
# Dataset Population Tests
# ==============================================================================

class TestDatasetPopulation:
    """Tests for populating Dataset table."""

    @pytest.fixture
    def prepared_test_data(self, test_data_dir, test_dataset_name, tmp_path):
        """
        Prepare test data in a temporary directory structure expected by populate_rig.

        populate_rig expects files in /data/data by default, but we'll override the path.
        """
        # Create data directory structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Copy pickle file
        src_pickle = test_data_dir / f"{test_dataset_name}.pickle"
        dst_pickle = data_dir / f"{test_dataset_name}.pickle"
        shutil.copy(src_pickle, dst_pickle)

        # Copy JSON file (if needed)
        src_json = test_data_dir / f"{test_dataset_name}.json"
        if src_json.exists():
            dst_json = data_dir / f"{test_dataset_name}.json"
            shutil.copy(src_json, dst_json)

        return {
            "data_dir": data_dir,
            "pickle_path": dst_pickle,
            "dataset_name": test_dataset_name,
        }

    def test_manual_dataset_insert(self, dj_config, prepared_test_data):
        """Test manually inserting a dataset entry."""
        from vr4mice.schema import vr4mice

        dataset_name = prepared_test_data["dataset_name"]

        # Manually insert dataset
        entry = {
            "dataset": dataset_name,
            "exp_teensy_filepath": str(prepared_test_data["pickle_path"]),
            "exp_session_filepath": "none",
            "session_label": "ar_discrim_5_occluders",
        }

        vr4mice.Dataset.insert1(entry, skip_duplicates=True)

        # Verify insertion
        result = (vr4mice.Dataset & f'dataset="{dataset_name}"').fetch(as_dict=True)
        assert len(result) == 1
        assert result[0]["dataset"] == dataset_name

    def test_dataset_fetch_after_insert(self, dj_config, prepared_test_data):
        """Test fetching dataset after insertion."""
        from vr4mice.schema import vr4mice

        dataset_name = prepared_test_data["dataset_name"]

        # Insert
        entry = {
            "dataset": dataset_name,
            "exp_teensy_filepath": str(prepared_test_data["pickle_path"]),
            "exp_session_filepath": "none",
            "session_label": "test_label",
        }
        vr4mice.Dataset.insert1(entry, skip_duplicates=True)

        # Fetch all datasets
        datasets = vr4mice.Dataset().fetch("dataset")
        assert dataset_name in datasets


# ==============================================================================
# MouseState Population Tests
# ==============================================================================

class TestMouseStatePopulation:
    """Tests for populating MouseState table with real data."""

    @pytest.fixture
    def pickle_data(self, test_data_dir, test_dataset_name):
        """Load real pickle data."""
        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        with open(pickle_path, "rb") as f:
            return pickle.load(f)

    def test_mousestate_insert_from_pickle(self, dj_config, pickle_data, test_dataset_name):
        """Test inserting MouseState data extracted from pickle."""
        from vr4mice.schema import vr4mice
        from helpers_dj import get_state

        # First insert dataset (required foreign key)
        dataset_entry = {
            "dataset": test_dataset_name,
            "exp_teensy_filepath": "test.pickle",
            "exp_session_filepath": "none",
            "session_label": "test",
        }
        vr4mice.Dataset.insert1(dataset_entry, skip_duplicates=True)

        # Extract state data using helper
        mouse_state_entry = {
            "dataset": test_dataset_name,
            "x_pos": get_state(raw_data=pickle_data, key="x_pos"),
            "z_pos": get_state(raw_data=pickle_data, key="z_pos"),
            "head_dir": get_state(raw_data=pickle_data, key="head_dir"),
            "mouse_can_report": get_state(raw_data=pickle_data, key="mouse_can_report"),
            "iti": get_state(raw_data=pickle_data, key="iti"),
            "obj_left": get_state(raw_data=pickle_data, key="obj_left"),
            "mouse_report_correct": get_state(raw_data=pickle_data, key="mouse_report_correct"),
            "report_left": get_state(raw_data=pickle_data, key="report_left"),
            "report_right": get_state(raw_data=pickle_data, key="report_right"),
            "velocity": get_state(raw_data=pickle_data, key="velocity"),
        }

        # Insert
        vr4mice.MouseState.insert1(mouse_state_entry, skip_duplicates=True)

        # Verify
        result = (vr4mice.MouseState & f'dataset="{test_dataset_name}"').fetch(as_dict=True)
        assert len(result) == 1

        # Verify data integrity - length
        fetched_x_pos = np.array(result[0]["x_pos"])
        assert len(fetched_x_pos) == 339045  # Expected length

        # Golden Master: Verify sample values from fetched data
        # These are specific values from the Nightingale golden dataset
        original_x_pos = np.array(get_state(raw_data=pickle_data, key="x_pos"))

        # Check first 5 values match
        np.testing.assert_array_almost_equal(
            fetched_x_pos[:5], original_x_pos[:5], decimal=6,
            err_msg="First 5 x_pos values don't match after DB round-trip"
        )

        # Check last 5 values match
        np.testing.assert_array_almost_equal(
            fetched_x_pos[-5:], original_x_pos[-5:], decimal=6,
            err_msg="Last 5 x_pos values don't match after DB round-trip"
        )

        # Verify dtype is preserved (or compatible floating type)
        assert np.issubdtype(fetched_x_pos.dtype, np.floating), \
            f"fetched x_pos should be floating type, got {fetched_x_pos.dtype}"

    def test_mousestate_data_roundtrip(self, dj_config, pickle_data, test_dataset_name):
        """Test that MouseState data survives database round-trip."""
        from vr4mice.schema import vr4mice
        from helpers_dj import get_state

        # Insert dataset
        vr4mice.Dataset.insert1({
            "dataset": test_dataset_name,
            "exp_teensy_filepath": "test.pickle",
            "exp_session_filepath": "none",
            "session_label": "test",
        }, skip_duplicates=True)

        # Original data (convert to numpy arrays for later comparison)
        original_x_pos = np.array(get_state(raw_data=pickle_data, key="x_pos"))
        original_velocity = np.array(get_state(raw_data=pickle_data, key="velocity"))

        # Insert MouseState
        vr4mice.MouseState.insert1({
            "dataset": test_dataset_name,
            "x_pos": original_x_pos,
            "z_pos": get_state(raw_data=pickle_data, key="z_pos"),
            "head_dir": get_state(raw_data=pickle_data, key="head_dir"),
            "mouse_can_report": get_state(raw_data=pickle_data, key="mouse_can_report"),
            "iti": get_state(raw_data=pickle_data, key="iti"),
            "obj_left": get_state(raw_data=pickle_data, key="obj_left"),
            "mouse_report_correct": get_state(raw_data=pickle_data, key="mouse_report_correct"),
            "report_left": get_state(raw_data=pickle_data, key="report_left"),
            "report_right": get_state(raw_data=pickle_data, key="report_right"),
            "velocity": original_velocity,
        }, skip_duplicates=True)

        # Fetch back
        result = (vr4mice.MouseState & f'dataset="{test_dataset_name}"').fetch1()

        # Compare (convert to numpy arrays for comparison)
        fetched_x_pos = np.array(result["x_pos"])
        fetched_velocity = np.array(result["velocity"])

        # Golden Baseline: Full array comparison
        assert np.allclose(fetched_x_pos, original_x_pos, equal_nan=True), \
            "x_pos arrays don't match after round-trip"
        assert np.allclose(fetched_velocity, original_velocity, equal_nan=True), \
            "velocity arrays don't match after round-trip"

        # Golden Baseline: Verify shapes preserved
        assert fetched_x_pos.shape == original_x_pos.shape, \
            f"x_pos shape mismatch: {fetched_x_pos.shape} vs {original_x_pos.shape}"
        assert fetched_velocity.shape == original_velocity.shape, \
            f"velocity shape mismatch: {fetched_velocity.shape} vs {original_velocity.shape}"

        # Golden Baseline: Verify dtypes preserved (or compatible)
        # Note: DB may return different but compatible dtype, so check values instead
        assert np.issubdtype(fetched_x_pos.dtype, np.floating), \
            f"x_pos dtype should be floating, got {fetched_x_pos.dtype}"
        assert np.issubdtype(fetched_velocity.dtype, np.floating), \
            f"velocity dtype should be floating, got {fetched_velocity.dtype}"

        # Golden Baseline: Verify statistical properties preserved
        assert np.nanmean(fetched_x_pos) == pytest.approx(np.nanmean(original_x_pos), rel=1e-6), \
            "x_pos mean changed after round-trip"
        assert np.nanstd(fetched_x_pos) == pytest.approx(np.nanstd(original_x_pos), rel=1e-6), \
            "x_pos std changed after round-trip"
        assert np.nanmean(fetched_velocity) == pytest.approx(np.nanmean(original_velocity), rel=1e-6), \
            "velocity mean changed after round-trip"


# ==============================================================================
# Video Table Population Tests
# ==============================================================================

class TestVideoPopulation:
    """Tests for Video table population."""

    def test_video_insert(self, dj_config, test_dataset_name):
        """Test inserting Video entry."""
        from vr4mice.schema import vr4mice
        from datetime import date

        # Insert required parent tables
        vr4mice.Dataset.insert1({
            "dataset": test_dataset_name,
            "exp_teensy_filepath": "test.pickle",
            "exp_session_filepath": "none",
            "session_label": "test",
        }, skip_duplicates=True)

        # Insert Video
        video_entry = {
            "dataset": test_dataset_name,
            "camera": "Imagingsource",
            "doe": date(2024, 8, 16),
            "duration": 4560,
            "fps": 100,
            "width": 530,
            "height": 510,
            "video_filepath": "/path/to/video.avi",
            "timestamp_filepath": "/path/to/timestamps.npy",
        }

        vr4mice.Video.insert1(video_entry, skip_duplicates=True)

        # Verify
        result = (vr4mice.Video & f'dataset="{test_dataset_name}"').fetch(as_dict=True)
        assert len(result) == 1
        assert result[0]["fps"] == 100


# ==============================================================================
# DLC Table Population Tests
# ==============================================================================

class TestDLCPopulation:
    """Tests for DLC table population."""

    def test_dlc_insert(self, dj_config, test_dataset_name):
        """Test inserting DLC entry."""
        from vr4mice.schema import vr4mice
        from datetime import date

        # Insert required parent tables
        vr4mice.Dataset.insert1({
            "dataset": test_dataset_name,
            "exp_teensy_filepath": "test.pickle",
            "exp_session_filepath": "none",
            "session_label": "test",
        }, skip_duplicates=True)

        vr4mice.Video.insert1({
            "dataset": test_dataset_name,
            "camera": "Imagingsource",
            "doe": date(2024, 8, 16),
        }, skip_duplicates=True)

        # Insert DLC
        dlc_entry = {
            "dataset": test_dataset_name,
            "camera": "Imagingsource",
            "doe": date(2024, 8, 16),
            "model_name": "DLC",
            "keypoints_filepath": "/path/to/keypoints.hdf5",
            "proc_filepath": "/path/to/proc",
        }

        vr4mice.DLC.insert1(dlc_entry, skip_duplicates=True)

        # Verify
        result = (vr4mice.DLC & f'dataset="{test_dataset_name}"').fetch(as_dict=True)
        assert len(result) == 1


# ==============================================================================
# Full Pipeline Tests
# ==============================================================================

class TestFullPipeline:
    """Tests for the complete data population pipeline."""

    @pytest.fixture
    def full_test_data(self, test_data_dir, test_dataset_name):
        """Load all test data files."""
        import json

        pickle_path = test_data_dir / f"{test_dataset_name}.pickle"
        json_path = test_data_dir / f"{test_dataset_name}.json"

        with open(pickle_path, "rb") as f:
            pickle_data = pickle.load(f)

        with open(json_path, "r") as f:
            json_data = json.load(f)

        return {
            "pickle_data": pickle_data,
            "json_data": json_data,
            "dataset_name": test_dataset_name,
        }

    def test_full_dataset_to_mousestate_pipeline(self, dj_config, full_test_data):
        """Test complete pipeline: Dataset -> MouseState -> State."""
        from vr4mice.schema import vr4mice
        from helpers_dj import get_state

        dataset_name = full_test_data["dataset_name"]
        pickle_data = full_test_data["pickle_data"]

        # 1. Insert Dataset
        vr4mice.Dataset.insert1({
            "dataset": dataset_name,
            "exp_teensy_filepath": "test.pickle",
            "exp_session_filepath": "none",
            "session_label": pickle_data["session_label"][0],
        }, skip_duplicates=True)

        # 2. Insert MouseState
        vr4mice.MouseState.insert1({
            "dataset": dataset_name,
            "x_pos": get_state(raw_data=pickle_data, key="x_pos"),
            "z_pos": get_state(raw_data=pickle_data, key="z_pos"),
            "head_dir": get_state(raw_data=pickle_data, key="head_dir"),
            "mouse_can_report": get_state(raw_data=pickle_data, key="mouse_can_report"),
            "iti": get_state(raw_data=pickle_data, key="iti"),
            "obj_left": get_state(raw_data=pickle_data, key="obj_left"),
            "mouse_report_correct": get_state(raw_data=pickle_data, key="mouse_report_correct"),
            "report_left": get_state(raw_data=pickle_data, key="report_left"),
            "report_right": get_state(raw_data=pickle_data, key="report_right"),
            "velocity": get_state(raw_data=pickle_data, key="velocity"),
        }, skip_duplicates=True)

        # 3. Insert State
        vr4mice.State.insert1({
            "dataset": dataset_name,
            "start_time": pickle_data["start_time"],
            "episode": pickle_data["episode"],
            "step": pickle_data["step"],
            "step_time": pickle_data["step_time"],
            "action": pickle_data["action"],
            "reward": pickle_data["reward"],
            "terminal": pickle_data["terminal"],
            "dlc_read_time": pickle_data.get("dlc_read_time"),
            "dlc_x": pickle_data["dlc_x"],
            "dlc_y": pickle_data["dlc_y"],
            "dlc_heading": pickle_data["dlc_heading"],
        }, skip_duplicates=True)

        # Verify all tables populated
        assert len(vr4mice.Dataset()) == 1
        assert len(vr4mice.MouseState()) == 1
        assert len(vr4mice.State()) == 1

        # Verify data integrity - length
        state_result = vr4mice.State.fetch1()
        assert len(state_result["episode"]) == 339045

        # Golden Baseline: Verify State table round-trip preserves values
        # Compare episode array
        fetched_episode = np.array(state_result["episode"])
        original_episode = pickle_data["episode"]
        np.testing.assert_array_equal(
            fetched_episode[:10], original_episode[:10],
            err_msg="First 10 episode values don't match"
        )
        np.testing.assert_array_equal(
            fetched_episode[-10:], original_episode[-10:],
            err_msg="Last 10 episode values don't match"
        )

        # Compare step_time array
        fetched_step_time = np.array(state_result["step_time"])
        original_step_time = pickle_data["step_time"]
        np.testing.assert_array_almost_equal(
            fetched_step_time[:10], original_step_time[:10], decimal=6,
            err_msg="First 10 step_time values don't match"
        )

        # Compare reward array
        fetched_reward = np.array(state_result["reward"])
        original_reward = pickle_data["reward"]
        np.testing.assert_array_almost_equal(
            fetched_reward[:10], original_reward[:10], decimal=6,
            err_msg="First 10 reward values don't match"
        )

        # Verify MouseState round-trip
        mousestate_result = vr4mice.MouseState.fetch1()
        fetched_x_pos = np.array(mousestate_result["x_pos"])
        original_x_pos = np.array(get_state(raw_data=pickle_data, key="x_pos"))

        assert fetched_x_pos.shape == original_x_pos.shape, \
            f"MouseState x_pos shape mismatch: {fetched_x_pos.shape} vs {original_x_pos.shape}"
        np.testing.assert_array_almost_equal(
            fetched_x_pos[:10], original_x_pos[:10], decimal=6,
            err_msg="MouseState x_pos first 10 values don't match"
        )
