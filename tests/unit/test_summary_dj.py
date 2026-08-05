"""Unit tests for summary_dj naming helpers."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "dj_pipeline" / "vr4mice" / "analysis" / "summary_dj.py"


@pytest.fixture(scope="module")
def summary_dj_module():
    spec = importlib.util.spec_from_file_location("_summary_dj_unit_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "matplotlib": MagicMock(),
        "matplotlib.pyplot": MagicMock(),
        "seaborn": MagicMock(),
    }
    with patch.dict(sys.modules, stubs, clear=False):
        spec.loader.exec_module(module)
    return module


class TestSummaryDjHelpers:
    def test_get_path_builds_expected_filename(self, summary_dj_module, tmp_path):
        key = {"dataset": "Whale_2026-07-08_1"}

        result = summary_dj_module.get_path(key=key, base=str(tmp_path), ext=".png")

        assert result.name == "Whale_2026-07-08_1_summary_plot.png"
        assert result.parent == tmp_path

    def test_get_subtitle_includes_task_and_dataset(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}

        result = summary_dj_module.get_subtitle(key=key, task_name="Active Sensing")

        assert result == "Active Sensing: Dataset: Whale_2026-07-08_1"

    def test_get_path_custom_extension(self, summary_dj_module, tmp_path):
        key = {"dataset": "Whale_2026-07-08_1"}

        result = summary_dj_module.get_path(key=key, base=str(tmp_path), ext=".svg")

        assert result.name == "Whale_2026-07-08_1_summary_plot.svg"

    def test_get_subtitle_uses_default_task_name(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}

        result = summary_dj_module.get_subtitle(key=key)

        assert result == "AR Task: Dataset: Whale_2026-07-08_1"


class TestInterpolatedSummaryFallback:
    def test_fallback_interpolation_adds_trial_step_and_length(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        source_df = pd.DataFrame(
            {
                "dataset": ["Whale_2026-07-08_1", "Whale_2026-07-08_1"],
                "trial": [1, 2],
                "trial_right_choice": [0, 1],
                "trial_rewarded": [1, 0],
                "y": [0.1, 0.2],
                "head_dir": [10.0, 20.0],
                "trial_tortuosity": [1.0, 1.1],
                "trial_duration": [5.0, 6.0],
                "x": [1.0, 2.0],
                "aperture": [0.0, 0.5],
                "velocity": [10.0, 11.0],
                "velocity_x": [1.0, 1.1],
                "velocity_y": [2.0, 2.1],
                "trial_traj_path_length": [30.0, 31.0],
                "flip_one_side": [1.0, -1.0],
            }
        )

        interpolated = pd.DataFrame(
            {
                "dataset": ["Whale_2026-07-08_1"] * 4,
                "trial": [1, 1, 2, 2],
                "trial_right_choice": [0, 0, 1, 1],
                "trial_rewarded": [1, 1, 0, 0],
                "y": [0.1, 0.11, 0.2, 0.21],
                "head_dir": [10.0, 10.5, 20.0, 20.5],
                "trial_tortuosity": [1.0, 1.0, 1.1, 1.1],
                "trial_duration": [5.0, 5.0, 6.0, 6.0],
                "x": [1.0, 1.1, 2.0, 2.1],
                "aperture": [0.0, 0.0, 0.5, 0.5],
                "velocity": [10.0, 10.1, 11.0, 11.1],
                "velocity_x": [1.0, 1.01, 1.1, 1.11],
                "velocity_y": [2.0, 2.01, 2.1, 2.11],
                "trial_traj_path_length": [30.0, 30.1, 31.0, 31.1],
                "flip_one_side": [1.0, 1.0, -1.0, -1.0],
            }
        )

        def fake_interpolate(df, n_points, value_columns):
            assert n_points == 200
            assert "trial_right_choice" in value_columns
            assert "trial_rewarded" in value_columns
            return interpolated.copy()

        utils_mod = ModuleType("vr4mice.analysis.utils")
        utils_mod.interpolate = fake_interpolate
        analysis_mod = ModuleType("vr4mice.analysis")
        analysis_mod.utils = utils_mod

        with patch.dict(
            sys.modules,
            {
                "vr4mice.analysis": analysis_mod,
                "vr4mice.analysis.utils": utils_mod,
            },
            clear=False,
        ):
            result = summary_dj_module._get_interpolated_summary_df(
                key=key,
                df=source_df,
                database=False,
            )

        assert list(result["trial_step"]) == [0, 1, 0, 1]
        assert list(result["trial_length"]) == [0.0, 0.005, 0.0, 0.005]


class TestInterpolatedSummaryDatabasePath:
    def test_database_interpolated_trials_used_when_available(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}

        class _Rel:
            def __and__(self, _key):
                return self

            def __len__(self):
                return 1

            def fetch(self, *args, **kwargs):
                return [
                    {
                        "dataset": ["Whale_2026-07-08_1", "Whale_2026-07-08_1"],
                        "trial": [1, 2],
                        "trial_length": [0.2, 0.4],
                        "aperture": [0.0, 0.5],
                        "trial_rewarded": [1, 0],
                        "trial_left_choice": [1, 0],
                        "heading_dir": [10.0, 20.0],
                        "velocity": [5.0, 6.0],
                    }
                ]

        class _InterpolatedTrialsFactory:
            def __call__(self):
                return _Rel()

        interp_mod = ModuleType("vr4mice.schema.interpolated_trajectories")
        interp_mod.InterpolatedTrials = _InterpolatedTrialsFactory()
        schema_mod = ModuleType("vr4mice.schema")
        schema_mod.interpolated_trajectories = interp_mod

        utils_mod = ModuleType("vr4mice.analysis.utils")
        utils_mod.interpolate = MagicMock()
        analysis_mod = ModuleType("vr4mice.analysis")
        analysis_mod.utils = utils_mod

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_mod,
                "vr4mice.schema.interpolated_trajectories": interp_mod,
                "vr4mice.analysis": analysis_mod,
                "vr4mice.analysis.utils": utils_mod,
            },
            clear=False,
        ):
            result = summary_dj_module._get_interpolated_summary_df(
                key=key,
                df=pd.DataFrame(),
                database=True,
            )

        assert list(result["head_dir"]) == [10.0, 20.0]
        assert list(result["trial_right_choice"]) == [0, 1]

    def test_database_interpolated_trials_fallbacks_to_inline_on_error(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        source_df = pd.DataFrame(
            {
                "dataset": ["Whale_2026-07-08_1", "Whale_2026-07-08_1"],
                "trial": [1, 2],
                "trial_right_choice": [0, 1],
                "trial_rewarded": [1, 0],
                "y": [0.1, 0.2],
                "head_dir": [10.0, 20.0],
                "trial_tortuosity": [1.0, 1.1],
                "trial_duration": [5.0, 6.0],
                "x": [1.0, 2.0],
                "aperture": [0.0, 0.5],
                "velocity": [10.0, 11.0],
                "velocity_x": [1.0, 1.1],
                "velocity_y": [2.0, 2.1],
                "trial_traj_path_length": [30.0, 31.0],
                "flip_one_side": [1.0, -1.0],
            }
        )

        inline_df = pd.DataFrame(
            {
                "dataset": ["Whale_2026-07-08_1", "Whale_2026-07-08_1"],
                "trial": [1, 1],
                "trial_right_choice": [0, 0],
                "trial_rewarded": [1, 1],
                "y": [0.1, 0.11],
                "head_dir": [10.0, 10.1],
                "trial_tortuosity": [1.0, 1.0],
                "trial_duration": [5.0, 5.0],
                "x": [1.0, 1.1],
                "aperture": [0.0, 0.0],
                "velocity": [10.0, 10.1],
                "velocity_x": [1.0, 1.01],
                "velocity_y": [2.0, 2.01],
                "trial_traj_path_length": [30.0, 30.1],
                "flip_one_side": [1.0, 1.0],
            }
        )

        class _FailRel:
            def __and__(self, _key):
                raise RuntimeError("db fetch failed")

        class _InterpolatedTrialsFactory:
            def __call__(self):
                return _FailRel()

        interp_mod = ModuleType("vr4mice.schema.interpolated_trajectories")
        interp_mod.InterpolatedTrials = _InterpolatedTrialsFactory()
        schema_mod = ModuleType("vr4mice.schema")
        schema_mod.interpolated_trajectories = interp_mod

        utils_mod = ModuleType("vr4mice.analysis.utils")
        utils_mod.interpolate = MagicMock(return_value=inline_df.copy())
        analysis_mod = ModuleType("vr4mice.analysis")
        analysis_mod.utils = utils_mod

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_mod,
                "vr4mice.schema.interpolated_trajectories": interp_mod,
                "vr4mice.analysis": analysis_mod,
                "vr4mice.analysis.utils": utils_mod,
            },
            clear=False,
        ):
            result = summary_dj_module._get_interpolated_summary_df(
                key=key,
                df=source_df,
                database=True,
            )

        assert "trial_step" in result.columns
        assert "trial_length" in result.columns


class TestFetchDataPaths:
    def test_fetch_data_database_true(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        df = pd.DataFrame({"iti": [0.0], "x": [1.0]})
        box_df = pd.DataFrame({"x": [0.0], "y": [0.0]})

        class _DataFrameTable:
            def get_data(self, _key):
                return df.copy()

            def populate(self, _key):
                return None

            def get_rewarded(self, _key):
                return [1]

        class _BoxDataFrameTable:
            def get_data(self, _key):
                return box_df.copy()

            def populate(self, _key):
                return None

        base_analysis_mod = ModuleType("vr4mice.schema.base_analysis")
        base_analysis_mod.DataFrame = lambda: _DataFrameTable()
        base_analysis_mod.BoxDataFrame = lambda: _BoxDataFrameTable()
        schema_mod = ModuleType("vr4mice.schema")
        schema_mod.base_analysis = base_analysis_mod

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_mod,
                "vr4mice.schema.base_analysis": base_analysis_mod,
            },
            clear=False,
        ):
            out_df, out_box = summary_dj_module.fetch_data(key=key, database=True)

        assert "trial_rewarded" in out_df.columns
        assert list(out_df["trial_rewarded"]) == [1]
        assert out_box.equals(box_df)

    def test_fetch_data_database_false(self, summary_dj_module):
        key = {"dataset": "Whale_2026-07-08_1"}
        created_df = pd.DataFrame({"iti": [0.0], "x": [1.0]})
        box_df = pd.DataFrame({"x": [0.0], "y": [0.0]})

        analysis_mod = ModuleType("vr4mice.analysis.analysis")
        analysis_mod.create_data_frame = MagicMock(
            return_value=(created_df.copy(), {"physical_arena_size": 120})
        )
        analysis_mod.get_rewarded = MagicMock(return_value=[1])
        analysis_mod.get_box_df = MagicMock(return_value=box_df.copy())

        analysis_pkg = ModuleType("vr4mice.analysis")
        analysis_pkg.analysis = analysis_mod

        with patch.dict(
            sys.modules,
            {
                "vr4mice.analysis": analysis_pkg,
                "vr4mice.analysis.analysis": analysis_mod,
            },
            clear=False,
        ):
            out_df, out_box = summary_dj_module.fetch_data(key=key, database=False)

        assert "trial_rewarded" in out_df.columns
        assert list(out_df["trial_rewarded"]) == [1]
        assert out_box.equals(box_df)
