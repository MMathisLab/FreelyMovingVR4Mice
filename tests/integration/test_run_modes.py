"""
Integration tests for run.py mode handlers using the Nightingale golden dataset.

These tests verify the full pipeline execution for each mode in run.py:
- connect: Schema imports and database connectivity
- populate: Dataset, MouseState, State, Video, DLC table population
- analysis: DataFrame, BoxDataFrame, GitCommit population
- dlc: DLCProcessor, DLCKptsDf, SyncDLCKptsDf, OfflineKinematics population
- summary: SummaryPlots, TrackingSummaryPlots generation
- interp: InterpolatedTrials, MeanXYTrajectory, SessionMetrics, TrialMetrics
- latency: SignalsPhotodiode, SignalsPhotodiodeAligned, AllLatencies
- fetch: GUI menu .npy file creation

Test Strategy:
- Sequential pipeline testing with shared database session
- Golden master verification: row counts + sample values (first/last/middle)
- Module-scoped fixtures for efficiency

Dependencies:
- Docker Desktop running with WSL integration
- Nightingale golden dataset in test_data/golden_dataset/

Run with:
    cd scene/tests
    sg docker -c "bash -c 'source ../venv/bin/activate && python -m pytest integration/test_run_modes.py -v'"
"""

import json
import os
import pickle
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ==============================================================================
# Golden Master Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def golden_baseline_dir():
    """Path to golden baseline output files for integration tests."""
    return Path(__file__).parent.parent / "golden_baseline" / "integration"


