"""
Unit tests for base-schema recovery (mouse_sync, recover_base, sync_days).

Mocks DataJoint / MySQL — no parent DB required.
"""

from __future__ import annotations

import datetime
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import action modules from ACTIONS_PATH (conftest), then re-register them under
# the vr4mice.actions.* names recover_base/sync_days expect. conftest mocks
# vr4mice.actions as a MagicMock package, which would otherwise block submodule imports.
import mouse_sync
import populate_rig
import pytest

sys.modules["vr4mice.actions.mouse_sync"] = mouse_sync
sys.modules["vr4mice.actions.populate_rig"] = populate_rig

import recover_base  # noqa: E402
import sync_days  # noqa: E402
from populate_rig import _schemas_for_dataset  # noqa: E402
from sync_days import _days_from_exp_dates, _normalize_paths  # noqa: E402

# ==============================================================================
# mouse_sync helpers
# ==============================================================================


class TestIsStubMouse:
    def test_stub_id(self):
        assert mouse_sync.is_stub_mouse({"mouse_id": mouse_sync.STUB_MOUSE_ID}) is True

    def test_real_id(self):
        assert mouse_sync.is_stub_mouse({"mouse_id": 42}) is False


class TestMouseRowFromRaw:
    def test_full_metadata_row(self):
        row = mouse_sync._mouse_row_from_raw(
            {
                "mouse_id": 7,
                "dob": "2024-01-15",
                "sex": "F",
                "strain": "C57",
            },
            "Flamingo",
        )
        assert row["mouse_name"] == "Flamingo"
        assert row["mouse_id"] == 7
        assert row["dob"] == datetime.date(2024, 1, 15)
        assert row["sex"] == "F"
        assert row["strain"] == "C57"

    def test_missing_metadata_creates_stub(self):
        with patch.object(mouse_sync.mice, "Strain") as mock_strain:
            mock_strain.insert1 = MagicMock()
            row = mouse_sync._mouse_row_from_raw({"sex": "M"}, "StubMouse")
        assert row["mouse_id"] == mouse_sync.STUB_MOUSE_ID
        assert row["dob"] == mouse_sync.STUB_DOB
        assert row["strain"] == "N/A"
        mock_strain.insert1.assert_called_once()


class TestMouseNameFromRaw:
    def test_from_raw_dict(self):
        assert mouse_sync._mouse_name_from_raw({"mouse_name": "A"}) == "A"

    def test_from_dataset_filename(self):
        import types

        base_mod = types.ModuleType("vr4mice.schema.base")
        base_mod.parse_filename = lambda filename: {
            "mouse_name": "Flamingo",
            "date": "2026-02-05",
            "attempt": 1,
        }
        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []
        with patch.dict(
            sys.modules,
            {"vr4mice.schema": schema_pkg, "vr4mice.schema.base": base_mod},
        ):
            assert (
                mouse_sync._mouse_name_from_raw({}, dataset="Flamingo_2026-02-05_1")
                == "Flamingo"
            )

    def test_missing(self):
        assert mouse_sync._mouse_name_from_raw({}, dataset=None) is None


class TestEnsureMouseForSession:
    def test_skips_when_full_mouse_exists(self):
        existing = {
            "mouse_name": "Flamingo",
            "mouse_id": 1,
            "dob": "2020-01-01",
            "sex": "F",
            "strain": "X",
        }
        query = MagicMock()
        query.fetch.return_value = [existing]
        with patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=query)
            inserted = mouse_sync.ensure_mouse_for_session(
                {
                    "mouse_name": "Flamingo",
                    "mouse_id": 99,
                    "dob": "2020-01-01",
                    "sex": "F",
                    "strain": "X",
                }
            )
        assert inserted is False
        mock_mice.Mouse.insert1.assert_not_called()

    def test_upgrades_stub_when_npy_has_full_metadata(self):
        log = MagicMock()
        stub = {
            "mouse_name": "Flamingo",
            "mouse_id": mouse_sync.STUB_MOUSE_ID,
            "dob": mouse_sync.STUB_DOB,
            "sex": "U",
            "strain": "N/A",
        }
        query = MagicMock()
        query.fetch.return_value = [stub]
        with patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=query)
            mock_mice.Mouse.insert1 = MagicMock()
            inserted = mouse_sync.ensure_mouse_for_session(
                {
                    "mouse_name": "Flamingo",
                    "mouse_id": 7,
                    "dob": "2024-01-15",
                    "sex": "F",
                    "strain": "C57",
                },
                log=log,
            )
        assert inserted is True
        mock_mice.Mouse.insert1.assert_called_once()
        assert mock_mice.Mouse.insert1.call_args.kwargs.get("replace") is True
        log.info.assert_called()

    def test_inserts_stub_when_missing(self):
        log = MagicMock()
        query = MagicMock()
        query.fetch.return_value = []
        with patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=query)
            mock_mice.Strain.insert1 = MagicMock()
            mock_mice.Mouse.insert1 = MagicMock()
            inserted = mouse_sync.ensure_mouse_for_session(
                {"mouse_name": "NewMouse"}, log=log
            )
        assert inserted is True
        mock_mice.Mouse.insert1.assert_called_once()
        args = mock_mice.Mouse.insert1.call_args[0][0]
        assert args["mouse_id"] == mouse_sync.STUB_MOUSE_ID
        log.warning.assert_called()


