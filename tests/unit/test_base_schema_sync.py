"""
Unit tests for base-schema sync / recovery (mouse_sync, recover_base, sync_days).

These cover the new run_base.py workflows without requiring MySQL or a parent DB.
Database tables and DataJoint connections are mocked.
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
    def test_skips_when_mouse_exists(self):
        with patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=True)
            inserted = mouse_sync.ensure_mouse_for_session(
                {
                    "mouse_name": "Flamingo",
                    "mouse_id": 1,
                    "dob": "2020-01-01",
                    "sex": "F",
                    "strain": "X",
                }
            )
        assert inserted is False

    def test_inserts_stub_when_missing(self):
        log = MagicMock()
        with patch.object(mouse_sync, "mice") as mock_mice:
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=False)
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


class TestSyncMiceFromMain:
    def test_requires_dj_main_host(self, monkeypatch):
        monkeypatch.delenv("DJ_MAIN_HOST", raising=False)
        with pytest.raises(ValueError, match="DJ_MAIN_HOST"):
            mouse_sync.sync_mice_from_main()

    def test_noop_when_no_local_sessions(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        with patch.object(mouse_sync, "get_session_mouse_names", return_value=set()):
            assert mouse_sync.sync_mice_from_main(log=log) == 0
        log.info.assert_called()

    def test_noop_when_all_complete(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        with patch.object(
            mouse_sync, "get_session_mouse_names", return_value={"Flamingo"}
        ), patch.object(mouse_sync, "get_incomplete_mouse_names", return_value=[]):
            assert mouse_sync.sync_mice_from_main(log=log) == 0

    def test_fetches_on_main_upserts_on_local(self, monkeypatch):
        """Rows are read inside _main_database, then upserted after leaving it."""
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        main_row = {"mouse_name": "Flamingo", "mouse_id": 7}
        table = MagicMock()
        table.return_value = table
        table.__and__ = MagicMock(return_value=table)
        table.fetch.return_value = [main_row]

        phase = {"on_main": False}

        @contextmanager
        def fake_main():
            phase["on_main"] = True
            try:
                yield
            finally:
                phase["on_main"] = False

        upsert_phases = []

        def fake_upsert(tbl, rows):
            upsert_phases.append(phase["on_main"])
            return len(list(rows))

        with patch.object(
            mouse_sync, "get_session_mouse_names", return_value={"Flamingo"}
        ), patch.object(
            mouse_sync, "get_incomplete_mouse_names", return_value=["Flamingo"]
        ), patch.object(
            mouse_sync, "MOUSE_SYNC_TABLES", (table,)
        ), patch.object(
            mouse_sync, "_main_database", fake_main
        ), patch.object(
            mouse_sync, "_upsert_rows", side_effect=fake_upsert
        ):
            count = mouse_sync.sync_mice_from_main(log=log)

        assert count == 1
        assert upsert_phases == [False]  # upsert after leaving main connection


class TestSyncExpToMain:
    def test_requires_dj_main_host(self, monkeypatch):
        monkeypatch.delenv("DJ_MAIN_HOST", raising=False)
        with pytest.raises(ValueError, match="DJ_MAIN_HOST"):
            mouse_sync.sync_exp_to_main()

    def test_noop_when_no_local_sessions(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        with patch.object(mouse_sync, "exp") as mock_exp:
            mock_exp.Session.return_value.fetch.return_value = []
            assert mouse_sync.sync_exp_to_main(log=log) == 0
        log.info.assert_called()

    def test_skips_when_mouse_missing_on_main(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        session = {
            "mouse_name": "Flamingo",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [session]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            # On main: mouse missing
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=False)
            mock_exp.Session.return_value.__and__ = MagicMock(return_value=False)
            assert mouse_sync.sync_exp_to_main(log=log) == 0
        log.warning.assert_called()

    def test_inserts_missing_session_on_main(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        session = {
            "mouse_name": "Flamingo",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [session]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=True)
            # Session missing on main, then present after insert
            session_and = MagicMock()
            session_and.__bool__ = MagicMock(side_effect=[False, False, True])
            mock_exp.Session.return_value.__and__ = MagicMock(return_value=session_and)
            mock_exp.Session.insert1 = MagicMock()
            mock_exp.SessionScoreSheet.return_value.__and__ = MagicMock(
                return_value=False
            )
            count = mouse_sync.sync_exp_to_main(log=log)
        assert count >= 1
        mock_exp.Session.insert1.assert_called_once_with(session)


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


class TestRunBaseCliSurface:
    def test_modes_and_force_flag_present(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "dj_pipeline" / "run_base.py").read_text()
        for mode in (
            "sync_mice",
            "sync_exp",
            "cleanup_mice",
            "recover_base",
        ):
            assert f'"{mode}"' in text
        for removed in ("sync_days", "fetch", "populate"):
            # modes list only — allow mentions in comments/docstrings
            assert f'            "{removed}",' not in text
        assert "--force" in text