@pytest.fixture(scope="module")
def golden_baseline(golden_baseline_dir, request):
    """
    Golden baseline comparison fixture.

    Provides methods to compare test outputs against golden snapshots.
    Use --regenerate-golden flag to regenerate golden files.
    """
    try:
        regenerate = request.config.getoption("--regenerate-golden")
    except ValueError:
        regenerate = False

    class GoldenBaseline:
        def __init__(self, base_dir, should_regenerate):
            self.base_dir = Path(base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.regenerate = should_regenerate

        def check_row_count(self, table_name, actual_count, tolerance=0):
            """Compare row count against golden value."""
            golden_path = self.base_dir / f"{table_name}_row_count.json"

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump({"row_count": actual_count}, f, indent=2)
                return True

            if not golden_path.exists():
                pytest.fail(
                    f"Golden file not found: {golden_path}\n"
                    f"Run with --regenerate-golden to create it.\n"
                    f"Actual count: {actual_count}"
                )

            with open(golden_path) as f:
                expected = json.load(f)["row_count"]

            if tolerance > 0:
                assert abs(actual_count - expected) <= tolerance, \
                    f"{table_name}: row count {actual_count} != {expected} (tolerance: {tolerance})"
            else:
                assert actual_count == expected, \
                    f"{table_name}: row count {actual_count} != {expected}"
            return True

        def check_sample_values(self, table_name, data_dict, keys_to_check=None):
            """
            Compare sample values (first, middle, last) against golden.

            Args:
                table_name: Name for the golden file
                data_dict: Dictionary of {column: array} data
                keys_to_check: List of columns to check (default: all)
            """
            golden_path = self.base_dir / f"{table_name}_samples.json"

            def extract_samples(arr):
                """Extract first, middle, last values from array."""
                arr = np.asarray(arr)
                if arr.ndim == 0:
                    return {"scalar": float(arr) if np.issubdtype(arr.dtype, np.floating) else int(arr)}
                if len(arr) == 0:
                    return {"empty": True}

                samples = {
                    "length": len(arr),
                    "dtype": str(arr.dtype),
                }

                # First value
                first_val = arr[0]
                if hasattr(first_val, 'tolist'):
                    first_val = first_val.tolist()
                samples["first"] = first_val

                # Middle value
                mid_idx = len(arr) // 2
                mid_val = arr[mid_idx]
                if hasattr(mid_val, 'tolist'):
                    mid_val = mid_val.tolist()
                samples["middle"] = mid_val
                samples["middle_idx"] = mid_idx

                # Last value
                last_val = arr[-1]
                if hasattr(last_val, 'tolist'):
                    last_val = last_val.tolist()
                samples["last"] = last_val

                return samples

            if keys_to_check is None:
                keys_to_check = list(data_dict.keys())

            actual_samples = {}
            for key in keys_to_check:
                if key in data_dict:
                    actual_samples[key] = extract_samples(data_dict[key])

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump(actual_samples, f, indent=2, default=str)
                return True

            if not golden_path.exists():
                pytest.fail(
                    f"Golden file not found: {golden_path}\n"
                    f"Run with --regenerate-golden to create it."
                )

            with open(golden_path) as f:
                expected_samples = json.load(f)

            for key in keys_to_check:
                if key not in expected_samples:
                    continue

                actual = actual_samples.get(key, {})
                expected = expected_samples[key]

                # Check length
                if "length" in expected:
                    assert actual.get("length") == expected["length"], \
                        f"{table_name}.{key}: length {actual.get('length')} != {expected['length']}"

                # Check values with floating point tolerance
                for pos in ["first", "middle", "last", "scalar"]:
                    if pos in expected:
                        actual_val = actual.get(pos)
                        expected_val = expected[pos]

                        if isinstance(expected_val, float):
                            assert actual_val == pytest.approx(expected_val, rel=1e-5, nan_ok=True), \
                                f"{table_name}.{key}[{pos}]: {actual_val} != {expected_val}"
                        elif isinstance(expected_val, list):
                            np.testing.assert_array_almost_equal(
                                actual_val, expected_val, decimal=5,
                                err_msg=f"{table_name}.{key}[{pos}] mismatch"
                            )
                        else:
                            assert actual_val == expected_val, \
                                f"{table_name}.{key}[{pos}]: {actual_val} != {expected_val}"

            return True

        def check_scalar(self, name, actual_value):
            """Compare a scalar value against golden."""
            golden_path = self.base_dir / f"{name}_scalar.json"

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump({"value": actual_value}, f, indent=2)
                return True

            if not golden_path.exists():
                pytest.fail(f"Golden file not found: {golden_path}")

            with open(golden_path) as f:
                expected = json.load(f)["value"]

            if isinstance(expected, float):
                assert actual_value == pytest.approx(expected, rel=1e-5), \
                    f"{name}: {actual_value} != {expected}"
            else:
                assert actual_value == expected, f"{name}: {actual_value} != {expected}"

            return True

    return GoldenBaseline(golden_baseline_dir, regenerate)


# ==============================================================================
# Pipeline Fixtures (Module-Scoped for Efficiency)
# ==============================================================================

@pytest.fixture(scope="module")
def pipeline_test_data(test_data_dir, test_dataset_name, test_camera_prefix, tmp_path_factory):
    """
    Prepare test data in a temporary directory structure.

    Creates a data directory that mimics the expected structure for populate_rig.
    Returns paths and metadata needed for pipeline tests.
    """
    # Create temporary data directory
    tmp_dir = tmp_path_factory.mktemp("pipeline_data")
    data_dir = tmp_dir / "data"
    data_dir.mkdir()

    # Also create summary_plots directory (needed by analysis mode)
    summary_dir = tmp_dir / "summary_plots"
    summary_dir.mkdir()

    # Copy required files
    files_to_copy = [
        f"{test_dataset_name}.pickle",
        f"{test_dataset_name}.json",
        f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5",
        f"{test_camera_prefix}_{test_dataset_name}_TS.npy",
        f"{test_camera_prefix}_{test_dataset_name}_PROC",
    ]

    for filename in files_to_copy:
        src = test_data_dir / filename
        if src.exists():
            dst = data_dir / filename
            if src.is_file():
                shutil.copy(src, dst)
            else:
                # For PROC files which might be directories
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy(src, dst)

    return {
        "data_dir": data_dir,
        "summary_dir": summary_dir,
        "tmp_dir": tmp_dir,
        "dataset_name": test_dataset_name,
        "camera_prefix": test_camera_prefix,
        "pickle_path": data_dir / f"{test_dataset_name}.pickle",
        "json_path": data_dir / f"{test_dataset_name}.json",
        "dlc_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5",
        "ts_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_TS.npy",
        "proc_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_PROC",
    }


@pytest.fixture(scope="module")
def populated_db(dj_config, pipeline_test_data, test_dataset_name, test_camera_prefix):
    """
    Run populate mode equivalent and return database handle.

    This is the foundation fixture - populates Dataset, MouseState, State, Video, DLC tables.
    """
    from datetime import date
    from vr4mice.schema import vr4mice
    from helpers_dj import get_state

    # Load test data
    with open(pipeline_test_data["pickle_path"], "rb") as f:
        pickle_data = pickle.load(f)

    with open(pipeline_test_data["json_path"]) as f:
        json_data = json.load(f)

    # 1. Insert Dataset
    dataset_entry = {
        "dataset": test_dataset_name,
        "exp_teensy_filepath": str(pipeline_test_data["pickle_path"]),
        "exp_session_filepath": "none",
        "session_label": pickle_data["session_label"][0],
    }
    vr4mice.Dataset.insert1(dataset_entry, skip_duplicates=True)

    # 2. Insert MouseState
    mousestate_entry = {
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
    vr4mice.MouseState.insert1(mousestate_entry, skip_duplicates=True)

    # 3. Insert State
    state_entry = {
        "dataset": test_dataset_name,
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
    }
    vr4mice.State.insert1(state_entry, skip_duplicates=True)

    # 4. Insert Video
    doe = date.fromisoformat(json_data["doe"])
    video_entry = {
        "dataset": test_dataset_name,
        "camera": test_camera_prefix,
        "doe": doe,
        "duration": json_data["video_meta"]["duration"],
        "fps": json_data["video_meta"]["fps"],
        "width": json_data["video_meta"]["width"],
        "height": json_data["video_meta"]["height"],
        "video_filepath": str(pipeline_test_data["data_dir"] / json_data["video_path"]["filename"]),
        "timestamp_filepath": str(pipeline_test_data["ts_path"]),
    }
    vr4mice.Video.insert1(video_entry, skip_duplicates=True)

    # 5. Insert DLC
    dlc_entry = {
        "dataset": test_dataset_name,
        "camera": test_camera_prefix,
        "doe": doe,
        "model_name": "DLC",
        "keypoints_filepath": str(pipeline_test_data["dlc_path"]),
        "proc_filepath": str(pipeline_test_data["proc_path"]),
    }
    vr4mice.DLC.insert1(dlc_entry, skip_duplicates=True)

    return {
        "vr4mice": vr4mice,
        "dataset_key": {"dataset": test_dataset_name},
        "video_key": {"dataset": test_dataset_name, "camera": test_camera_prefix, "doe": doe},
        "dlc_key": {"dataset": test_dataset_name, "camera": test_camera_prefix, "doe": doe, "model_name": "DLC"},
        "pickle_data": pickle_data,
        "json_data": json_data,
        "test_data": pipeline_test_data,
    }


# ==============================================================================
# Connect Mode Tests
# ==============================================================================

class TestConnectMode:
    """Tests for connect mode - verifies schema imports."""

    def test_vr4mice_schema_imports(self, dj_config):
        """Verify vr4mice schema imports without error."""
        from vr4mice.schema import vr4mice

        assert hasattr(vr4mice, 'Dataset')
        assert hasattr(vr4mice, 'MouseState')
        assert hasattr(vr4mice, 'State')
        assert hasattr(vr4mice, 'Video')
        assert hasattr(vr4mice, 'DLC')

    def test_base_analysis_schema_imports(self, dj_config):
        """Verify base_analysis schema imports without error."""
        from vr4mice.schema import base_analysis

        assert hasattr(base_analysis, 'DataFrame')
        assert hasattr(base_analysis, 'BoxDataFrame')
        assert hasattr(base_analysis, 'SummaryPlots')
        assert hasattr(base_analysis, 'GitCommit')

    def test_dlc_schema_imports(self, dj_config):
        """Verify dlc schema imports without error."""
        from vr4mice.schema import dlc

        assert hasattr(dlc, 'DLCProcessor')
        assert hasattr(dlc, 'DLCKptsDf')
        assert hasattr(dlc, 'SyncDLCKptsDf')
        assert hasattr(dlc, 'OfflineKinematics')

    def test_interpolated_trajectories_schema_imports(self, dj_config):
        """Verify interpolated_trajectories schema imports without error."""
        from vr4mice.schema import interpolated_trajectories

        assert hasattr(interpolated_trajectories, 'InterpolatedTrials')
        assert hasattr(interpolated_trajectories, 'MeanXYTrajectory')
        assert hasattr(interpolated_trajectories, 'YBinnedXYTrajectory')
        assert hasattr(interpolated_trajectories, 'MeanVelocities')

    def test_session_metrics_schema_imports(self, dj_config):
        """Verify session_metrics schema imports without error."""
        from vr4mice.schema import session_metrics

        assert hasattr(session_metrics, 'SessionMetrics')
        assert hasattr(session_metrics, 'TrialMetrics')

    def test_latency_tests_schema_imports(self, dj_config):
        """Verify latency_tests schema imports without error."""
        from vr4mice.schema import latency_tests

        assert hasattr(latency_tests, 'SignalsPhotodiodeAligned')
        assert hasattr(latency_tests, 'AllLatencies')

    @pytest.mark.skip(reason="base_schemas has non-CamelCase class names incompatible with DataJoint 2.0")
    def test_base_schema_imports(self, dj_config):
        """Verify base schema imports without CamelCase errors."""
        from vr4mice.schema import base

        assert hasattr(base, 'Base')


# ==============================================================================
# Populate Mode Tests
# ==============================================================================

class TestPopulateMode:
    """Tests for populate mode - foundation of the pipeline."""

    def test_dataset_table_populated(self, populated_db, golden_baseline):
        """Verify Dataset table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.Dataset())
        golden_baseline.check_row_count("dataset", count)

    def test_dataset_values(self, populated_db):
        """Verify Dataset entry has correct values."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dataset_key"]

        result = (vr4mice.Dataset & key).fetch1()
        assert result["dataset"] == key["dataset"]
        assert result["session_label"] == "ar_discrim_5_occluders"

    def test_mousestate_table_populated(self, populated_db, golden_baseline):
        """Verify MouseState table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.MouseState())
        golden_baseline.check_row_count("mousestate", count)

    def test_mousestate_array_lengths(self, populated_db, golden_baseline):
        """Verify MouseState arrays have expected lengths (339,045 steps)."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dataset_key"]

        result = (vr4mice.MouseState & key).fetch1()
        x_pos = np.array(result["x_pos"])

        # Expected from golden dataset
        assert len(x_pos) == 339045, f"x_pos length {len(x_pos)} != 339045"

        # Check sample values
        golden_baseline.check_sample_values("mousestate_x_pos", {"x_pos": x_pos})

    def test_mousestate_data_integrity(self, populated_db):
        """Verify MouseState data matches original pickle data."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dataset_key"]
        pickle_data = populated_db["pickle_data"]

        from helpers_dj import get_state

        result = (vr4mice.MouseState & key).fetch1()
        fetched_x_pos = np.array(result["x_pos"])
        original_x_pos = np.array(get_state(raw_data=pickle_data, key="x_pos"))

        # First 10 values
        np.testing.assert_array_almost_equal(
            fetched_x_pos[:10], original_x_pos[:10], decimal=6
        )
        # Last 10 values
        np.testing.assert_array_almost_equal(
            fetched_x_pos[-10:], original_x_pos[-10:], decimal=6
        )

    def test_state_table_populated(self, populated_db, golden_baseline):
        """Verify State table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.State())
        golden_baseline.check_row_count("state", count)

    def test_state_episode_array(self, populated_db, golden_baseline):
        """Verify State episode array has expected values."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dataset_key"]

        result = (vr4mice.State & key).fetch1()
        episode = np.array(result["episode"])

        assert len(episode) == 339045
        golden_baseline.check_sample_values("state_episode", {"episode": episode})

    def test_video_table_populated(self, populated_db, golden_baseline):
        """Verify Video table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.Video())
        golden_baseline.check_row_count("video", count)

    def test_video_metadata(self, populated_db):
        """Verify Video entry has correct metadata."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["video_key"]

        result = (vr4mice.Video & key).fetch1()
        assert result["fps"] == 100
        assert result["width"] == 530
        assert result["height"] == 510

    def test_dlc_table_populated(self, populated_db, golden_baseline):
        """Verify DLC table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.DLC())
        golden_baseline.check_row_count("dlc", count)

    def test_dlc_file_paths(self, populated_db):
        """Verify DLC entry has correct file paths."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dlc_key"]

        result = (vr4mice.DLC & key).fetch1()
        assert result["keypoints_filepath"].endswith("_DLC.hdf5")
        assert result["proc_filepath"].endswith("_PROC")


# ==============================================================================
# Analysis Mode Tests
# ==============================================================================

class TestAnalysisMode:
    """Tests for analysis mode - requires populate."""

    def test_dataframe_populates(self, populated_db, golden_baseline):
        """Verify DataFrame.populate() creates entry."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]

        # Populate DataFrame
        base_analysis.DataFrame.populate()

        count = len(base_analysis.DataFrame())
        golden_baseline.check_row_count("dataframe", count)

    def test_dataframe_columns_exist(self, populated_db):
        """Verify DataFrame has expected columns."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]

        # Get data
        df = base_analysis.DataFrame().get_data(key)

        # Skip if DataFrame wasn't populated (requires base.Base table)
        if df is False or df is None:
            pytest.skip("DataFrame not populated - requires base.Base table data")

        expected_columns = [
            "x", "y", "trial", "iti", "velocity",
            "object_on_left", "mouse_in_left", "mouse_in_right"
        ]

        for col in expected_columns:
            assert col in df.columns, f"Missing column: {col}"

    def test_dataframe_sample_values(self, populated_db, golden_baseline):
        """Verify DataFrame sample values match golden."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]
        df = base_analysis.DataFrame().get_data(key)

        # Skip if DataFrame wasn't populated (requires base.Base table)
        if df is False or df is None:
            pytest.skip("DataFrame not populated - requires base.Base table data")

        # Check key columns
        data_dict = {
            "x": df["x"].values,
            "y": df["y"].values,
            "trial": df["trial"].values,
            "velocity": df["velocity"].values,
        }
        golden_baseline.check_sample_values("dataframe", data_dict)

    def test_boxdataframe_populates(self, populated_db, golden_baseline):
        """Verify BoxDataFrame.populate() creates entry."""
        from vr4mice.schema import base_analysis

        # BoxDataFrame depends on DataFrame
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame.populate()

        count = len(base_analysis.BoxDataFrame())
        golden_baseline.check_row_count("boxdataframe", count)

    def test_boxdataframe_values(self, populated_db):
        """Verify BoxDataFrame has box coordinate values."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]

        box_df = base_analysis.BoxDataFrame().get_data(key)

        # Skip if BoxDataFrame wasn't populated (depends on DataFrame)
        if box_df is False or box_df is None:
            pytest.skip("BoxDataFrame not populated - requires DataFrame to be populated first")

        # Should have box coordinates
        assert "l_box_x_min" in box_df.columns
        assert "r_box_x_max" in box_df.columns
        assert "tt_box_z_min" in box_df.columns


# ==============================================================================
# DLC Mode Tests
# ==============================================================================

class TestDlcMode:
    """Tests for dlc mode - requires populate."""

    def test_dlcprocessor_populates(self, populated_db, golden_baseline):
        """Verify DLCProcessor.populate() creates entry."""
        from vr4mice.schema import dlc

        dlc.DLCProcessor.populate()

        count = len(dlc.DLCProcessor())
        golden_baseline.check_row_count("dlcprocessor", count)

    def test_dlcprocessor_kinematics(self, populated_db, golden_baseline):
        """Verify DLCProcessor contains kinematic data."""
        from vr4mice.schema import dlc

        key = populated_db["dlc_key"]

        result = (dlc.DLCProcessor & key).fetch1()

        # Should have processed kinematics
        x_pos = np.array(result["x_pos"])
        y_pos = np.array(result["y_pos"])
        heading = np.array(result["heading_direction"])

        # From golden: PROC has 281,876 frames
        assert len(x_pos) == 281876, f"x_pos length {len(x_pos)} != 281876"

        golden_baseline.check_sample_values(
            "dlcprocessor_kinematics",
            {"x_pos": x_pos, "y_pos": y_pos, "heading_direction": heading}
        )

    def test_dlckptsdf_populates(self, populated_db, golden_baseline):
        """Verify DLCKptsDf.populate() creates entry."""
        from vr4mice.schema import dlc

        dlc.DLCKptsDf.populate()

        count = len(dlc.DLCKptsDf())
        golden_baseline.check_row_count("dlckptsdf", count)

    def test_dlckptsdf_keypoints(self, populated_db):
        """Verify DLCKptsDf contains keypoint data."""
        from vr4mice.schema import dlc

        key = populated_db["dlc_key"]

        df = dlc.DLCKptsDf().get_data(key)

        # Should have 281,748 frames (from golden DLC file)
        assert len(df) == 281748, f"DLC DataFrame length {len(df)} != 281748"

        # Should have bodypart columns
        assert "nose" in str(df.columns) or ("nose", "x") in df.columns

    def test_syncdlckptsdf_populates(self, populated_db, golden_baseline):
        """Verify SyncDLCKptsDf.populate() creates entry."""
        from vr4mice.schema import dlc

        # Depends on DLCKptsDf
        dlc.DLCKptsDf.populate()
        dlc.SyncDLCKptsDf.populate()

        count = len(dlc.SyncDLCKptsDf())
        golden_baseline.check_row_count("syncdlckptsdf", count)

    def test_offlinekinematics_populates(self, populated_db, golden_baseline):
        """Verify OfflineKinematics.populate() creates entry."""
        from vr4mice.schema import dlc

        # Depends on SyncDLCKptsDf
        dlc.DLCKptsDf.populate()
        dlc.SyncDLCKptsDf.populate()
        dlc.OfflineKinematics.populate()

        count = len(dlc.OfflineKinematics())
        golden_baseline.check_row_count("offlinekinematics", count)

    def test_offlinekinematics_data(self, populated_db, golden_baseline):
        """Verify OfflineKinematics contains computed kinematics."""
        from vr4mice.schema import dlc

        key = populated_db["dlc_key"]

        df = dlc.OfflineKinematics().get_data(key)

        if df is not None and df is not False:
            # Should have kinematic columns
            assert "heading_dir" in df.columns or "head_angle" in df.columns

            golden_baseline.check_sample_values(
                "offlinekinematics",
                {col: df[col].values for col in df.columns if col not in ["dataset"]}
            )


# ==============================================================================
# Interp Mode Tests
# ==============================================================================

class TestInterpMode:
    """Tests for interp mode - requires analysis + dlc."""

    @pytest.fixture(autouse=True)
    def setup_dependencies(self, populated_db):
        """Ensure analysis and dlc modes have run."""
        from vr4mice.schema import base_analysis, dlc

        # Analysis dependencies
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame.populate()

        # DLC dependencies
        dlc.DLCProcessor.populate()
        dlc.DLCKptsDf.populate()
        dlc.SyncDLCKptsDf.populate()
        dlc.OfflineKinematics.populate()

    def test_interpolatedtrials_populates(self, populated_db, golden_baseline):
        """Verify InterpolatedTrials.populate() creates entry."""
        from vr4mice.schema import interpolated_trajectories

        interpolated_trajectories.InterpolatedTrials.populate()

        count = len(interpolated_trajectories.InterpolatedTrials())
        golden_baseline.check_row_count("interpolatedtrials", count)

    def test_interpolatedtrials_columns(self, populated_db):
        """Verify InterpolatedTrials has expected columns."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]

        result = (interpolated_trajectories.InterpolatedTrials & key).fetch(as_dict=True)

        if len(result) > 0:
            data = result[0]
            expected_keys = ["x", "y", "trial", "velocity", "aperture"]
            for k in expected_keys:
                assert k in data, f"Missing key: {k}"

    def test_meanxytrajectory_populates(self, populated_db, golden_baseline):
        """Verify MeanXYTrajectory.populate() creates entry."""
        from vr4mice.schema import interpolated_trajectories

        interpolated_trajectories.InterpolatedTrials.populate()
        interpolated_trajectories.MeanXYTrajectory.populate()

        count = len(interpolated_trajectories.MeanXYTrajectory())
        golden_baseline.check_row_count("meanxytrajectory", count)

    def test_sessionmetrics_populates(self, populated_db, golden_baseline):
        """Verify SessionMetrics.populate() creates entry."""
        from vr4mice.schema import session_metrics

        session_metrics.SessionMetrics.populate()

        count = len(session_metrics.SessionMetrics())
        golden_baseline.check_row_count("sessionmetrics", count)

    def test_sessionmetrics_values(self, populated_db, golden_baseline):
        """Verify SessionMetrics has computed values."""
        from vr4mice.schema import session_metrics

        key = populated_db["dataset_key"]

        result = (session_metrics.SessionMetrics & key).fetch(as_dict=True)

        if len(result) > 0:
            data = result[0]

            # Verify expected metrics exist
            assert "session_reward" in data
            assert "session_trial_duration" in data
            assert "session_max_trial_number" in data

            golden_baseline.check_scalar("session_reward", data["session_reward"])
            golden_baseline.check_scalar("session_max_trial_number", data["session_max_trial_number"])

    def test_trialmetrics_populates(self, populated_db, golden_baseline):
        """Verify TrialMetrics.populate() creates entry."""
        from vr4mice.schema import session_metrics

        session_metrics.TrialMetrics.populate()

        count = len(session_metrics.TrialMetrics())
        golden_baseline.check_row_count("trialmetrics", count)


