"""
Recovery workflow for local base/exp/mice schema (not part of the main cron pipeline).

Steps:
  1. Verify MySQL replication is not actively running on the local database.
  2. Remove orphan exp.Session and mice.Mouse rows not backed by vr4mice.Dataset.
  3. Repopulate exp (and stub Mouse name-only rows) from GUI .npy files in data/ and processed/.
  4. Print instructions for bidirectional sync with the main database via two DJ connections.
"""

from __future__ import annotations

import os
from typing import Iterable, List, Set, Tuple

import datajoint as dj
from base_schemas.schemas import exp, mice

from vr4mice.actions.mouse_sync import (
    SYNC_EXP_COMMAND,
    SYNC_MICE_COMMAND,
    warn_incomplete_mice,
)
from vr4mice.actions.populate_rig import populate_base_from_gui_folder
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

POST_RECOVERY_NOTE = """
================================================================================
Recovery finished — sync with the main database
================================================================================

This recovery script only rebuilds LOCAL exp/mice rows from GUI files on disk.
It uses stub Mouse rows (mouse_id=-1, minimal fields) so sessions can be inserted.

Two DataJoint connections are involved (local DJ_HOST vs main DJ_MAIN_HOST):

  1. Main → local (Mouse metadata)
     Pull full Mouse records (dob, strain, surgery, score sheets, …) from the
     main registry into this database:
       {sync_mice}

     Requires: DJ_MAIN_HOST (and optionally DJ_MAIN_USER / DJ_MAIN_PWD)

  2. Local → main (Experiment sessions) — automated
     Push recovered/new exp.Session (+ SessionScoreSheet) to the parent exp
     schema (inserts missing rows only; does not overwrite existing parent
     sessions). Mouse must already exist on main:
       {sync_exp}

     Requires: DJ_MAIN_HOST and write access on main exp.

Replication: recover_base aborts if replica IO/SQL threads are running or the
DB is read-only. Orphan cleanup (--force) is only safe with replication OFF.
Keep replication OFF while editing local tables; re-enable only after both
sync directions (mice from main, sessions to main) are consistent.

MySQL diagnostics: make -f mysql.mk replication-summary
================================================================================
""".format(sync_mice=SYNC_MICE_COMMAND, sync_exp=SYNC_EXP_COMMAND)


def _session_key_from_dataset(dataset: str) -> Tuple[str, str, int]:
    from vr4mice.schema.base import parse_filename

    parsed = parse_filename(dataset)
    return (parsed["mouse_name"], parsed["date"], parsed["attempt"])


def get_vr4mice_session_keys() -> Set[Tuple[str, str, int]]:
    """(mouse_name, doe_iso, attempt) keys derived from vr4mice.Dataset names."""
    from vr4mice.schema import vr4mice

    keys: Set[Tuple[str, str, int]] = set()
    for row in vr4mice.Dataset().fetch("dataset", as_dict=True):
        try:
            keys.add(_session_key_from_dataset(row["dataset"]))
        except ValueError as err:
            logger.warning("Skipping unparseable dataset %r: %s", row["dataset"], err)
    return keys


def get_vr4mice_mouse_names() -> Set[str]:
    return {key[0] for key in get_vr4mice_session_keys()}


def _session_tuple(session_row: dict) -> Tuple[str, str, int]:
    doe = session_row["doe"]
    if hasattr(doe, "isoformat"):
        doe = doe.isoformat()
    return (session_row["mouse_name"], str(doe), session_row["attempt"])


def check_replication_off(log=None) -> None:
    """
    Abort recovery when this MySQL instance is actively replicating.

    Recovery mutates local exp/mice tables; that is unsafe while replica IO/SQL
    threads are running or while this host is read-only replica of another source.
    """
    log = log or logger
    conn = dj.conn()
    status = None
    for query in ("SHOW REPLICA STATUS", "SHOW SLAVE STATUS"):
        try:
            rows = conn.query(query).fetchall()
        except Exception:
            continue
        if rows:
            status = rows[0]
            break

    if status:
        io_running = status.get("Replica_IO_Running") or status.get("Slave_IO_Running")
        sql_running = status.get("Replica_SQL_Running") or status.get("Slave_SQL_Running")
        if io_running == "Yes" or sql_running == "Yes":
            raise RuntimeError(
                "MySQL replication is active "
                f"(Replica_IO_Running={io_running}, Replica_SQL_Running={sql_running}). "
                "Stop replication before running recover_base."
            )
        log.info(
            "Replication is configured but not running (IO=%s, SQL=%s). OK for recovery.",
            io_running,
            sql_running,
        )
    else:
        log.info("No MySQL replication configured on this server. OK for recovery.")

    try:
        read_only = conn.query("SHOW VARIABLES LIKE 'read_only'").fetchall()
        super_ro = conn.query("SHOW VARIABLES LIKE 'super_read_only'").fetchall()
    except Exception:
        return

    ro = read_only[0].get("Value") if read_only else "OFF"
    sro = super_ro[0].get("Value") if super_ro else "OFF"
    if ro == "ON" or sro == "ON":
        raise RuntimeError(
            f"Database is read-only (read_only={ro}, super_read_only={sro}). "
            "Recovery requires a writable local database with replication off."
        )


