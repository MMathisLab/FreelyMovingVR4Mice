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


class TestSyncMiceFromMain:
    def test_requires_dj_main_host(self, monkeypatch):
        monkeypatch.delenv("DJ_MAIN_HOST", raising=False)
        with pytest.raises(ValueError, match="DJ_MAIN_HOST"):
            mouse_sync.sync_mice_from_main()

    def test_noop_when_no_known_mice(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        with patch.object(
            mouse_sync, "get_known_local_mouse_names", return_value=set()
        ):
            assert mouse_sync.sync_mice_from_main(log=log) == 0
        log.info.assert_called()

    def test_noop_when_all_complete(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        with patch.object(
            mouse_sync, "get_known_local_mouse_names", return_value={"Flamingo"}
        ), patch.object(mouse_sync, "get_incomplete_mouse_names", return_value=[]):
            assert mouse_sync.sync_mice_from_main(log=log) == 0

    def test_explicit_mouse_names_skip_local_discovery(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        table = MagicMock()
        table.return_value = table
        table.__and__ = MagicMock(return_value=table)
        table.fetch.return_value = [
            {"mouse_name": "Flamingo", "mouse_id": 7, "strain": "C57"}
        ]

        with patch.object(
            mouse_sync, "get_known_local_mouse_names"
        ) as mock_known, patch.object(
            mouse_sync, "MOUSE_SYNC_TABLES", (table,)
        ), patch.object(
            mouse_sync, "_main_database"
        ) as mock_main, patch.object(
            mouse_sync, "_upsert_rows", return_value=1
        ), patch.object(mouse_sync, "mice") as mock_mice:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_mice.Mouse = table
            mock_mice.Strain.return_value = table
            count = mouse_sync.sync_mice_from_main(
                log=log, mouse_names=["Flamingo", " Flamingo "]
            )

        assert count >= 1
        mock_known.assert_not_called()
        assert any("named mice" in str(c) for c in log.info.call_args_list)

    def test_fetches_targets_on_main_upserts_on_local(self, monkeypatch):
        """Named targets are read inside _main_database, then upserted locally."""
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        main_row = {"mouse_name": "Flamingo", "mouse_id": 7, "strain": "C57"}
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
            mouse_sync, "get_known_local_mouse_names", return_value={"Flamingo"}
        ), patch.object(
            mouse_sync, "get_incomplete_mouse_names", side_effect=[["Flamingo"], []]
        ), patch.object(
            mouse_sync, "MOUSE_SYNC_TABLES", (table,)
        ), patch.object(
            mouse_sync, "_main_database", fake_main
        ), patch.object(
            mouse_sync, "_upsert_rows", side_effect=fake_upsert
        ), patch.object(
            mouse_sync, "mice"
        ) as mock_mice:
            mock_mice.Mouse = table
            mock_mice.Strain.return_value = table
            count = mouse_sync.sync_mice_from_main(log=log)

        assert count >= 1
        assert False in upsert_phases  # upsert after leaving main connection
        assert any("known local mice" in str(c) for c in log.info.call_args_list)

    def test_split_host_port(self):
        assert mouse_sync._split_host_port("db.example:3306") == ("db.example", 3306)
        assert mouse_sync._split_host_port("128.178.51.167") == ("128.178.51.167", 3306)

    def test_main_database_switches_host_port_and_restores(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        cfg = {
            "database.host": "127.0.0.1",
            "database.port": 3309,
            "database.user": "u",
            "database.password": "p",
        }
        connect_calls = []

        def fake_connect(**kwargs):
            connect_calls.append(kwargs)
            cfg["database.host"] = kwargs["host"]
            cfg["database.port"] = kwargs["port"]

        with patch.object(mouse_sync.dj, "config", cfg), patch.object(
            mouse_sync, "_dj_connect", side_effect=fake_connect
        ), patch.object(
            mouse_sync, "_active_endpoint", side_effect=[("main.example", 3306)]
        ):
            with mouse_sync._main_database():
                assert cfg["database.host"] == "main.example"
                assert cfg["database.port"] == 3306
        assert connect_calls[0]["host"] == "main.example"
        assert connect_calls[0]["port"] == 3306
        assert connect_calls[0]["disable_ssl"] is True
        # restore local
        assert connect_calls[1]["host"] == "127.0.0.1"
        assert connect_calls[1]["port"] == 3309

    def test_main_database_errors_if_still_on_local(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "127.0.0.1:3306")
        cfg = {
            "database.host": "127.0.0.1",
            "database.port": 3309,
            "database.user": "u",
            "database.password": "p",
        }
        with patch.object(mouse_sync.dj, "config", cfg), patch.object(
            mouse_sync, "_dj_connect"
        ), patch.object(
            mouse_sync, "_active_endpoint", return_value=("127.0.0.1", 3309)
        ):
            with pytest.raises(RuntimeError, match="Still connected to local"):
                with mouse_sync._main_database():
                    pass

    def test_pymysql_disable_ssl_sets_ssl_disabled(self):
        import pymysql

        seen = {}
        original = pymysql.connect

        def fake_connect(*args, **kwargs):
            seen.update(kwargs)
            return MagicMock()

        pymysql.connect = fake_connect
        try:
            with mouse_sync._pymysql_disable_ssl():
                pymysql.connect(host="h", user="u", password="p")
        finally:
            pymysql.connect = original
        assert seen.get("ssl_disabled") is True
        assert seen.get("ssl") is None


class TestUpsertRows:
    def test_uses_replace_not_delete(self):
        table = MagicMock()
        row = {"mouse_name": "Flamingo", "mouse_id": 7}
        count = mouse_sync._upsert_rows(table, [row])
        assert count == 1
        table.insert1.assert_called_once_with(row, replace=True)
        table.delete.assert_not_called()


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
        pushable = {("Flamingo", "2026-02-05", 1)}
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(
            mouse_sync, "get_pushable_local_session_keys", return_value=pushable
        ), patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [session]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=False)
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
        prepared = {
            "mouse_name": "Flamingo",
            "day": 3,
            "attempt": 1,
            "doe": datetime.date(2026, 2, 5),
        }
        pushable = {("Flamingo", "2026-02-05", 1)}
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(
            mouse_sync, "get_pushable_local_session_keys", return_value=pushable
        ), patch.object(
            mouse_sync, "_prepare_session_row_for_main", return_value=("ready", prepared)
        ), patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [session]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=True)
            mock_exp.Session.insert1 = MagicMock()
            mock_exp.SessionScoreSheet.return_value.__and__ = MagicMock(
                return_value=False
            )
            count = mouse_sync.sync_exp_to_main(log=log)
        assert count >= 1
        mock_exp.Session.insert1.assert_called_once_with(prepared)

    def test_skips_when_doe_already_on_main(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        session = {
            "mouse_name": "Flamingo",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        pushable = {("Flamingo", "2026-02-05", 1)}
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(
            mouse_sync, "get_pushable_local_session_keys", return_value=pushable
        ), patch.object(
            mouse_sync, "_prepare_session_row_for_main", return_value=("exists", None)
        ), patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [session]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=True)
            mock_exp.Session.insert1 = MagicMock()
            assert mouse_sync.sync_exp_to_main(log=log) == 0
            mock_exp.Session.insert1.assert_not_called()

    def test_skips_sessions_without_local_dataset(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        log = MagicMock()
        session = {
            "mouse_name": "CollabOnly",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "get_pushable_local_session_keys", return_value=set()
        ), patch.object(mouse_sync, "_main_database") as mock_main:
            mock_exp.Session.return_value.fetch.return_value = [session]
            assert mouse_sync.sync_exp_to_main(log=log) == 0
            mock_main.assert_not_called()
        assert any(
            "No local non-collab" in str(c) for c in log.info.call_args_list
        )

    def test_skips_collab_lab_sessions(self, monkeypatch):
        monkeypatch.setenv("DJ_MAIN_HOST", "main.example:3306")
        monkeypatch.setenv("DJ_LAB", "mathis-lab")
        log = MagicMock()
        local = {
            "mouse_name": "LocalMouse",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        collab = {
            "mouse_name": "CollabMouse",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-06",
        }
        prepared = dict(local)
        pushable = {("LocalMouse", "2026-02-05", 1)}
        with patch.object(mouse_sync, "exp") as mock_exp, patch.object(
            mouse_sync, "mice"
        ) as mock_mice, patch.object(
            mouse_sync, "get_pushable_local_session_keys", return_value=pushable
        ), patch.object(
            mouse_sync, "_prepare_session_row_for_main", return_value=("ready", prepared)
        ), patch.object(mouse_sync, "_main_database") as mock_main:
            mock_main.return_value.__enter__ = MagicMock()
            mock_main.return_value.__exit__ = MagicMock(return_value=False)
            mock_exp.Session.primary_key = ["mouse_name", "day", "attempt"]
            mock_exp.Session.return_value.fetch.return_value = [local, collab]
            mock_exp.SessionScoreSheet.return_value.fetch.return_value = []
            mock_mice.Mouse.return_value.__and__ = MagicMock(return_value=True)
            mock_exp.Session.insert1 = MagicMock()
            mock_exp.SessionScoreSheet.return_value.__and__ = MagicMock(
                return_value=False
            )
            mouse_sync.sync_exp_to_main(log=log)
        mock_exp.Session.insert1.assert_called_once_with(prepared)


class TestPrepareSessionRowForMain:
    def test_exists_by_doe_not_day(self):
        log = MagicMock()
        row = {
            "mouse_name": "Flamingo",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        exists_q = MagicMock()
        exists_q.__bool__ = MagicMock(return_value=True)
        session_table = MagicMock()
        # First restriction chain: mouse+attempt & doe → exists
        session_table.__and__ = MagicMock(return_value=exists_q)
        exists_q.__and__ = MagicMock(return_value=exists_q)
        with patch.object(mouse_sync, "exp") as mock_exp:
            mock_exp.Session.return_value = session_table
            status, out = mouse_sync._prepare_session_row_for_main(row, log=log)
        assert status == "exists"
        assert out is None

    def test_assigns_day_from_main_timeline(self):
        log = MagicMock()
        row = {
            "mouse_name": "Flamingo",
            "day": 1,
            "attempt": 1,
            "doe": "2026-02-05",
        }
        # Build a query mock: doe-check empty, fetch returns earlier session, pk free
        doe_miss = MagicMock()
        doe_miss.__bool__ = MagicMock(return_value=False)
        mouse_q = MagicMock()
        mouse_q.fetch.return_value = [
            {"mouse_name": "Flamingo", "day": 1, "attempt": 1, "doe": "2026-01-01"}
        ]
        pk_miss = MagicMock()
        pk_miss.__bool__ = MagicMock(return_value=False)

        def and_side_effect(restriction):
            if isinstance(restriction, str) and restriction.startswith("doe="):
                return doe_miss
            if isinstance(restriction, dict) and set(restriction) == {"mouse_name"}:
                return mouse_q
            if isinstance(restriction, dict) and "day" in restriction:
                return pk_miss
            # mouse_name + attempt
            chained = MagicMock()
            chained.__and__ = MagicMock(side_effect=and_side_effect)
            chained.__bool__ = MagicMock(return_value=False)
            return chained

        session_table = MagicMock()
        session_table.__and__ = MagicMock(side_effect=and_side_effect)
        with patch.object(mouse_sync, "exp") as mock_exp:
            mock_exp.Session.return_value = session_table
            status, out = mouse_sync._prepare_session_row_for_main(row, log=log)
        assert status == "ready"
        assert out["day"] == 36  # 2026-02-05 - 2026-01-01 + 1
        assert out["doe"] == datetime.date(2026, 2, 5)


class TestGetPushableLocalSessionKeys:
    def test_excludes_other_lab_collab(self, monkeypatch):
        monkeypatch.setenv("DJ_LAB", "mathis-lab")
        log = MagicMock()

        class FakeJoin:
            def fetch(self, *args, **kwargs):
                return [
                    {"dataset": "Local_2026-02-05_1", "lab": "mathis-lab"},
                    {"dataset": "Other_2026-02-06_1", "lab": "tolias-lab"},
                ]

        class FakeCollab:
            def __mul__(self, _labs):
                return FakeJoin()

        class FakeDataset:
            def fetch(self, *args, **kwargs):
                return [
                    {"dataset": "Local_2026-02-05_1"},
                    {"dataset": "Other_2026-02-06_1"},
                ]

        fake_vr4mice = MagicMock()
        fake_vr4mice.Collab.return_value = FakeCollab()
        fake_vr4mice.Labs.return_value = MagicMock()
        fake_vr4mice.Dataset.return_value = FakeDataset()

        import types

        base_mod = types.ModuleType("vr4mice.schema.base")
        base_mod.parse_filename = lambda filename: {
            "mouse_name": filename.split("_")[0],
            "date": filename.split("_")[1],
            "attempt": int(filename.split("_")[2]),
        }
        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []
        schema_pkg.vr4mice = fake_vr4mice

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_pkg,
                "vr4mice.schema.base": base_mod,
                "vr4mice.schema.vr4mice": fake_vr4mice,
            },
        ):
            keys = mouse_sync.get_pushable_local_session_keys(log=log)

        assert ("Local", "2026-02-05", 1) in keys
        assert ("Other", "2026-02-06", 1) not in keys

    def test_requires_dj_lab_when_collab_present(self, monkeypatch):
        monkeypatch.delenv("DJ_LAB", raising=False)
        log = MagicMock()

        class FakeJoin:
            def fetch(self, *args, **kwargs):
                return [{"dataset": "Local_2026-02-05_1", "lab": "mathis-lab"}]

        class FakeCollab:
            def __mul__(self, _labs):
                return FakeJoin()

        class FakeDataset:
            def fetch(self, *args, **kwargs):
                return [{"dataset": "Local_2026-02-05_1"}]

        fake_vr4mice = MagicMock()
        fake_vr4mice.Collab.return_value = FakeCollab()
        fake_vr4mice.Labs.return_value = MagicMock()
        fake_vr4mice.Dataset.return_value = FakeDataset()

        import types

        base_mod = types.ModuleType("vr4mice.schema.base")
        base_mod.parse_filename = lambda filename: {
            "mouse_name": "Local",
            "date": "2026-02-05",
            "attempt": 1,
        }
        schema_pkg = types.ModuleType("vr4mice.schema")
        schema_pkg.__path__ = []
        schema_pkg.vr4mice = fake_vr4mice

        with patch.dict(
            sys.modules,
            {
                "vr4mice.schema": schema_pkg,
                "vr4mice.schema.base": base_mod,
                "vr4mice.schema.vr4mice": fake_vr4mice,
            },
        ):
            with pytest.raises(ValueError, match="DJ_LAB"):
                mouse_sync.get_pushable_local_session_keys(log=log)


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
        ) as mock_cleanup, patch(
            "vr4mice.actions.mouse_sync.sync_mice_from_main"
        ) as mock_sync:
            recover_base.run_recovery()
        assert order == ["populate"]
        mock_cleanup.assert_not_called()
        mock_sync.assert_not_called()


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
            "sync_mice",
            "sync_exp",
            "recover_base",
            "cleanup_orphans",
            "cleanup_mice",
        ):
            assert f'"{mode}"' in text
        for removed in ("sync_days", "fetch", "populate"):
            # modes list only — allow mentions in comments/docstrings
            assert f'            "{removed}",' not in text
        assert "--force" in text
        assert "sync_mice →" not in text  # recover_base must not chain sync/cleanup