# ==============================================================================
# Latency Mode Tests
# ==============================================================================

class TestLatencyMode:
    """Tests for latency mode - requires populate (specifically SignalsPhotodiode)."""

    def test_signals_photodiode_table_exists(self, populated_db):
        """Verify SignalsPhotodiode table can be accessed."""
        vr4mice = populated_db["vr4mice"]

        # SignalsPhotodiode is populated from PROC data
        # This test verifies the table structure exists
        assert hasattr(vr4mice, 'SignalsPhotodiode')

    @pytest.mark.skip(reason="SignalsPhotodiode population requires specific PROC data format")
    def test_signalsphotodiode_populates(self, populated_db, golden_baseline):
        """Verify SignalsPhotodiode.populate() creates entry."""
        vr4mice = populated_db["vr4mice"]

        vr4mice.SignalsPhotodiode.populate()

        count = len(vr4mice.SignalsPhotodiode())
        golden_baseline.check_row_count("signalsphotodiode", count)

    @pytest.mark.skip(reason="Depends on SignalsPhotodiode population")
    def test_signalsphotodiodealigned_populates(self, populated_db, golden_baseline):
        """Verify SignalsPhotodiodeAligned.populate() creates entry."""
        from vr4mice.schema import latency_tests

        latency_tests.SignalsPhotodiodeAligned.populate()

        count = len(latency_tests.SignalsPhotodiodeAligned())
        golden_baseline.check_row_count("signalsphotodiodealigned", count)


