"""Unit tests for the DLC and interpolated trajectory schemas: error-handling
branches and the InterpolatedTrials sample grid (utils.trial_grid_times)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DLC_MODULE_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "dlc.py"
INTERP_MODULE_PATH = (
    PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "interpolated_trajectories.py"
)
VR4MICE_CORE_MODULE_PATH = (
    PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "vr4mice.py"
)
ANALYSIS_UTILS_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "analysis" / "utils.py"


def _identity_schema_decorator(_name, _locals):
    def decorator(cls):
        return cls

    return decorator


def _load_module(module_name: str, module_path: Path, stubs: dict):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs, clear=False):
        spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def dlc_module():
    dj_stub = ModuleType("datajoint")
    dj_stub.Imported = type("Imported", (), {})
    dj_stub.Computed = type("Computed", (), {})

    logger_mod = ModuleType("vr4mice.utils.logger")
    logger_mod.Logger = type(
        "Logger",
        (),
        {"get_logger": staticmethod(lambda: MagicMock())},
    )

    schema_config_mod = ModuleType("vr4mice.utils.schema_config")
    schema_config_mod.get_schema = _identity_schema_decorator

    utils_pkg = ModuleType("vr4mice.utils")
    utils_pkg.logger = logger_mod
    utils_pkg.schema_config = schema_config_mod

    schema_pkg = ModuleType("vr4mice.schema")
    vr4mice_schema_mod = ModuleType("vr4mice.schema.vr4mice")
    vr4mice_schema_mod.DLC = MagicMock()
    vr4mice_schema_mod.FailedSession = MagicMock()
    schema_pkg.vr4mice = vr4mice_schema_mod

    analysis_pkg = ModuleType("vr4mice.analysis")
    dlc_helpers_mod = ModuleType("vr4mice.analysis.dlc_helpers")
    dlc_helpers_mod.sync_keypoint_table = MagicMock()
    dlc_helpers_mod.df_to_dj = MagicMock(
        return_value={"data": [], "headers": [], "scorer": None}
    )
    dlc_helpers_mod.get_offline_dlc_variables = MagicMock(return_value=pd.DataFrame())
    analysis_pkg.dlc_helpers = dlc_helpers_mod

    vr4mice_pkg = ModuleType("vr4mice")
    vr4mice_pkg.schema = schema_pkg
    vr4mice_pkg.analysis = analysis_pkg
    vr4mice_pkg.utils = utils_pkg

    stubs = {
        "datajoint": dj_stub,
        "vr4mice": vr4mice_pkg,
        "vr4mice.schema": schema_pkg,
        "vr4mice.schema.vr4mice": vr4mice_schema_mod,
        "vr4mice.analysis": analysis_pkg,
        "vr4mice.analysis.dlc_helpers": dlc_helpers_mod,
        "vr4mice.utils": utils_pkg,
        "vr4mice.utils.logger": logger_mod,
        "vr4mice.utils.schema_config": schema_config_mod,
    }
    return _load_module("_dlc_error_paths_unit_test", DLC_MODULE_PATH, stubs)


@pytest.fixture(scope="module")
def interp_module():
    dj_stub = ModuleType("datajoint")
    dj_stub.Computed = type("Computed", (), {})
    dj_errors_mod = ModuleType("datajoint.errors")
    dj_errors_mod.DuplicateError = type("DuplicateError", (Exception,), {})
    dj_stub.errors = dj_errors_mod

    logger_mod = ModuleType("vr4mice.utils.logger")
    logger_mod.Logger = type(
        "Logger",
        (),
        {"get_logger": staticmethod(lambda: MagicMock())},
    )

    schema_config_mod = ModuleType("vr4mice.utils.schema_config")
    schema_config_mod.get_schema = _identity_schema_decorator

    utils_schema_pkg = ModuleType("vr4mice.utils")
    utils_schema_pkg.logger = logger_mod
    utils_schema_pkg.schema_config = schema_config_mod

    vr4mice_schema_mod = ModuleType("vr4mice.schema.vr4mice")
    vr4mice_schema_mod.FailedSession = MagicMock()

    dataframe_stub = MagicMock()
    box_stub = MagicMock()
    base_analysis_mod = ModuleType("vr4mice.schema.base_analysis")
    base_analysis_mod.DataFrame = dataframe_stub
    base_analysis_mod.BoxDataFrame = box_stub

    dlc_schema_mod = ModuleType("vr4mice.schema.dlc")
    dlc_schema_mod.OfflineKinematics = MagicMock()

    schema_pkg = ModuleType("vr4mice.schema")
    schema_pkg.vr4mice = vr4mice_schema_mod
    schema_pkg.base_analysis = base_analysis_mod
    schema_pkg.dlc = dlc_schema_mod

    analysis_utils_mod = ModuleType("vr4mice.analysis.utils")
    analysis_utils_mod.interpolate_j_shaped = MagicMock()
    analysis_pkg = ModuleType("vr4mice.analysis")
    analysis_pkg.utils = analysis_utils_mod

    vr4mice_pkg = ModuleType("vr4mice")
    vr4mice_pkg.schema = schema_pkg
    vr4mice_pkg.utils = utils_schema_pkg
    vr4mice_pkg.analysis = analysis_pkg

    stubs = {
        "datajoint": dj_stub,
        "datajoint.errors": dj_errors_mod,
        "vr4mice": vr4mice_pkg,
        "vr4mice.schema": schema_pkg,
        "vr4mice.schema.vr4mice": vr4mice_schema_mod,
        "vr4mice.schema.base_analysis": base_analysis_mod,
        "vr4mice.schema.dlc": dlc_schema_mod,
        "vr4mice.utils": utils_schema_pkg,
        "vr4mice.utils.logger": logger_mod,
        "vr4mice.utils.schema_config": schema_config_mod,
        "vr4mice.analysis": analysis_pkg,
        "vr4mice.analysis.utils": analysis_utils_mod,
    }

    return _load_module(
        "_interpolated_error_paths_unit_test",
        INTERP_MODULE_PATH,
        stubs,
    )


@pytest.fixture(scope="module")
def vr4mice_core_module():
    dj_stub = ModuleType("datajoint")
    dj_stub.Lookup = type("Lookup", (), {})
    dj_stub.Manual = type("Manual", (), {})
    dj_stub.Computed = type("Computed", (), {})

    logger_mod = ModuleType("vr4mice.utils.logger")
    logger_mod.Logger = type(
        "Logger",
        (),
        {"get_logger": staticmethod(lambda: MagicMock())},
    )

    schema_config_mod = ModuleType("vr4mice.utils.schema_config")
    schema_config_mod.get_schema = _identity_schema_decorator

    utils_pkg = ModuleType("vr4mice.utils")
    utils_pkg.logger = logger_mod
    utils_pkg.schema_config = schema_config_mod

    populate_rig_mod = ModuleType("vr4mice.actions.populate_rig")
    populate_rig_mod.get_files_paths = MagicMock()

    actions_pkg = ModuleType("vr4mice.actions")
    actions_pkg.__path__ = []
    actions_pkg.populate_rig = populate_rig_mod

    schema_pkg = ModuleType("vr4mice.schema")

    vr4mice_pkg = ModuleType("vr4mice")
    vr4mice_pkg.utils = utils_pkg
    vr4mice_pkg.actions = actions_pkg
    vr4mice_pkg.schema = schema_pkg

    stubs = {
        "datajoint": dj_stub,
        "vr4mice": vr4mice_pkg,
        "vr4mice.utils": utils_pkg,
        "vr4mice.utils.logger": logger_mod,
        "vr4mice.utils.schema_config": schema_config_mod,
        "vr4mice.actions": actions_pkg,
        "vr4mice.actions.populate_rig": populate_rig_mod,
        "vr4mice.schema": schema_pkg,
    }

    with patch.dict("os.environ", {"DJ_LAB": "mathis-lab"}, clear=False):
        return _load_module(
            "_vr4mice_core_error_paths_unit_test",
            VR4MICE_CORE_MODULE_PATH,
            stubs,
        )


class _AlwaysMissingTable:
    heading = SimpleNamespace(names=[])
    primary_key = []

    def __init__(self):
        self.insert1 = MagicMock()

    def __and__(self, key):
        return False


class _SelfRelation:
    def __init__(self, fetch1_value=None, fetch_value=None, primary_key=None):
        self._fetch1_value = fetch1_value
        self._fetch_value = fetch_value if fetch_value is not None else []
        self.primary_key = primary_key or ["dataset", "camera", "doe"]

    def __and__(self, key):
        return self

    def fetch1(self, field):
        return self._fetch1_value

    def fetch(self, *args, **kwargs):
        return self._fetch_value


class TestDlcErrorPaths:
    def test_complete_dlc_key_raises_when_no_match(self, dlc_module):
        rel = _SelfRelation(fetch_value=[], primary_key=["dataset", "camera", "doe"])
        dlc_module.vr4mice.DLC = MagicMock(return_value=rel)

        with pytest.raises(KeyError):
            dlc_module._complete_dlc_key({"dataset": "Whale_2026-07-08_1"})

    def test_dlcprocessor_make_records_failed_session_on_load_error(self, dlc_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        table = _AlwaysMissingTable()

        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        dlc_module.vr4mice.FailedSession = failed_session_cls

        dlc_module.vr4mice.DLC = MagicMock(
            return_value=_SelfRelation(fetch1_value="/tmp/proc.npy")
        )

        with patch.object(dlc_module.Path, "is_file", return_value=True), patch.object(
            dlc_module.np, "load", side_effect=RuntimeError("bad proc")
        ):
            result = dlc_module.DLCProcessor.make(table, key)

        assert result is None
        failed_session_row.add_entry.assert_called_once()


class TestVr4miceDlcTransientInvariant:
    def test_dlc_make_missing_file_is_transient_then_late_file_inserts(
        self, vr4mice_core_module, tmp_path
    ):
        """Missing DLC/PROC must be transient (no FailedSession), then insert later."""

        module = vr4mice_core_module
        make_fn = module.DLC.make
        key = {
            "dataset": "Whale_2026-07-08_1",
            "camera": "Imagingsource",
            "doe": "2026-07-08",
            "model_name": "DLC",
        }

        # FailedSession must not be touched on transient missing files.
        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        module.FailedSession = failed_session_cls

        # Patch global DLC() insert target used inside DLC.make.
        inserted_rows = []

        class _InsertTarget:
            def insert1(self, data, skip_duplicates=True):
                inserted_rows.append((data, skip_duplicates))

        module.DLC = MagicMock(return_value=_InsertTarget())

        # `self & key` duplicate guard should be false in both passes.
        class _SelfTable:
            def __and__(self, _key):
                return False

        self_table = _SelfTable()

        dlc_file = tmp_path / "dlc_video" / "Imagingsource_Whale_2026-07-08_1_DLC.hdf5"
        proc_file = tmp_path / "dlc_video" / "Imagingsource_Whale_2026-07-08_1_PROC"

        actions_pkg = ModuleType("vr4mice.actions")
        actions_pkg.__path__ = []
        populate_rig_mod = ModuleType("vr4mice.actions.populate_rig")
        populate_rig_mod.get_files_paths = lambda *_args, **_kwargs: {
            "dlc_path": {
                "dst": str(dlc_file.parent),
                "filename": dlc_file.name,
            },
            "proc_path": {
                "dst": str(proc_file.parent),
                "filename": proc_file.name,
            },
        }

        with patch.dict(
            sys.modules,
            {
                "vr4mice.actions": actions_pkg,
                "vr4mice.actions.populate_rig": populate_rig_mod,
            },
            clear=False,
        ):
            # Pass 1: files absent -> transient skip, no FailedSession, no insert.
            make_fn(self_table, key)
            assert inserted_rows == []
            failed_session_row.add_entry.assert_not_called()

            # Pass 2: files appear later -> insert succeeds.
            dlc_file.parent.mkdir(parents=True, exist_ok=True)
            dlc_file.touch()
            proc_file.touch()

            make_fn(self_table, key)
            assert len(inserted_rows) == 1
            inserted_data, skip_duplicates = inserted_rows[0]
            assert skip_duplicates is True
            assert inserted_data["dataset"] == key["dataset"]
            assert inserted_data["keypoints_filepath"].endswith("_DLC.hdf5")
            assert inserted_data["proc_filepath"].endswith("_PROC")
            failed_session_row.add_entry.assert_not_called()

    def test_dlcprocessor_make_missing_file_is_transient_skip(self, dlc_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        table = _AlwaysMissingTable()

        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        dlc_module.vr4mice.FailedSession = failed_session_cls

        dlc_module.vr4mice.DLC = MagicMock(
            return_value=_SelfRelation(fetch1_value="/tmp/missing_proc.npy")
        )

        with patch.object(dlc_module.Path, "is_file", return_value=False):
            result = dlc_module.DLCProcessor.make(table, key)

        assert result is None
        failed_session_row.add_entry.assert_not_called()

    def test_syncdlckptsdf_make_records_failed_session_on_sync_error(self, dlc_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        table = _AlwaysMissingTable()

        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        dlc_module.vr4mice.FailedSession = failed_session_cls

        dlc_module.dlc_helpers.sync_keypoint_table = MagicMock(
            side_effect=ValueError("sync failed")
        )

        result = dlc_module.SyncDLCKptsDf.make(table, key)

        assert result is None
        failed_session_row.add_entry.assert_called_once()

    def test_offlinekinematics_missing_sync_data_records_failure(self, dlc_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        table = _AlwaysMissingTable()

        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        dlc_module.vr4mice.FailedSession = failed_session_cls

        dlc_module.SyncDLCKptsDf = MagicMock(
            return_value=MagicMock(get_data=MagicMock(return_value=None))
        )

        result = dlc_module.OfflineKinematics.make(table, key)

        assert result is None
        failed_session_row.add_entry.assert_called_once()


class TestInterpolatedErrorPaths:
    def _setup_base_analysis(self, interp_module):
        key = {"dataset": "Whale_2026-07-08_1"}

        class _DataFrameRel:
            def __and__(self, _key):
                return self

            def __len__(self):
                return 1

            def __call__(self):
                return self

            def get_data(self, key=None):
                return pd.DataFrame({"iti": [0.0], "x": [1.0], "flip_one_side": [1.0]})

            def get_rewarded(self, key=None):
                return [1]

        class _BoxRel:
            def __call__(self):
                return self

            def get_data(self, key=None):
                return pd.DataFrame({"x": [0.0], "y": [0.0]})

        interp_module.base_analysis.DataFrame = _DataFrameRel()
        interp_module.base_analysis.BoxDataFrame = _BoxRel()

        failed_session_row = MagicMock()
        failed_session_cls = MagicMock(return_value=failed_session_row)
        failed_session_cls.should_skip = MagicMock(return_value=False)
        interp_module.vr4mice.FailedSession = failed_session_cls

        return key, failed_session_row

    def test_interpolated_trials_skips_when_offline_missing(self, interp_module):
        key, failed_session_row = self._setup_base_analysis(interp_module)
        table = _AlwaysMissingTable()

        interp_module.dlc.OfflineKinematics = MagicMock(
            return_value=MagicMock(get_data=MagicMock(return_value=None))
        )

        analysis_pkg = ModuleType("vr4mice.analysis")
        analysis_pkg.__path__ = []
        analysis_utils_mod = ModuleType("vr4mice.analysis.utils")
        analysis_utils_mod.interpolate_j_shaped = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "vr4mice.analysis": analysis_pkg,
                "vr4mice.analysis.utils": analysis_utils_mod,
            },
            clear=False,
        ):
            interp_module.InterpolatedTrials.make(table, key)

        table.insert1.assert_not_called()
        failed_session_row.add_entry.assert_called_once()

    def test_interpolated_trials_records_failed_session_on_interpolate_error(
        self, interp_module
    ):
        key, failed_session_row = self._setup_base_analysis(interp_module)
        table = _AlwaysMissingTable()

        interp_module.dlc.OfflineKinematics = MagicMock(
            return_value=MagicMock(
                get_data=MagicMock(
                    return_value=pd.DataFrame(
                        {"heading_dir": [0.0], "head_angle": [0.0]}
                    )
                )
            )
        )

        analysis_pkg = ModuleType("vr4mice.analysis")
        analysis_pkg.__path__ = []
        analysis_utils_mod = ModuleType("vr4mice.analysis.utils")
        analysis_utils_mod.interpolate_j_shaped = MagicMock(
            side_effect=RuntimeError("interpolation failed")
        )

        with patch.dict(
            sys.modules,
            {
                "vr4mice.analysis": analysis_pkg,
                "vr4mice.analysis.utils": analysis_utils_mod,
            },
            clear=False,
        ):
            interp_module.InterpolatedTrials.make(table, key)

        failed_session_row.add_entry.assert_called_once()


@pytest.fixture(scope="module")
def analysis_utils():
    # Own module name, so it does not shadow the ``utils`` package of other
    # tests; the unused vr4mice.analysis.analysis import gets a placeholder.
    return _load_module(
        "analysis_utils_grid",
        ANALYSIS_UTILS_PATH,
        {"vr4mice.analysis.analysis": ModuleType("vr4mice.analysis.analysis")},
    )


def _retained_rows():
    """20 ms rows of two trials after dropping incomplete rows.

    Trial 1 lost its first three rows (missing pose), so its retained rows start
    at index 3 (0.06 s); trial 2 lost a row in the middle.
    """
    index = [3, 4, 5, 6, 7, 10, 11, 13, 14]
    step_time = 0.02 * np.array(index, dtype=float)
    return pd.DataFrame(
        {
            "dataset": "d",
            "trial": [1, 1, 1, 1, 1, 2, 2, 2, 2],
            "step_time": step_time,
            "x": step_time * 10,
        },
        index=index,
    )


class TestTrialSampleGrid:
    def test_grid_spans_the_retained_rows_of_each_trial(self, analysis_utils):
        grid = analysis_utils.trial_grid_times(_retained_rows(), n_points=5)

        trial1 = grid[grid.trial == 1]
        assert trial1["trial_step"].tolist() == [0, 1, 2, 3, 4]
        # Starts at the first retained row (0.06 s), not the trial's first step
        np.testing.assert_allclose(trial1["step_time"], np.linspace(0.06, 0.14, 5))
        trial2 = grid[grid.trial == 2]
        np.testing.assert_allclose(trial2["step_time"], np.linspace(0.20, 0.28, 5))

    def test_grid_times_are_the_interpolated_samples(self, analysis_utils):
        rows = _retained_rows()

        grid = analysis_utils.trial_grid_times(rows, n_points=5)
        interpolated = analysis_utils.interpolate(
            rows,
            n_points=5,
            value_columns=["step_time"],
            interpolation_columns=["dataset", "trial"],
        )

        # Same sample positions, so the same moments (step_time is linear in
        # the index here, so the spline reproduces it exactly)
        np.testing.assert_allclose(grid["step_time"], interpolated["step_time"])
        assert grid["trial"].tolist() == interpolated["trial"].astype(int).tolist()


class _FailedSessions:
    entries = []

    @staticmethod
    def should_skip(*_):
        return False

    def add_entry(self, *entry):
        self.entries.append(entry)


class _StoredTrials:
    """InterpolatedTrials with one session's stored samples and inputs."""

    def __init__(self, trials, rows):
        self.trials, self.rows = trials, rows

    def __and__(self, _key):
        return self

    def fetch1(self, _attribute):
        return self.trials

    def load_inputs(self, _key):
        return self.rows, None