class TestGetGuiMouseNames:
    def test_parses_npy_stems(self, tmp_path):
        (tmp_path / "Flamingo_2026-02-05_1.npy").write_bytes(b"x")
        (tmp_path / "Other_2026-01-01_2.npy").write_bytes(b"x")
        (tmp_path / "not-a-dataset.npy").write_bytes(b"x")

        import types

        base_mod = types.ModuleType("vr4mice.schema.base")

        def parse_filename(filename):
            parts = filename.split("_")
            if len(parts) < 3:
                raise ValueError("bad")
            return {
                "mouse_name": parts[0],
                "date": parts[1],
                "attempt": int(parts[2]),
            }

        base_mod.parse_filename = parse_filename
        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []

        with patch.dict(
            sys.modules,
            {"vr4mice.schema": schema_pkg, "vr4mice.schema.base": base_mod},
        ), patch(
            "vr4mice.actions.populate_rig.get_filenames",
            return_value={
                ".npy": [
                    "Flamingo_2026-02-05_1.npy",
                    "Other_2026-01-01_2.npy",
                    "not-a-dataset.npy",
                ]
            },
        ):
            names = mouse_sync.get_gui_mouse_names([str(tmp_path)])
        assert names == {"Flamingo", "Other"}

    def test_known_names_include_gui(self):
        with patch.object(
            mouse_sync, "get_session_mouse_names", return_value=set()
        ), patch.object(
            mouse_sync, "get_dataset_mouse_names", return_value=set()
        ), patch.object(
            mouse_sync, "get_gui_mouse_names", return_value={"FromDisk"}
        ):
            assert mouse_sync.get_known_local_mouse_names() == {"FromDisk"}


class TestCleanupMiceWithoutSessions:
    def test_dry_run_lists_stub_orphans(self):
        rows = [
            {"mouse_name": "Keep", "mouse_id": 1},
            {"mouse_name": "OrphanStub", "mouse_id": mouse_sync.STUB_MOUSE_ID},
            {"mouse_name": "OrphanReal", "mouse_id": 9},
        ]
        with patch.object(
            mouse_sync, "get_session_mouse_names", return_value={"Keep"}
        ), patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.fetch.return_value = rows
            count = mouse_sync.cleanup_mice_without_sessions(
                dry_run=True, stubs_only=True
            )
        assert count == 1  # OrphanStub only

    def test_force_deletes_stub_orphans(self):
        rows = [
            {"mouse_name": "OrphanStub", "mouse_id": mouse_sync.STUB_MOUSE_ID},
        ]
        with patch.object(
            mouse_sync, "get_session_mouse_names", return_value=set()
        ), patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.fetch.return_value = rows
            restricted = MagicMock()
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=restricted)
            count = mouse_sync.cleanup_mice_without_sessions(
                dry_run=False, stubs_only=True
            )
        assert count == 1
        restricted.delete.assert_called_once()