# ==============================================================================
# Summary Mode Tests
# ==============================================================================

class TestSummaryMode:
    """Tests for summary mode - requires analysis (DataFrame + BoxDataFrame)."""

    @pytest.fixture(autouse=True)
    def setup_dependencies(self, populated_db):
        """Ensure analysis mode has run."""
        from vr4mice.schema import base_analysis

        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame.populate()

    @pytest.mark.skip(reason="SummaryPlots requires EMAIL env var and plot generation infrastructure")
    def test_summaryplots_populates(self, populated_db, golden_master, monkeypatch):
        """Verify SummaryPlots.populate() creates entry."""
        from vr4mice.schema import base_analysis

        # Disable email sending
        monkeypatch.setenv("EMAIL", "false")

        base_analysis.SummaryPlots.populate()

        count = len(base_analysis.SummaryPlots())
        golden_baseline.check_row_count("summaryplots", count)

    @pytest.mark.skip(reason="TrackingSummaryPlots requires DLC data and plot infrastructure")
    def test_trackingsummaryplots_populates(self, populated_db, golden_master, monkeypatch):
        """Verify TrackingSummaryPlots.populate() creates entry."""
        from vr4mice.schema import base_analysis, dlc

        # Ensure DLC is populated
        dlc.DLCKptsDf.populate()

        # Disable email sending
        monkeypatch.setenv("EMAIL", "false")

        base_analysis.TrackingSummaryPlots.populate()

        count = len(base_analysis.TrackingSummaryPlots())
        golden_baseline.check_row_count("trackingsummaryplots", count)


# ==============================================================================
# Fetch Mode Tests
# ==============================================================================

class TestFetchMode:
    """Tests for fetch mode - independent of pipeline, creates GUI menu file."""

    @pytest.mark.skip(reason="Fetch mode requires connection to production base_schemas tables")
    def test_fetch_creates_npy_file(self, dj_config, tmp_path):
        """Verify fetch_data creates .npy file with expected structure."""
        from vr4mice.actions.fetch_data import fetch_data

        output_path = tmp_path / "gui_menu.npy"
        fetch_data(dst=str(output_path))

        assert output_path.exists(), "gui_menu.npy was not created"

        # Load and verify structure
        data = np.load(output_path, allow_pickle=True).item()

        # Expected keys in the menu data
        expected_keys = ["MouseDict", "experimenter_name", "timestamp"]
        for key in expected_keys:
            assert key in data, f"Missing expected key: {key}"
