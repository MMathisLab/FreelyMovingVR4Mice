"""Unit tests for DLC/interpolation schema error-handling branches."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DLC_MODULE_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "dlc.py"
INTERP_MODULE_PATH = (
    PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "interpolated_trajectories.py"
)


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