def _delete_sessions(sessions: Iterable[dict], *, dry_run: bool) -> int:
    sessions = list(sessions)
    if not sessions:
        return 0

    labels = [
        f"{s['mouse_name']} doe={s['doe']} attempt={s['attempt']}" for s in sessions
    ]
    if dry_run:
        logger.warning(
            "Dry run: would delete %d exp.Session row(s) without vr4mice.Dataset: %s",
            len(sessions),
            ", ".join(labels),
        )
        return len(sessions)

    for session_row in sessions:
        key = {field: session_row[field] for field in exp.Session.primary_key}
        (exp.SessionScoreSheet() & key).delete(safemode=False)
        (exp.Session() & key).delete(safemode=False)

    logger.info("Deleted %d orphan exp.Session row(s).", len(sessions))
    return len(sessions)


def _delete_mice(mouse_names: Iterable[str], *, dry_run: bool) -> int:
    names = sorted(set(mouse_names))
    if not names:
        return 0

    if dry_run:
        logger.warning(
            "Dry run: would delete %d mice.Mouse row(s) not referenced by "
            "vr4mice.Dataset: %s",
            len(names),
            ", ".join(names),
        )
        return len(names)

    mouse_tables = (
        mice.MouseScoreSheet,
        mice.MouseScoreSheet_WaterRestriction,
        mice.Surgery,
    )
    for name in names:
        restriction = {"mouse_name": name}
        for table in mouse_tables:
            (table() & restriction).delete(safemode=False)
        (mice.Mouse() & restriction).delete(safemode=False)

    logger.info("Deleted %d orphan mice.Mouse row(s).", len(names))
    return len(names)


def cleanup_orphan_exp_mice(*, dry_run: bool = True) -> Tuple[int, int]:
    """
    Remove exp/mice rows that are not backed by a vr4mice.Dataset entry.

    vr4mice.Dataset is the source of truth for which sessions exist in this pipeline.
    """
    dataset_keys = get_vr4mice_session_keys()
    dataset_mice = get_vr4mice_mouse_names()

    orphan_sessions = [
        row
        for row in exp.Session().fetch(as_dict=True)
        if _session_tuple(row) not in dataset_keys
    ]
    deleted_sessions = _delete_sessions(orphan_sessions, dry_run=dry_run)

    orphan_mice = [
        row["mouse_name"]
        for row in mice.Mouse().fetch(as_dict=True)
        if row["mouse_name"] not in dataset_mice
    ]
    deleted_mice = _delete_mice(orphan_mice, dry_run=dry_run)

    if not orphan_sessions and not orphan_mice:
        logger.info(
            "No orphan exp/mice rows (all sessions and mice match vr4mice.Dataset)."
        )

    if dry_run and (orphan_sessions or orphan_mice):
        logger.warning("Re-run with --force to apply cleanup.")

    return deleted_sessions, deleted_mice


def recover_base_from_gui(
    gui_paths: List[str],
    *,
    srcf: str = "/data",
) -> Tuple[int, int]:
    """Sync days and populate base/exp (+ stub Mouse) from GUI folders."""
    from vr4mice.actions.sync_days import sync_days

    sync_days()

    total_ok, total_failed = 0, 0
    for folder in gui_paths:
        if not os.path.isdir(folder):
            logger.warning("GUI folder does not exist, skipping: %s", folder)
            continue
        logger.info("Populating base schema from GUI files in %s", folder)
        ok, failed = populate_base_from_gui_folder(folder, srcf=srcf)
        total_ok += ok
        total_failed += failed
        logger.info(
            "Folder %s: %d dataset(s) populated, %d failed/incomplete.",
            folder,
            ok,
            failed,
        )
    return total_ok, total_failed


def run_recovery(
    *,
    force: bool = False,
    srcf: str = "/data",
    data_dir: str = "/data/data",
    processed_dir: str = "/data/processed",
) -> None:
    """
    Full recovery: replication check → cleanup → GUI base populate → sync notes.
    """
    logger.info("=== recover_base: starting (force=%s) ===", force)

    check_replication_off(log=logger)

    cleanup_orphan_exp_mice(dry_run=not force)

    ok, failed = recover_base_from_gui([data_dir, processed_dir], srcf=srcf)
    logger.info(
        "GUI base populate summary: %d complete, %d failed/incomplete.", ok, failed
    )

    warn_incomplete_mice(log=logger)
    logger.info(POST_RECOVERY_NOTE)
