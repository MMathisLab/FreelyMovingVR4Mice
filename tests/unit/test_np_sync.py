"""Unit tests for the VR-to-NP barcode alignment fit, plus guards that
behavioral analysis stays unaffected when np_pipeline is unavailable.
"""

import importlib
import sys
import ast
import textwrap
import pickle
from pathlib import Path

import numpy as np
import pytest

from np_sync import align_barcodes

REPO_ROOT = Path(__file__).parent.parent.parent
RUN_PY = REPO_ROOT / "dj_pipeline" / "run.py"
CRON_SCENARIO_PY = REPO_ROOT / "dj_pipeline" / "cron_scenario.py"
SCHEMA_NP_SYNC_PY = REPO_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "np_sync.py"


def _linear_barcode_streams(*, n=20, slope=2.0, intercept=100.0, skip_vr=0, skip_np=0):
    """Two barcode streams sharing all-but-`skip_*` values, related by a known linear fit."""
    values = np.arange(n)
    vr_times = np.arange(n, dtype=np.float64)
    np_times = slope * vr_times + intercept

    vr_values = values[skip_vr:] if skip_vr else values
    vr_times = vr_times[skip_vr:] if skip_vr else vr_times
    np_values = values[skip_np:] if skip_np else values
    np_times = np_times[skip_np:] if skip_np else np_times

    return vr_times, vr_values, np_times, np_values


def test_align_barcodes_recovers_known_linear_fit():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(100.0)
    assert fit.r2 == pytest.approx(1.0)
    assert fit.rmse_ms == pytest.approx(0.0)
    assert fit.max_abs_residual_ms == pytest.approx(0.0)
    assert len(fit.shared_barcodes) == 20
    assert fit.n_trimmed_leading == 0
    assert fit.n_trimmed_trailing == 0
    assert fit.n_rejected_outliers == 0


def test_align_barcodes_is_a_no_op_on_a_clean_stream():
    """Clean sessions should be left untouched by guards and robust rejection."""
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=40)

    guarded = align_barcodes(vr_times, vr_values, np_times, np_values)
    raw = align_barcodes(
        vr_times, vr_values, np_times, np_values, reject_outliers=False
    )

    assert (guarded.slope, guarded.intercept) == (raw.slope, raw.intercept)
    assert guarded.n_rejected_outliers == 0
    assert (guarded.n_trimmed_leading, guarded.n_trimmed_trailing) == (0, 0)


def test_align_barcodes_uses_only_shared_barcode_values():
    # VR side is missing the first 3 barcode values, NP side the last 3.
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        n=20, skip_vr=3
    )
    np_values = np_values[:-3]
    np_times = np_times[:-3]

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert len(fit.shared_barcodes) == 14  # 20 - 3 leading - 3 trailing
    assert fit.slope == pytest.approx(2.0)


def test_align_barcodes_trims_repetitive_boundary_timebins():
    vr_values = np.arange(8)
    np_values = np.arange(8)

    # First two and last two events collapse onto one Unity timebin each.
    vr_times = np.array([0.0, 0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0], dtype=np.float64)
    np_times = 2.0 * np.arange(8, dtype=np.float64) + 100.0

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)
    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(100.0)
    assert len(fit.shared_barcodes) == 4
    assert fit.n_trimmed_leading == 2
    assert fit.n_trimmed_trailing == 2


def test_align_barcodes_reports_real_clamped_prefix_length():
    n = 60
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=n)
    vr_times = vr_times.copy()
    vr_times[:17] = vr_times[16]

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.n_trimmed_leading == 17
    assert len(fit.shared_barcodes) == n - 17
    assert fit.slope == pytest.approx(2.0)


def test_align_barcodes_interpol_func_maps_vr_time_to_np_time():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.interpol_func(5.0) == pytest.approx(110.0)


def test_align_barcodes_drops_non_finite_tie_points():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=40)
    vr_times = vr_times.copy()
    vr_times[4] = np.nan
    np_times = np_times.copy()
    np_times[7] = np.inf

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(100.0)
    assert len(fit.shared_barcodes) == 38


def test_align_barcodes_requires_finite_tie_points_after_filtering():
    vr_times = np.array([np.nan, np.nan, np.nan])
    vr_values = np.array([1, 2, 3])
    np_times = np.array([100.0, 101.0, 102.0])
    np_values = np.array([1, 2, 3])

    with pytest.raises(ValueError, match="finite timepoint"):
        align_barcodes(vr_times, vr_values, np_times, np_values)


def test_align_barcodes_requires_three_tie_points():
    values = np.arange(2)

    with pytest.raises(ValueError, match="at least 3"):
        align_barcodes(
            np.array([0.0, 1.0]), values, np.array([100.0, 102.0]), values
        )


def test_align_barcodes_accepts_reject_outliers_keyword():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(
        vr_times,
        vr_values,
        np_times,
        np_values,
        reject_outliers=False,
    )
    assert fit.slope == pytest.approx(2.0)


def test_align_barcodes_rejects_a_single_displaced_tie_point():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=40)
    np_times = np_times.copy()
    np_times[17] += 0.725

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.n_rejected_outliers == 1
    assert fit.slope == pytest.approx(2.0)
    assert fit.rmse_ms == pytest.approx(0.0, abs=1e-6)


def test_align_barcodes_rejection_floor_spares_unity_quantization():
    for displacement_ms, expected in ((29, 0), (31, 1)):
        vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=200)
        np_times = np_times.copy()
        np_times[100] += displacement_ms / 1000.0

        fit = align_barcodes(vr_times, vr_values, np_times, np_values)

        assert fit.n_rejected_outliers == expected, displacement_ms