class TestEnsureWaterRestrictionOnFkTable:
    def test_mirrors_into_dunder_table_when_missing(self):
        conn = MagicMock()
        conn.query.return_value.fetchall.return_value = [
            ("mouse_score_sheet_water_restriction",),
            ("mouse_score_sheet__water_restriction",),
        ]
        ft = MagicMock()
        ft.__and__ = MagicMock(return_value=False)
        row = {
            "mouse_name": "Whale",
            "doc": datetime.date(2026, 7, 13),
            "weight_percentage": "95",
        }
        with patch.object(mouse_sync.dj, "conn", return_value=conn), patch.object(
            mouse_sync.dj, "FreeTable", return_value=ft
        ) as mock_ft:
            assert mouse_sync.ensure_water_restriction_on_fk_table(row) is True
        mock_ft.assert_called_once()
        assert "mouse_score_sheet__water_restriction" in mock_ft.call_args[0][1]
        ft.insert1.assert_called_once()

    def test_noop_when_dunder_table_absent(self):
        conn = MagicMock()
        conn.query.return_value.fetchall.return_value = [
            ("mouse_score_sheet_water_restriction",),
        ]
        with patch.object(mouse_sync.dj, "conn", return_value=conn), patch.object(
            mouse_sync.dj, "FreeTable"
        ) as mock_ft:
            assert (
                mouse_sync.ensure_water_restriction_on_fk_table(
                    {
                        "mouse_name": "Whale",
                        "doc": datetime.date(2026, 7, 13),
                        "weight_percentage": "95",
                    }
                )
                is False
            )
        mock_ft.assert_not_called()


# ==============================================================================
# recover_base: replication gate + orphan cleanup
# ==============================================================================


def _mock_conn(replica_rows=None, read_only="OFF", super_read_only="OFF"):
    conn = MagicMock()

    def query(sql):
        result = MagicMock()
        if "REPLICA STATUS" in sql or "SLAVE STATUS" in sql:
            result.fetchall.return_value = replica_rows or []
        elif "read_only" in sql and "super" not in sql:
            result.fetchall.return_value = [{"Value": read_only}]
        elif "super_read_only" in sql:
            result.fetchall.return_value = [{"Value": super_read_only}]
        else:
            result.fetchall.return_value = []
        return result

    conn.query.side_effect = query
    return conn


class TestCheckReplicationOff:
    def test_ok_when_no_replication(self):
        with patch.object(recover_base.dj, "conn", return_value=_mock_conn()):
            recover_base.check_replication_off(log=MagicMock())

    def test_blocks_when_replica_running(self):
        rows = [
            {
                "Replica_IO_Running": "Yes",
                "Replica_SQL_Running": "Yes",
            }
        ]
        with patch.object(recover_base.dj, "conn", return_value=_mock_conn(rows)):
            with pytest.raises(RuntimeError, match="replication is active"):
                recover_base.check_replication_off(log=MagicMock())

    def test_ok_when_replica_configured_but_stopped(self):
        rows = [
            {
                "Replica_IO_Running": "No",
                "Replica_SQL_Running": "No",
            }
        ]
        with patch.object(recover_base.dj, "conn", return_value=_mock_conn(rows)):
            recover_base.check_replication_off(log=MagicMock())

    def test_blocks_when_read_only(self):
        with patch.object(
            recover_base.dj,
            "conn",
            return_value=_mock_conn(read_only="ON"),
        ):
            with pytest.raises(RuntimeError, match="read-only"):
                recover_base.check_replication_off(log=MagicMock())

    def test_read_only_accepts_tuple_rows(self):
        """DJ/pymysql often returns SHOW VARIABLES as (name, value) tuples."""
        conn = MagicMock()

        def query(sql):
            result = MagicMock()
            if "REPLICA STATUS" in sql or "SLAVE STATUS" in sql:
                result.fetchall.return_value = []
            elif "super_read_only" in sql:
                result.fetchall.return_value = [("super_read_only", "OFF")]
            elif "read_only" in sql:
                result.fetchall.return_value = [("read_only", "OFF")]
            else:
                result.fetchall.return_value = []
            return result

        conn.query.side_effect = query
        with patch.object(recover_base.dj, "conn", return_value=conn):
            recover_base.check_replication_off(log=MagicMock())

    def test_blocks_when_read_only_tuple_rows(self):
        conn = MagicMock()

        def query(sql):
            result = MagicMock()
            if "REPLICA STATUS" in sql or "SLAVE STATUS" in sql:
                result.fetchall.return_value = []
            elif "super_read_only" in sql:
                result.fetchall.return_value = [("super_read_only", "OFF")]
            elif "read_only" in sql:
                result.fetchall.return_value = [("read_only", "ON")]
            else:
                result.fetchall.return_value = []
            return result

        conn.query.side_effect = query
        with patch.object(recover_base.dj, "conn", return_value=conn), pytest.raises(
            RuntimeError, match="read-only"
        ):
            recover_base.check_replication_off(log=MagicMock())


