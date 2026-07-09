"""
Integration tests for the vr4mice pipeline using the golden dataset.

Tests are organized by pipeline mode (matching run.py's mode argument):
- connect: Schema imports and database connectivity
- populate: Dataset, MouseState, State, Video, DLC table population
- analysis: DataFrame, BoxDataFrame, SummaryPlots population
- dlc: DLCProcessor, DLCKptsDf, SyncDLCKptsDf, OfflineKinematics population
- interp: InterpolatedTrials, MeanXYTrajectory, YBinnedXYTrajectory,
          MeanVelocities, SessionMetrics, TrialMetrics
- latency: SignalsPhotodiode, SignalsPhotodiodeAligned, AllLatencies
- fetch: GUI menu .npy file creation

Test Strategy:
- Sequential pipeline testing with shared database session
- Golden baseline verification: row counts + sample values (first/last/middle)
- Module-scoped fixtures for efficiency

Dependencies:
- Docker Desktop running (MySQL via docker-compose)
- Golden dataset in dj_pipeline/tests/data/w_photodiode/ (via Git LFS)

Run with:
    cd dj_pipeline
    docker-compose -f docker-compose.test.yml run --rm tests \\
        bash -c "cd tests && python -m pytest integration/test_run_modes.py -v"
"""

import json
import pickle
import shutil
from pathlib import Path

import numpy as np
import pytest

# Golden dataset sizes (Flamingo_2026-02-05_1).
# These are properties of the golden dataset, not configuration.
# If the golden dataset changes, update these values here.
GOLDEN_STATE_ROWS = 151737  # rows in pickle state array
GOLDEN_DLC_FRAMES = 119755  # frames in DLC HDF5 file
GOLDEN_PROC_FRAMES = 119864  # frames in PROC file (DLCProcessor output)


# ==============================================================================
# Golden Baseline Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def golden_baseline_dir():
    """Path to golden baseline output files for integration tests."""
    return Path(__file__).parent.parent / "golden_baseline" / "pipeline"


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
                    f.write("\n")
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
                assert (
                    abs(actual_count - expected) <= tolerance
                ), f"{table_name}: row count {actual_count} != {expected} (tolerance: {tolerance})"
            else:
                assert (
                    actual_count == expected
                ), f"{table_name}: row count {actual_count} != {expected}"
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
                    if arr.dtype == object:
                        inner = arr.item()
                        if isinstance(inner, dict):
                            # Dict-valued blobs from DataFrame.to_dict():
                            # {row_idx: value, ...} -> extract values as array
                            arr = np.array(list(inner.values()))
                        else:
                            return {"scalar_object": True}
                    else:
                        return {
                            "scalar": (
                                float(arr)
                                if np.issubdtype(arr.dtype, np.floating)
                                else int(arr)
                            )
                        }
                if len(arr) == 0:
                    return {"empty": True}

                samples = {
                    "length": len(arr),
                    "dtype": str(arr.dtype),
                }

                # First value
                first_val = arr[0]
                if hasattr(first_val, "tolist"):
                    first_val = first_val.tolist()
                samples["first"] = first_val

                # Middle value
                mid_idx = len(arr) // 2
                mid_val = arr[mid_idx]
                if hasattr(mid_val, "tolist"):
                    mid_val = mid_val.tolist()
                samples["middle"] = mid_val
                samples["middle_idx"] = mid_idx

                # Last value
                last_val = arr[-1]
                if hasattr(last_val, "tolist"):
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
                    f.write("\n")
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
                    assert (
                        actual.get("length") == expected["length"]
                    ), f"{table_name}.{key}: length {actual.get('length')} != {expected['length']}"

                # Check values with floating point tolerance
                for pos in ["first", "middle", "last", "scalar"]:
                    if pos in expected:
                        actual_val = actual.get(pos)
                        expected_val = expected[pos]

                        if isinstance(expected_val, float):
                            assert actual_val == pytest.approx(
                                expected_val, rel=1e-5, nan_ok=True
                            ), f"{table_name}.{key}[{pos}]: {actual_val} != {expected_val}"
                        elif isinstance(expected_val, list):
                            np.testing.assert_array_almost_equal(
                                actual_val,
                                expected_val,
                                decimal=5,
                                err_msg=f"{table_name}.{key}[{pos}] mismatch",
                            )
                        else:
                            assert (
                                actual_val == expected_val
                            ), f"{table_name}.{key}[{pos}]: {actual_val} != {expected_val}"

            return True

        def check_scalar(self, name, actual_value):
            """Compare a scalar value against golden."""
            golden_path = self.base_dir / f"{name}_scalar.json"

            if self.regenerate:
                with open(golden_path, "w") as f:
                    json.dump({"value": actual_value}, f, indent=2)
                    f.write("\n")
                return True

            if not golden_path.exists():
                pytest.fail(f"Golden file not found: {golden_path}")

            with open(golden_path) as f:
                expected = json.load(f)["value"]

            if isinstance(expected, float):
                assert actual_value == pytest.approx(
                    expected, rel=1e-5
                ), f"{name}: {actual_value} != {expected}"
            else:
                assert actual_value == expected, f"{name}: {actual_value} != {expected}"

            return True

    return GoldenBaseline(golden_baseline_dir, regenerate)