def test_align_barcodes_raises_when_disagreement_is_not_isolated():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=40)
    np_times = np_times.copy()
    np_times[::4] += 0.5

    with pytest.raises(ValueError, match="not simply linear"):
        align_barcodes(vr_times, vr_values, np_times, np_values)


def test_align_barcodes_raises_on_degenerate_onset_time_unity():
    vr_values = np.arange(6)

    with pytest.raises(ValueError, match="same onset_time_unity"):
        align_barcodes(
            np.zeros(6), vr_values, np.arange(6, dtype=np.float64), vr_values
        )


def test_analysis_np_sync_has_no_datajoint_or_np_pipeline_dependency(monkeypatch):
    """The pure alignment math must import and run with np_pipeline/datajoint absent."""
    monkeypatch.setitem(sys.modules, "datajoint", None)
    monkeypatch.setitem(sys.modules, "np_pipeline", None)

    import np_sync as np_sync_analysis

    importlib.reload(np_sync_analysis)

    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )
    fit = np_sync_analysis.align_barcodes(vr_times, vr_values, np_times, np_values)
    assert fit.slope == pytest.approx(2.0)


def _function_source(file_text: str, def_line: str) -> str:
    """Return the source of a top-level-indented function, up to the next `def `."""
    start = file_text.index(def_line)
    rest = file_text[start + len(def_line) :]
    end = rest.find("\n    def ")
    return def_line + (rest if end == -1 else rest[:end])


def _load_schema_align_timepoints_method():
    """Load BarcodeSync.align_timepoints from source without importing DB deps."""
    text = SCHEMA_NP_SYNC_PY.read_text()
    module = ast.parse(text)

    method_src = None
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "BarcodeSync":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "align_timepoints":
                    method_src = ast.get_source_segment(text, item)
                    break
            break

    if method_src is None:
        raise ValueError("BarcodeSync.align_timepoints not found")

    namespace = {"np": np, "pickle": pickle}
    exec(textwrap.dedent(method_src), namespace)
    return namespace["align_timepoints"]


def test_schema_align_timepoints_preserves_none_entries():
    align_timepoints = _load_schema_align_timepoints_method()

    class _FakeRelation:
        def fetch1(self, field_name):
            assert field_name == "interpol_func"
            return pickle.dumps(np.square)

    class _FakeCls:
        def __and__(self, key):
            assert key == {"dataset": "dummy"}
            return _FakeRelation()

    aligned = align_timepoints(_FakeCls(), {"dataset": "dummy"}, [1.0, None, 2.0])
    assert aligned == [1.0, None, 4.0]


def test_cron_scenario_core_schemas_import_excludes_np_sync():
    """import_core_schemas() must not import np_sync, so a missing np_pipeline
    can't null out the whole behavioral core_schemas tuple (see import_np_sync_schema,
    which is deliberately a separate run_import() call)."""
    text = CRON_SCENARIO_PY.read_text()
    core_schemas_src = _function_source(text, "    def import_core_schemas():")

    assert "np_sync" not in core_schemas_src
    assert "def import_np_sync_schema():" in text


def test_run_py_np_sync_mode_catches_broad_exception():
    """The np_sync CLI mode must not let an import/connection failure crash the
    process; it should catch broadly and warn, not just ModuleNotFoundError."""
    text = RUN_PY.read_text()
    start = text.index('elif args.mode == "np_sync":')
    end = text.index('elif args.mode == "fetch":')
    block = text[start:end]

    assert "from vr4mice.schema import np_sync" in block
    assert "except Exception as err:" in block
    assert "except ModuleNotFoundError" not in block


def test_schema_make_handles_empty_np_events_with_clear_reason():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "if len(np_values) == 0:" in make_src
    assert "No NP barcode events found for key at populate time" in make_src


def test_schema_make_filters_non_finite_tie_point_times_before_alignment():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "vr_finite = np.isfinite(vr_times)" in make_src
    assert "np_finite = np.isfinite(np_times)" in make_src
    assert "dropped %d non-finite VR and %d non-finite NP barcode events" in make_src


def test_schema_make_uses_key_only_without_identity_parsing():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "_dataset_identity" not in make_src
    assert "_identity_matches_row" not in make_src
    assert "_select_rows_by_np_event_count" not in make_src
    assert "No NP candidate matched key fields" in make_src


def test_schema_make_fails_ambiguous_matches_directly_without_event_count_tie_break():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "Ambiguous NP candidates matched key fields" in make_src
    assert "event_count matching" not in make_src


def test_schema_make_has_quality_gate_for_min_shared_and_overlap():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "min_shared_barcodes = 20" in text
    assert "min_barcode_overlap = 0.90" in text
    assert "max_rmse_ms = 15.0" in text
    assert "Insufficient shared barcodes for reliable NP-VR alignment" in make_src
    assert "Insufficient NP-VR barcode overlap for reliable alignment" in make_src
    assert "Barcode alignment residuals too large for reliable NP-VR" in make_src
    assert "max_allowed={self.max_rmse_ms:.2f}" in make_src


def test_schema_definition_stores_alignment_diagnostics():
    text = SCHEMA_NP_SYNC_PY.read_text()

    assert "rmse_ms: float64" in text
    assert "max_abs_residual_ms: float64" in text
    assert "n_shared_barcodes: int32" in text
    assert "n_trimmed_leading: int32" in text
    assert "n_trimmed_trailing: int32" in text
    assert "n_rejected_outliers: int32" in text


def test_schema_module_docstring_states_vr_only_sessions_excluded_from_key_source():
    text = SCHEMA_NP_SYNC_PY.read_text()

    assert "so VR-only datasets are excluded from this table" in text
    assert "are not visited by" in text
