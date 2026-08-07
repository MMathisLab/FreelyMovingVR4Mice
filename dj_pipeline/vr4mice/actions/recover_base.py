"""
Recovery workflow for local base/exp/mice schema (not part of the main cron pipeline).

``recover_base`` only:
  1. Verify MySQL replication is not actively running on the local database.
  2. Repopulate exp from all unpopulated GUI .npy files in data/ and processed/.
  3. Warn about incomplete mice and print the recommended next commands.

Parent sync and orphan cleanup are separate ``run_base.py`` modes — see docs.
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

CLEANUP_ORPHANS_COMMAND = (
    "python run_base.py cleanup_orphans          # dry-run Dataset orphans\n"
    "python run_base.py cleanup_orphans --force  # apply deletes (local only)"
)

POST_RECOVERY_NOTE = """
================================================================================
recover_base finished — recommended next steps (run separately)
================================================================================

This mode only rebuilt LOCAL exp/mice from unpopulated GUI .npy files.
It does not sync from parent or delete orphans.

Recommended order:

  1. Before recover (or again if stubs remain):
       {sync_mice}

  2. recover_base (already done)

  3. Optional — remove local exp/mice with no vr4mice.Dataset:
       {cleanup_orphans}

  4. Optional — push missing local (non-collab) sessions to parent:
       {sync_exp}

Never deletes on main. Orphan cleanup (--force) needs replication OFF.

MySQL diagnostics: make -f mysql.mk replication-summary
================================================================================
""".format(
    sync_mice=SYNC_MICE_COMMAND,
    cleanup_orphans=CLEANUP_ORPHANS_COMMAND,
    sync_exp=SYNC_EXP_COMMAND,
)


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
        sql_running = status.get("Replica_SQL_Running") or status.get(
            "Slave_SQL_Running"
        )
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
    Remove **local** exp/mice rows that are not backed by a vr4mice.Dataset.

    Never touches the parent DB. Separate from ``recover_base`` — run via
    ``python run_base.py cleanup_orphans``.
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
    """Sync days and populate base/exp from all unpopulated GUI .npy files."""
    from vr4mice.actions.sync_days import sync_days

    sync_days()

    total_ok, total_failed = 0, 0
    for folder in gui_paths:
        if not os.path.isdir(folder):
            logger.warning("GUI folder does not exist, skipping: %s", folder)
            continue
        logger.info("Populating base schema from GUI files in %s", folder)
        ok, failed = populate_base_from_gui_folder(
            folder, srcf=srcf, restrict_to_datasets=False
        )
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
    srcf: str = "/data",
    data_dir: str = "/data/data",
    processed_dir: str = "/data/processed",
) -> None:
    """
    Rebuild local exp/mice from unpopulated GUI files only.

    Does not sync from parent or clean orphans — run those as separate
    ``run_base.py`` modes (see POST_RECOVERY_NOTE / docs).
    """
    logger.info("=== recover_base: starting (GUI populate only) ===")

    check_replication_off(log=logger)

    ok, failed = recover_base_from_gui([data_dir, processed_dir], srcf=srcf)
    logger.info(
        "GUI base populate summary: %d complete, %d failed/incomplete.", ok, failed
    )

    warn_incomplete_mice(log=logger)
    logger.info(POST_RECOVERY_NOTE)