class TestTrialSampleTimes:
    def _make(self, interp_module, analysis_utils, monkeypatch, stored_trials):
        utils_mod = ModuleType("vr4mice.analysis.utils")
        utils_mod.prepare_j_shaped_trials = lambda rows, _box: (rows, [])
        utils_mod.trial_grid_times = lambda rows: analysis_utils.trial_grid_times(
            rows, n_points=5
        )
        monkeypatch.setitem(sys.modules, "vr4mice.analysis.utils", utils_mod)
        monkeypatch.setattr(interp_module.vr4mice, "FailedSession", _FailedSessions)
        monkeypatch.setattr(_FailedSessions, "entries", [])
        monkeypatch.setattr(
            interp_module,
            "InterpolatedTrials",
            _StoredTrials(stored_trials, _retained_rows()),
        )
        inserted = []
        table = interp_module.TrialSampleTimes()
        table.insert1 = inserted.append
        interp_module.TrialSampleTimes.make(table, {"dataset": "d"})
        return inserted, _FailedSessions.entries

    def test_stores_the_sample_times_of_the_stored_trials(
        self, interp_module, analysis_utils, monkeypatch
    ):
        inserted, failures = self._make(
            interp_module, analysis_utils, monkeypatch, [1.0] * 5 + [2.0] * 5
        )

        assert not failures
        (row,) = inserted
        assert row["dataset"] == "d"
        np.testing.assert_array_equal(row["trial"], [1] * 5 + [2] * 5)
        np.testing.assert_array_equal(row["trial_step"], [0, 1, 2, 3, 4] * 2)
        np.testing.assert_allclose(
            row["step_time"], np.r_[np.linspace(0.06, 0.14, 5), np.linspace(0.2, 0.28, 5)]
        )

    def test_samples_not_matching_interpolated_trials_fail_the_session(
        self, interp_module, analysis_utils, monkeypatch
    ):
        # InterpolatedTrials was computed from other rows: trial 2 is missing
        inserted, failures = self._make(
            interp_module, analysis_utils, monkeypatch, [1.0] * 5
        )

        assert not inserted
        ((dataset, table, reason),) = failures
        assert (dataset, table) == ("d", "TrialSampleTimes")
        assert "repopulate InterpolatedTrials" in reason
