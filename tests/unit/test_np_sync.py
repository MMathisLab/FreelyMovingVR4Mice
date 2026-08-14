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
SCHEMA_DECISION_PY = REPO_ROOT / "dj_pipeline" / "vr4mice" / "schema" / "decision.py"


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
    assert len(fit.shared_barcodes) == 20


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


def test_align_barcodes_skip_first_n_excludes_leading_vr_events():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(n=20)
    # Corrupt the first two VR onset times so an unskipped fit would be biased.
    vr_times = vr_times.copy()
    vr_times[:2] += 1000.0

    biased_fit = align_barcodes(vr_times, vr_values, np_times, np_values)
    assert biased_fit.slope != pytest.approx(2.0)

    corrected_fit = align_barcodes(
        vr_times, vr_values, np_times, np_values, skip_first_n_barcodes=2
    )
    assert corrected_fit.slope == pytest.approx(2.0)
    assert corrected_fit.intercept == pytest.approx(100.0)
    assert len(corrected_fit.shared_barcodes) == 18


def test_align_barcodes_interpol_func_maps_vr_time_to_np_time():
    vr_times, vr_values, np_times, np_values = _linear_barcode_streams(
        slope=2.0, intercept=100.0
    )

    fit = align_barcodes(vr_times, vr_values, np_times, np_values)

    assert fit.interpol_func(5.0) == pytest.approx(110.0)


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


def test_run_py_decision_mode_orders_datasetbatch_before_decision_tables():
    text = RUN_PY.read_text()
    start = text.index('elif args.mode == "decision":')
    end = text.index('elif args.mode == "np_sync":')
    block = text[start:end]

    sync_lookup_idx = block.index("decision.sync_lookup_contents()")
    dataset_batch_idx = block.index("vr4mice.DatasetBatch().populate()")
    member_idx = block.index("decision.ExperimentMember().populate()")

    assert sync_lookup_idx < dataset_batch_idx < member_idx


def test_cron_scenario_orders_batch_sync_before_datasetbatch_and_gates_decision_on_core():
    text = CRON_SCENARIO_PY.read_text()

    batch_sync_idx = text.index('"vr4mice.Batch.sync_contents"')
    dataset_batch_idx = text.index('"vr4mice.DatasetBatch.populate"')
    decision_gate_idx = text.index("if decision and core_schemas:")
    decision_member_idx = text.index('"decision.ExperimentMember.populate"')

    assert batch_sync_idx < dataset_batch_idx < decision_gate_idx < decision_member_idx


def test_decision_experimentmember_key_source_is_datasetbatch_lineaged():
    text = SCHEMA_DECISION_PY.read_text()
    start = text.index("class ExperimentMember")
    end = text.index("class InclusionStatus")
    block = text[start:end]

    assert "def key_source(self):" in block
    assert "return vr4mice.DatasetBatch" in block


def test_schema_make_handles_empty_np_events_with_clear_reason():
    text = SCHEMA_NP_SYNC_PY.read_text()
    make_src = _function_source(text, "    def make(self, key):")

    assert "if len(np_values) == 0:" in make_src
    assert "No NP barcode events found for key at populate time" in make_src


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
    assert "Insufficient shared barcodes for reliable NP-VR alignment" in make_src
    assert "Insufficient NP-VR barcode overlap for reliable alignment" in make_src


def test_schema_module_docstring_states_vr_only_sessions_excluded_from_key_source():
    text = SCHEMA_NP_SYNC_PY.read_text()

    assert "so VR-only datasets are excluded from this table" in text
    assert "are not visited by" in text