class TestCleanupOrphanExpMice:
    def test_dry_run_reports_orphans(self):
        dataset_keys = {("Flamingo", "2026-02-05", 1)}
        sessions = [
            {"mouse_name": "Flamingo", "doe": "2026-02-05", "attempt": 1},
            {"mouse_name": "Orphan", "doe": "2026-01-01", "attempt": 1},
        ]
        mice_rows = [
            {"mouse_name": "Flamingo"},
            {"mouse_name": "FutureMouse"},
        ]
        with patch.object(
            recover_base, "get_vr4mice_session_keys", return_value=dataset_keys
        ), patch.object(
            recover_base, "get_vr4mice_mouse_names", return_value={"Flamingo"}
        ), patch.object(
            recover_base, "exp"
        ) as mock_exp, patch.object(
            recover_base, "mice"
        ) as mock_mice:
            mock_exp.Session.return_value.fetch.return_value = sessions
            mock_mice.Mouse.return_value.fetch.return_value = mice_rows
            deleted_sessions, deleted_mice = recover_base.cleanup_orphan_exp_mice(
                dry_run=True
            )
        assert deleted_sessions == 1
        assert deleted_mice == 1  # FutureMouse has no Dataset


class TestRunRecoveryPopulateOnly:
    def test_does_not_sync_or_cleanup(self, monkeypatch):
        order = []

        def track_gui(*args, **kwargs):
            order.append("populate")
            return (0, 0)

        with patch.object(
            recover_base, "check_replication_off"
        ), patch.object(
            recover_base, "recover_base_from_gui", side_effect=track_gui
        ), patch.object(
            recover_base, "warn_incomplete_mice"
        ), patch.object(
            recover_base, "cleanup_orphan_exp_mice"
        ) as mock_cleanup:
            recover_base.run_recovery()
        assert order == ["populate"]
        mock_cleanup.assert_not_called()


class TestSessionKeyFromDataset:
    def test_parses_dataset_name(self):
        import types

        base_mod = types.ModuleType("vr4mice.schema.base")
        base_mod.parse_filename = lambda filename: {
            "mouse_name": "Flamingo",
            "date": "2026-02-05",
            "attempt": 1,
        }
        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []
        with patch.dict(
            sys.modules,
            {"vr4mice.schema": schema_pkg, "vr4mice.schema.base": base_mod},
        ):
            assert recover_base._session_key_from_dataset("Flamingo_2026-02-05_1") == (
                "Flamingo",
                "2026-02-05",
                1,
            )


class TestSessionDayMismatches:
    def test_reports_only_wrong_days(self):
        sessions = [
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 1,
                "doe": datetime.date(2026, 1, 16),
            },
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 2,
                "doe": datetime.date(2026, 1, 28),
            },
            {
                "mouse_name": "OkMouse",
                "day": 1,
                "attempt": 1,
                "doe": datetime.date(2026, 2, 1),
            },
            {
                "mouse_name": "OkMouse",
                "day": 3,
                "attempt": 1,
                "doe": datetime.date(2026, 2, 3),
            },
        ]
        bad = recover_base.find_session_day_mismatches(sessions)
        assert bad == [
            {
                "mouse_name": "Flamingo",
                "stored_day": 1,
                "attempt": 2,
                "doe": "2026-01-28",
                "correct_day": 13,
            }
        ]

    def test_empty_when_all_match(self):
        sessions = [
            {
                "mouse_name": "A",
                "day": 1,
                "attempt": 1,
                "doe": "2026-01-01",
            },
            {
                "mouse_name": "A",
                "day": 5,
                "attempt": 1,
                "doe": "2026-01-05",
            },
        ]
        assert recover_base.find_session_day_mismatches(sessions) == []


class TestPlanSessionDayFixes:
    def test_plans_rekey_without_conflict(self):
        sessions = [
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 1,
                "doe": datetime.date(2026, 1, 16),
            },
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 2,
                "doe": datetime.date(2026, 1, 28),
            },
        ]
        plans = recover_base.plan_session_day_fixes(sessions)
        assert len(plans) == 1
        assert plans[0]["correct_day"] == 13
        assert plans[0]["conflict"] is None

    def test_flags_target_pk_conflict(self):
        sessions = [
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 1,
                "doe": datetime.date(2026, 1, 16),
            },
            {
                "mouse_name": "Flamingo",
                "day": 1,
                "attempt": 2,
                "doe": datetime.date(2026, 1, 28),
            },
            {
                "mouse_name": "Flamingo",
                "day": 13,
                "attempt": 2,
                "doe": datetime.date(2026, 1, 28),
            },
        ]
        plans = recover_base.plan_session_day_fixes(sessions)
        assert len(plans) == 1
        assert plans[0]["conflict"] is not None
        assert "already exists" in plans[0]["conflict"]


