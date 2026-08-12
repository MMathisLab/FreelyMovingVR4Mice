"""Unit tests for the VR-to-NP barcode alignment fit, plus guards that
behavioral analysis stays unaffected when np_pipeline is unavailable.
"""

import importlib
import sys
import ast
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


def _top_level_function_source(file_text: str, function_name: str) -> str:
    """Return source for a top-level function using AST locations."""
    module = ast.parse(file_text)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(file_text, node)
    raise ValueError(f"Function not found: {function_name}")


def _load_schema_helpers():
    """Load pure helper functions from schema np_sync source without importing DB deps."""
    text = SCHEMA_NP_SYNC_PY.read_text()
    namespace = {}
    for function_name in (
        "_dataset_identity",
        "_candidate_sort_key",
    ):
        exec(_top_level_function_source(text, function_name), namespace)
    return namespace


def test_schema_dataset_identity_parses():
    dataset_identity = _load_schema_helpers()["_dataset_identity"]

    assert dataset_identity("Xestia_2026-07-01_1") == (
        "Xestia",
        "2026-07-01",
        1,
    )
    assert dataset_identity("bad_name") is None


def test_schema_candidate_sort_key_prefers_identity_then_event_count():
    helper_ns = _load_schema_helpers()
    candidate_sort_key = helper_ns["_candidate_sort_key"]

    identity = ("Xestia", "2026-07-01", 2)

    # Exact identity match should beat higher event count with wrong attempt.
    exact = {
        "mouse_name": "Xestia",
        "day": "2026-07-01",
        "attempt": 2,
        "np_event_count": 10,
        "recording_id": "rec_a",
        "probe_serial_number": "p1",
    }
    wrong_attempt_but_more_events = {
        "mouse_name": "Xestia",
        "day": "2026-07-01",
        "attempt": 1,
        "np_event_count": 999,
        "recording_id": "rec_b",
        "probe_serial_number": "p1",
    }

    ranked = sorted(
        [wrong_attempt_but_more_events, exact],
        key=lambda row: candidate_sort_key(row, identity),
    )
    assert ranked[0]["recording_id"] == "rec_a"

    # Within the same identity, higher np_event_count should win.
    same_identity_low = {
        **exact,
        "np_event_count": 5,
        "recording_id": "rec_low",
    }
    same_identity_high = {
        **exact,
        "np_event_count": 25,
        "recording_id": "rec_high",
    }
    ranked_same = sorted(
        [same_identity_low, same_identity_high],
        key=lambda row: candidate_sort_key(row, identity),
    )
    assert ranked_same[0]["recording_id"] == "rec_high"


def test_schema_candidate_sort_key_without_identity_prefers_event_count():
    candidate_sort_key = _load_schema_helpers()["_candidate_sort_key"]

    low = {
        "np_event_count": 5,
        "recording_id": "rec_low",
        "probe_serial_number": "p1",
    }
    high = {
        "np_event_count": 50,
        "recording_id": "rec_high",
        "probe_serial_number": "p2",
    }

    ranked = sorted([low, high], key=lambda row: candidate_sort_key(row, None))
    assert ranked[0]["recording_id"] == "rec_high"


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