# ==============================================================================
# Pipeline Fixtures (Module-Scoped for Efficiency)
# ==============================================================================


@pytest.fixture(scope="module")
def pipeline_test_data(
    test_data_dir, test_dataset_name, test_camera_prefix, tmp_path_factory
):
    """
    Prepare test data in a temporary directory structure.

    Creates a data directory that mimics the expected structure for populate_rig.
    Returns paths and metadata needed for pipeline tests.
    """
    # Create temporary data directory
    tmp_dir = tmp_path_factory.mktemp("pipeline_data")
    data_dir = tmp_dir / "data"
    data_dir.mkdir()

    # Copy required files (.npy metadata for Flamingo dataset)
    files_to_copy = [
        f"{test_dataset_name}.pickle",
        f"{test_dataset_name}.npy",
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
        "tmp_dir": tmp_dir,
        "dataset_name": test_dataset_name,
        "camera_prefix": test_camera_prefix,
        "pickle_path": data_dir / f"{test_dataset_name}.pickle",
        "metadata_path": data_dir / f"{test_dataset_name}.npy",
        "dlc_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_DLC.hdf5",
        "ts_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_TS.npy",
        "proc_path": data_dir / f"{test_camera_prefix}_{test_dataset_name}_PROC",
    }


@pytest.fixture(scope="module")
def populated_db(dj_config, pipeline_test_data, test_dataset_name, test_camera_prefix):
    """
    Populate input tables using check_keys() + populate() from populate_rig.py.

    This bypasses populate_rig() itself because it hardcodes Docker-specific
    paths (/data, /data/dlc_video) that don't work with temp directories.
    What we exercise here is the validation/transformation/insertion core:
    - check_keys() validates required attributes exist or can be derived
    - populate() applies transformers and local_defs (get_state, get_path, etc.)
    - Real table.insert1() inserts the data

    What we skip: file discovery (get_filenames), GUI/non-GUI branching,
    get_session_incr(), and populate_rig()'s error handling wrapper.

    Additionally, we merge session metadata (video_meta) into raw_data so the
    Video table gets real fps/width/height values. In the gui=False production
    path, these would be None since video_meta comes from the .npy GUI file.
    """
    from vr4mice.schema import vr4mice
    from vr4mice.actions.populate_rig import check_keys, populate, get_files_paths
    from vr4mice.actions.keys2tables_vr4mice import vr4mice as vr4mice_schema_dict

    # Load test data
    with open(pipeline_test_data["pickle_path"], "rb") as f:
        pickle_data = pickle.load(f)

    # Load session metadata (.npy for Flamingo dataset)
    metadata_path = pipeline_test_data["metadata_path"]
    session_metadata = np.load(metadata_path, allow_pickle=True).item()

    # Set up directory structure matching what get_path() expects.
    # get_path() resolves: Path(srcf) / Path(file_info["dst"]).name / filename
    # So we need DLC/TS/PROC files in a "dlc_video" subdir under srcf.
    data_dir = pipeline_test_data["data_dir"]
    srcf = str(data_dir.parent)  # tmp_dir, parent of "data/"
    dlc_video_dir = data_dir.parent / "dlc_video"
    dlc_video_dir.mkdir(exist_ok=True)
    for src_key in ["dlc_path", "ts_path", "proc_path"]:
        src = pipeline_test_data[src_key]
        dst = dlc_video_dir / src.name
        if not dst.exists() and src.exists():
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy(src, dst)

    # Build raw_data the same way populate_rig() does for gui=False:
    # 1. get_files_paths() generates file path info from dataset name
    # 2. Merge with pickle data
    files_info = get_files_paths(
        dataset=test_dataset_name,
        remote_src=None,
        local_src=srcf,
        data=str(data_dir),
    )
    raw_data = {**files_info, **pickle_data}

    # Merge session video metadata so Video table gets real values.
    # In production gui=False, video_meta values are None. We override
    # them here to get better test coverage of the Video insertion path.
    raw_data["video_meta"] = session_metadata["video_meta"]
    raw_data["doe"] = files_info["doe"]

    # Run check_keys + populate for each table, same as populate_rig()'s inner loop
    for table_name, attributes in vr4mice_schema_dict["tables"].items():
        flag, none_vals = check_keys(
            attributes, raw_data, table_name, schema=vr4mice_schema_dict
        )
        if flag:
            raw_data = {**raw_data, **none_vals}
            populate(
                table_name,
                attributes,
                raw_data,
                schema=vr4mice_schema_dict,
                srcf=srcf,
                dstf="processed",
                move=False,
            )

    # Verify the 5 core tables populated (fail fast if pipeline broke)
    assert len(vr4mice.Dataset()) == 1, "Dataset not populated"
    assert len(vr4mice.MouseState()) == 1, "MouseState not populated"
    assert len(vr4mice.State()) == 1, "State not populated"
    assert len(vr4mice.Video()) == 1, "Video not populated"
    assert len(vr4mice.DLC()) == 1, "DLC not populated"

    # Build keys for downstream test lookups.
    # parse_date() returns datetime; convert to date for key matching.
    doe = (
        files_info["doe"].date()
        if hasattr(files_info["doe"], "date")
        else files_info["doe"]
    )

    return {
        "vr4mice": vr4mice,
        "dataset_key": {"dataset": test_dataset_name},
        "video_key": {
            "dataset": test_dataset_name,
            "camera": test_camera_prefix,
            "doe": doe,
        },
        "dlc_key": {
            "dataset": test_dataset_name,
            "camera": test_camera_prefix,
            "doe": doe,
            "model_name": "DLC",
        },
        "pickle_data": pickle_data,
        "session_metadata": session_metadata,
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

        assert hasattr(vr4mice, "Dataset")
        assert hasattr(vr4mice, "MouseState")
        assert hasattr(vr4mice, "State")
        assert hasattr(vr4mice, "Video")
        assert hasattr(vr4mice, "DLC")

    def test_base_analysis_schema_imports(self, dj_config):
        """Verify base_analysis schema imports without error."""
        from vr4mice.schema import base_analysis

        assert hasattr(base_analysis, "DataFrame")
        assert hasattr(base_analysis, "BoxDataFrame")
        assert hasattr(base_analysis, "SummaryPlots")
        assert hasattr(base_analysis, "GitCommit")

    def test_dlc_schema_imports(self, dj_config):
        """Verify dlc schema imports without error."""
        from vr4mice.schema import dlc

        assert hasattr(dlc, "DLCProcessor")
        assert hasattr(dlc, "DLCKptsDf")
        assert hasattr(dlc, "SyncDLCKptsDf")
        assert hasattr(dlc, "OfflineKinematics")

    def test_interpolated_trajectories_schema_imports(self, dj_config):
        """Verify interpolated_trajectories schema imports without error."""
        from vr4mice.schema import interpolated_trajectories

        assert hasattr(interpolated_trajectories, "InterpolatedTrials")
        assert hasattr(interpolated_trajectories, "MeanXYTrajectory")
        assert hasattr(interpolated_trajectories, "YBinnedXYTrajectory")
        assert hasattr(interpolated_trajectories, "MeanVelocities")

    def test_session_metrics_schema_imports(self, dj_config):
        """Verify session_metrics schema imports without error."""
        from vr4mice.schema import session_metrics

        assert hasattr(session_metrics, "SessionMetrics")
        assert hasattr(session_metrics, "TrialMetrics")

    def test_latency_tests_schema_imports(self, dj_config):
        """Verify latency_tests schema imports without error."""
        from vr4mice.schema import latency_tests

        assert hasattr(latency_tests, "SignalsPhotodiodeAligned")
        assert hasattr(latency_tests, "AllLatencies")

    def test_base_schema_imports(self, dj_config):
        """Verify base schema imports without CamelCase errors."""
        from vr4mice.schema import base

        assert hasattr(base, "Base")


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
        assert result["session_label"] == "ar_discrim_occluders_inv"

    def test_mousestate_table_populated(self, populated_db, golden_baseline):
        """Verify MouseState table has expected row count."""
        vr4mice = populated_db["vr4mice"]
        count = len(vr4mice.MouseState())
        golden_baseline.check_row_count("mousestate", count)

    def test_mousestate_array_lengths(self, populated_db, golden_baseline):
        """Verify MouseState arrays have expected lengths."""
        vr4mice = populated_db["vr4mice"]
        key = populated_db["dataset_key"]

        result = (vr4mice.MouseState & key).fetch1()
        x_pos = np.array(result["x_pos"])

        # Expected from golden dataset
        assert (
            len(x_pos) == GOLDEN_STATE_ROWS
        ), f"x_pos length {len(x_pos)} != {GOLDEN_STATE_ROWS}"

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

        assert len(episode) == GOLDEN_STATE_ROWS
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

        assert (
            df is not False and df is not None
        ), "DataFrame not populated - expected rows after populate()"

        expected_columns = [
            "x",
            "y",
            "trial",
            "iti",
            "velocity",
            "object_on_left",
            "mouse_in_left",
            "mouse_in_right",
        ]

        for col in expected_columns:
            assert col in df.columns, f"Missing column: {col}"

    def test_dataframe_keys_match_columns(self, populated_db):
        """Verify inserted DataFrame keys match the stored dataframe columns."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]

        df = base_analysis.DataFrame().get_data(key)
        row = (base_analysis.DataFrame & key).fetch1()

        assert (
            df is not False and df is not None
        ), "DataFrame not populated - expected rows after populate()"

        row_columns = {
            col for col in row.keys() if col not in {"interpolation"}
        }

        assert (
            set(df.columns) == row_columns
        ), "DataFrame column names do not match inserted data keys"

    def test_dataframe_sample_values(self, populated_db, golden_baseline):
        """Verify DataFrame sample values match golden."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]
        df = base_analysis.DataFrame().get_data(key)

        assert (
            df is not False and df is not None
        ), "DataFrame not populated - expected rows after populate()"

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

        assert (
            box_df is not False and box_df is not None
        ), "BoxDataFrame not populated - expected rows after populate()"

        # Should have box coordinates
        assert "l_box_x_min" in box_df.columns
        assert "r_box_x_max" in box_df.columns
        assert "tt_box_z_min" in box_df.columns

    def test_boxdataframe_sample_values(self, populated_db, golden_baseline):
        """Verify BoxDataFrame sample values match golden."""
        from vr4mice.schema import base_analysis

        key = populated_db["dataset_key"]
        box_df = base_analysis.BoxDataFrame().get_data(key)

        assert (
            box_df is not False and box_df is not None
        ), "BoxDataFrame not populated - expected rows after populate()"

        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "boxdataframe",
            {
                col: box_df[col].values
                for col in box_df.columns
                if col not in key_columns
            },
        )


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

        # Check against golden dataset PROC frame count
        assert (
            len(x_pos) == GOLDEN_PROC_FRAMES
        ), f"x_pos length {len(x_pos)} != {GOLDEN_PROC_FRAMES}"

        golden_baseline.check_sample_values(
            "dlcprocessor_kinematics",
            {"x_pos": x_pos, "y_pos": y_pos, "heading_direction": heading},
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

        # Check against golden dataset DLC frame count
        assert (
            len(df) == GOLDEN_DLC_FRAMES
        ), f"DLC DataFrame length {len(df)} != {GOLDEN_DLC_FRAMES}"

        # Should have bodypart columns (MultiIndex: bodypart, coord)
        assert (
            "nose",
            "x",
        ) in df.columns, "Missing expected bodypart column ('nose', 'x')"

    def test_dlckptsdf_sample_values(self, populated_db, golden_baseline):
        """Verify DLCKptsDf sample values match golden."""
        from vr4mice.schema import dlc

        key = populated_db["dlc_key"]
        df = dlc.DLCKptsDf().get_data(key)

        assert (
            df is not None
        ), "DLCKptsDf not populated - expected rows after populate()"

        # Flatten MultiIndex columns for a few representative bodyparts
        data_dict = {
            f"{bp}_{coord}": df[(bp, coord)].values
            for bp, coord in [("nose", "x"), ("nose", "y"), ("nose", "likelihood")]
        }
        golden_baseline.check_sample_values("dlckptsdf", data_dict)

    def test_syncdlckptsdf_populates(self, populated_db, golden_baseline):
        """Verify SyncDLCKptsDf.populate() creates entry."""
        from vr4mice.schema import dlc

        # Depends on DLCKptsDf
        dlc.DLCKptsDf.populate()
        dlc.SyncDLCKptsDf.populate()

        count = len(dlc.SyncDLCKptsDf())
        golden_baseline.check_row_count("syncdlckptsdf", count)

    def test_syncdlckptsdf_sample_values(self, populated_db, golden_baseline):
        """Verify SyncDLCKptsDf sample values match golden."""
        from vr4mice.schema import dlc

        key = populated_db["dlc_key"]
        df = dlc.SyncDLCKptsDf().get_data(key)

        assert (
            df is not None
        ), "SyncDLCKptsDf not populated - expected rows after populate()"

        # Flatten MultiIndex columns for a few representative bodyparts
        data_dict = {
            f"{bp}_{coord}": df[(bp, coord)].values
            for bp, coord in [("nose", "x"), ("nose", "y"), ("nose", "likelihood")]
        }
        golden_baseline.check_sample_values("syncdlckptsdf", data_dict)

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

        assert (
            df is not False and df is not None
        ), "OfflineKinematics not populated - expected rows after populate()"

        # Should have both kinematic columns (defined in OfflineKinematics schema)
        assert "heading_dir" in df.columns, "Missing expected column 'heading_dir'"
        assert "head_angle" in df.columns, "Missing expected column 'head_angle'"

        # Exclude primary key columns (dataset, camera, doe, model_name) - these
        # contain non-numeric types (dates, strings) that don't round-trip through JSON.
        key_columns = {"dataset", "camera", "doe", "model_name"}
        golden_baseline.check_sample_values(
            "offlinekinematics",
            {col: df[col].values for col in df.columns if col not in key_columns},
        )


# ==============================================================================
# Interp Mode Tests
# ==============================================================================


class TestInterpMode:
    """Tests for interp mode - requires analysis + dlc."""

    @pytest.fixture(autouse=True)
    def setup_dependencies(self, populated_db):
        """Ensure analysis and dlc modes have run.

        These populate() calls are safe to repeat. If the table already has
        data (e.g., from TestAnalysisMode or TestDlcMode running first),
        populate() returns immediately without re-computing anything. This
        guarantees interp tests work regardless of test execution order.
        """
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

        result = (interpolated_trajectories.InterpolatedTrials & key).fetch(
            as_dict=True
        )

        assert (
            len(result) > 0
        ), "InterpolatedTrials not populated - expected rows after populate()"

        data = result[0]
        expected_keys = ["x", "y", "trial", "velocity", "aperture"]
        for k in expected_keys:
            assert k in data, f"Missing key: {k}"

    def test_interpolatedtrials_sample_values(self, populated_db, golden_baseline):
        """Verify InterpolatedTrials sample values match golden."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.InterpolatedTrials & key).fetch(
            as_dict=True
        )

        assert (
            len(result) > 0
        ), "InterpolatedTrials not populated - expected rows after populate()"

        data = result[0]
        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "interpolatedtrials",
            {k: np.array(v) for k, v in data.items() if k not in key_columns},
        )

    def test_meanxytrajectory_populates(self, populated_db, golden_baseline):
        """Verify MeanXYTrajectory.populate() creates entry."""
        from vr4mice.schema import interpolated_trajectories

        interpolated_trajectories.InterpolatedTrials.populate()
        interpolated_trajectories.MeanXYTrajectory.populate()

        count = len(interpolated_trajectories.MeanXYTrajectory())
        golden_baseline.check_row_count("meanxytrajectory", count)

    def test_meanxytrajectory_sample_values(self, populated_db, golden_baseline):
        """Verify MeanXYTrajectory sample values match golden."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.MeanXYTrajectory & key).fetch(as_dict=True)

        assert (
            len(result) > 0
        ), "MeanXYTrajectory not populated - expected rows after populate()"

        data = result[0]
        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "meanxytrajectory",
            {k: np.array(v) for k, v in data.items() if k not in key_columns},
        )

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

        assert (
            len(result) > 0
        ), "SessionMetrics not populated - expected rows after populate()"

        data = result[0]

        # Verify expected metrics exist
        assert "session_reward" in data
        assert "session_trial_duration" in data
        assert "session_max_trial_number" in data

        golden_baseline.check_scalar("session_reward", data["session_reward"])
        golden_baseline.check_scalar(
            "session_max_trial_number", data["session_max_trial_number"]
        )

    def test_trialmetrics_populates(self, populated_db, golden_baseline):
        """Verify TrialMetrics.populate() creates entry."""
        from vr4mice.schema import session_metrics

        session_metrics.TrialMetrics.populate()

        count = len(session_metrics.TrialMetrics())
        golden_baseline.check_row_count("trialmetrics", count)

    def test_trialmetrics_sample_values(self, populated_db, golden_baseline):
        """Verify TrialMetrics sample values match golden."""
        from vr4mice.schema import session_metrics

        key = populated_db["dataset_key"]
        result = (session_metrics.TrialMetrics & key).fetch(as_dict=True)

        assert (
            len(result) > 0
        ), "TrialMetrics not populated - expected rows after populate()"

        data = result[0]
        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "trialmetrics",
            {k: np.array(v) for k, v in data.items() if k not in key_columns},
        )

    def test_ybinnedxytrajectory_populates(self, populated_db, golden_baseline):
        """Verify YBinnedXYTrajectory.populate() creates entry."""
        from vr4mice.schema import interpolated_trajectories

        interpolated_trajectories.InterpolatedTrials.populate()
        interpolated_trajectories.YBinnedXYTrajectory.populate()

        count = len(interpolated_trajectories.YBinnedXYTrajectory())
        golden_baseline.check_row_count("ybinnedxytrajectory", count)

    def test_ybinnedxytrajectory_columns(self, populated_db):
        """Verify YBinnedXYTrajectory has expected columns."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.YBinnedXYTrajectory & key).fetch(
            as_dict=True
        )

        assert (
            len(result) > 0
        ), "YBinnedXYTrajectory not populated - expected rows after populate()"

        data = result[0]
        for k in ["aperture", "bin_centers", "x_flipped", "y"]:
            assert k in data, f"Missing key: {k}"

    def test_ybinnedxytrajectory_sample_values(self, populated_db, golden_baseline):
        """Verify YBinnedXYTrajectory sample values match golden."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.YBinnedXYTrajectory & key).fetch(
            as_dict=True
        )

        assert (
            len(result) > 0
        ), "YBinnedXYTrajectory not populated - expected rows after populate()"

        data = result[0]
        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "ybinnedxytrajectory",
            {k: np.array(v) for k, v in data.items() if k not in key_columns},
        )

    def test_meanvelocities_populates(self, populated_db, golden_baseline):
        """Verify MeanVelocities.populate() creates entry."""
        from vr4mice.schema import interpolated_trajectories

        interpolated_trajectories.InterpolatedTrials.populate()
        interpolated_trajectories.MeanVelocities.populate()

        count = len(interpolated_trajectories.MeanVelocities())
        golden_baseline.check_row_count("meanvelocities", count)

    def test_meanvelocities_columns(self, populated_db):
        """Verify MeanVelocities has expected columns."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.MeanVelocities & key).fetch(as_dict=True)

        assert (
            len(result) > 0
        ), "MeanVelocities not populated - expected rows after populate()"

        data = result[0]
        for k in [
            "aperture",
            "trial_length",
            "velocity",
            "velocity_x",
            "velocity_y",
            "velocity_x_fliped",
        ]:
            assert k in data, f"Missing key: {k}"

    def test_meanvelocities_sample_values(self, populated_db, golden_baseline):
        """Verify MeanVelocities sample values match golden."""
        from vr4mice.schema import interpolated_trajectories

        key = populated_db["dataset_key"]
        result = (interpolated_trajectories.MeanVelocities & key).fetch(as_dict=True)

        assert (
            len(result) > 0
        ), "MeanVelocities not populated - expected rows after populate()"

        data = result[0]
        key_columns = {"dataset"}
        golden_baseline.check_sample_values(
            "meanvelocities",
            {k: np.array(v) for k, v in data.items() if k not in key_columns},
        )


# ==============================================================================
# Latency Mode Tests
# ==============================================================================


class TestLatencyMode:
    """Tests for latency mode - photodiode signal and latency analysis.

    The Flamingo golden dataset has valid photodiode recordings (mean baseline
    signal ~70, well above the has_signal() threshold of 8.0), so the full
    chain populates: SignalsPhotodiode -> SignalsPhotodiodeAligned -> AllLatencies.

    SignalsPhotodiode.make() reads PROC files from disk via get_files_paths(),
    which defaults to Docker paths (/data/dlc_video). We patch it to use the
    temp test data directory instead.
    """

    @pytest.fixture(autouse=True)
    def setup_photodiode_chain(self, populated_db, monkeypatch):
        """Patch file paths and populate the photodiode table chain."""
        from vr4mice.schema import vr4mice
        from vr4mice.schema import latency_tests
        from vr4mice.actions.populate_rig import get_files_paths as real_fn

        test_data = populated_db["test_data"]

        def patched_get_files_paths(dataset, **kwargs):
            kwargs["local_src"] = str(test_data["data_dir"].parent)
            return real_fn(dataset, **kwargs)

        monkeypatch.setattr(
            "vr4mice.actions.populate_rig.get_files_paths",
            patched_get_files_paths,
        )

        # Populate the full chain
        vr4mice.SignalsPhotodiode.populate()
        latency_tests.SignalsPhotodiodeAligned.populate()
        latency_tests.AllLatencies.populate()

    def test_signals_photodiode_table_exists(self, populated_db):
        """Verify SignalsPhotodiode table can be accessed."""
        vr4mice = populated_db["vr4mice"]
        assert hasattr(vr4mice, "SignalsPhotodiode")

    def test_signals_photodiode_populates(self, populated_db, golden_baseline):
        """Verify SignalsPhotodiode.populate() creates entry from PROC data."""
        from vr4mice.schema import vr4mice

        count = len(vr4mice.SignalsPhotodiode())
        golden_baseline.check_row_count("signalsphotodiode", count)

    def test_signals_photodiode_fields(self, populated_db):
        """Verify SignalsPhotodiode entry has expected blob fields."""
        from vr4mice.schema import vr4mice

        key = populated_db["dataset_key"]
        result = (vr4mice.SignalsPhotodiode & key).fetch(as_dict=True)
        assert len(result) == 1, "SignalsPhotodiode should have 1 row"
        data = result[0]

        for field in [
            "photodiode_time",
            "photodiode_read",
            "generated_frame_time",
            "generated_send_time",
            "generated_signal",
        ]:
            assert field in data, f"Missing field: {field}"
            assert len(data[field]) > 0, f"Field {field} is empty"

    def test_signals_photodiode_sample_values(self, populated_db, golden_baseline):
        """Verify SignalsPhotodiode sample values match golden."""
        from vr4mice.schema import vr4mice

        key = populated_db["dataset_key"]
        result = (vr4mice.SignalsPhotodiode & key).fetch(as_dict=True)
        assert len(result) > 0
        data = result[0]

        # Exclude non-array fields (dataset key, scalar start_time, varchar signal_type,
        # float signal_delay) from sample value checks
        skip_fields = {"dataset", "signal_type", "signal_delay", "start_time"}
        golden_baseline.check_sample_values(
            "signalsphotodiode",
            {
                k: v
                for k, v in data.items()
                if k not in skip_fields and isinstance(v, np.ndarray) and v.ndim > 0
            },
        )

    def test_signals_photodiode_aligned_populates(self, populated_db, golden_baseline):
        """Verify SignalsPhotodiodeAligned.populate() creates entry."""
        from vr4mice.schema import latency_tests

        count = len(latency_tests.SignalsPhotodiodeAligned())
        golden_baseline.check_row_count("signalsphotodiodealigned", count)

    def test_all_latencies_populates(self, populated_db, golden_baseline):
        """Verify AllLatencies.populate() creates entry."""
        from vr4mice.schema import latency_tests

        count = len(latency_tests.AllLatencies())
        golden_baseline.check_row_count("alllatencies", count)


# ==============================================================================
# SummaryPlots Tests
# ==============================================================================


class TestSummaryPlots:
    """Tests for SummaryPlots table population.

    SummaryPlots.make() lazily imports vr4mice.schema.base and
    base_schemas.schemas. In DJ 2.0, table declarations cannot happen inside
    a populate() transaction, so these modules must be imported before
    populate() is called. The setup fixture handles this pre-import,
    matching what run.py does in production (importing all schemas at
    module level before calling populate).

    NOTE: TrackingSummaryPlots was deprecated in PR #291.
    """

    @pytest.fixture(autouse=True)
    def setup_summaryplots(self, populated_db, monkeypatch, tmp_path):
        """Set up SummaryPlots dependencies and pre-import lazy modules.

        Pre-imports vr4mice.schema.base and base_schemas.schemas to ensure
        their @schema table declarations run OUTSIDE any populate()
        transaction. This mirrors how run.py imports all schemas at module
        level before calling populate() in production.

        Also monkeypatches vr4mice_summary_plots() to avoid the hardcoded
        /data/summary_plots path (Docker production path).
        """
        from vr4mice.schema import base_analysis, dlc

        # Populate analysis prerequisites
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame.populate()

        # DLC prerequisites (needed by summary plots data fetch)
        dlc.DLCProcessor.populate()
        dlc.DLCKptsDf.populate()
        dlc.SyncDLCKptsDf.populate()
        dlc.OfflineKinematics.populate()

        # Pre-import lazy dependencies BEFORE any SummaryPlots.populate()
        # call. This is the key fix: these imports trigger @schema table
        # declarations which must happen outside a transaction in DJ 2.0.
        from vr4mice.schema import base  # noqa: F401
        from base_schemas.schemas import exp, mice  # noqa: F401

        # Monkeypatch vr4mice_summary_plots to avoid /data path and
        # heavy matplotlib rendering
        summary_dir = tmp_path / "summary_plots"
        summary_dir.mkdir()

        def mock_summary_plots(key, save_path=None, database=False):
            path = summary_dir / f"{key['dataset']}_summary.png"
            path.touch()
            return str(path)

        # PR #291 moved vr4mice_summary_plots back to a module-level import,
        # so we patch the module attribute.
        monkeypatch.setattr(
            base_analysis,
            "vr4mice_summary_plots",
            mock_summary_plots,
        )

        # Populate SummaryPlots
        base_analysis.SummaryPlots.populate()

    def test_summaryplots_populates(self, populated_db, golden_baseline):
        """Verify SummaryPlots.populate() creates entry."""
        from vr4mice.schema import base_analysis

        count = len(base_analysis.SummaryPlots())
        golden_baseline.check_row_count("summaryplots", count)

    def test_summaryplots_filename(self, populated_db):
        """Verify SummaryPlots stores a valid filename."""
        from vr4mice.schema import base_analysis

        row = base_analysis.SummaryPlots.fetch(as_dict=True)
        assert len(row) == 1, f"Expected 1 SummaryPlots row, got {len(row)}"
        filename = row[0]["filename"]
        assert filename, "SummaryPlots filename is empty"
        assert "summary" in filename.lower(), f"Unexpected filename: {filename}"

    # TrackingSummaryPlots deprecated in PR #291


# ==============================================================================
# Fetch Mode Tests
# ==============================================================================


class TestFetchMode:
    """Tests for fetch mode - independent of pipeline, creates GUI menu file."""

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