# ==============================================================================
# sync_days helpers
# ==============================================================================


class TestDaysFromExpDates:
    def test_per_mouse_day_numbering_with_gaps(self):
        sessions = [
            ["2026-01-01", "A", "1"],
            ["2026-01-03", "A", "1"],
            ["2026-01-03", "A", "2"],
        ]
        days = _days_from_exp_dates(sessions)
        assert days["A_2026-01-01_1"] == 1
        assert days["A_2026-01-03_1"] == 3
        assert days["A_2026-01-03_2"] == 3

    def test_independent_mice_do_not_share_counter(self):
        # Callers group by mouse; each mouse starts at day 1
        days_a = _days_from_exp_dates([["2026-01-10", "A", "1"]])
        days_b = _days_from_exp_dates([["2026-01-01", "B", "1"]])
        assert days_a["A_2026-01-10_1"] == 1
        assert days_b["B_2026-01-01_1"] == 1


class TestNormalizePaths:
    def test_filters_missing_dirs(self, tmp_path):
        existing = tmp_path / "data"
        existing.mkdir()
        missing = tmp_path / "missing"
        assert _normalize_paths([str(existing), str(missing)]) == [
            os.path.normpath(str(existing))
        ]

    def test_none_uses_defaults_when_present(self, tmp_path, monkeypatch):
        data = tmp_path / "data"
        processed = tmp_path / "processed"
        data.mkdir()
        processed.mkdir()
        monkeypatch.setattr(
            sync_days,
            "DEFAULT_GUI_PATHS",
            (str(data), str(processed), str(tmp_path / "x")),
        )
        paths = _normalize_paths(None)
        assert str(data) in paths or os.path.normpath(str(data)) in paths
        assert len(paths) == 2


# ==============================================================================
# populate_rig base-schema flags
# ==============================================================================


class TestPopulateBaseFlags:
    def test_schemas_for_dataset_respects_flag(self):
        with patch("populate_rig.base", {"name": "base"}), patch(
            "populate_rig.vr4mice", {"name": "vr4mice"}
        ):
            assert _schemas_for_dataset({"x": 1}, populate_base=False) == [
                {"name": "vr4mice"}
            ]
            assert _schemas_for_dataset(None, populate_base=True) == [
                {"name": "vr4mice"}
            ]
            schemas = _schemas_for_dataset({"x": 1}, populate_base=True)
            assert schemas == [{"name": "base"}, {"name": "vr4mice"}]

    def test_gui_folder_skips_without_dataset(self, tmp_path):
        import numpy as np
        import populate_rig

        npy = tmp_path / "Orphan_2026-02-05_1.npy"
        np.save(str(npy), {"day": 1, "mouse_name": "Orphan"})

        fake_vr4mice = MagicMock()
        fake_vr4mice.Dataset.return_value.fetch.return_value = ["Keep_2026-02-05_1"]

        import types

        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []
        schema_pkg.vr4mice = fake_vr4mice

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_pkg,
                "vr4mice.schema.vr4mice": fake_vr4mice,
            },
        ), patch.object(
            populate_rig, "populate_dataset_tables"
        ) as mock_pop:
            ok, failed = populate_rig.populate_base_from_gui_folder(
                str(tmp_path), restrict_to_datasets=True
            )
        assert ok == 0 and failed == 0
        mock_pop.assert_not_called()


class TestRunBaseCliSurface:
    def test_modes_and_force_flag_present(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "dj_pipeline" / "run_base.py").read_text()
        for mode in (
            "recover_base",
            "cleanup_orphans",
            "cleanup_mice",
            "check_session_days",
            "fix_session_days",
        ):
            assert f'"{mode}"' in text
        for removed in ("sync_mice", "sync_exp", "sync_days", "fetch", "populate"):
            assert f'            "{removed}",' not in text
        assert "--force" in text
        assert "mysql.mk sync-mice-from-main" in text
