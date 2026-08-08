"""
Recovery workflow for local base/exp/mice schema (not part of the main cron pipeline).

``recover_base`` only:
  1. Verify MySQL replication is not actively running on the local database.
  2. Repopulate exp from all unpopulated GUI .npy files in data/ and processed/.
  3. Warn about incomplete mice and print the recommended next commands.

Parent mice sync (mysql.mk) and orphan cleanup are separate modes — see docs.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import datajoint as dj
from base_schemas.schemas import exp, mice
from vr4mice.actions.mouse_sync import SYNC_MICE_COMMAND, warn_incomplete_mice
from vr4mice.actions.populate_rig import populate_base_from_gui_folder
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


class SessionDayMismatchError(RuntimeError):
    """Raised when exp.Session.day does not match the doe timeline."""


def _dj_delete(restricted) -> None:
    """Delete without prompt. DJ2 removed delete(safemode=...); use config."""
    prev = dj.config.get("safemode", True)
    dj.config["safemode"] = False
    try:
        restricted.delete()
    finally:
        dj.config["safemode"] = prev


def _as_date(value: Union[date, datetime, str]) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def find_session_day_mismatches(
    sessions: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Sessions where stored day != (doe − first doe for that mouse) + 1.

    Same rule as sync_days / Mouse.get_starting_date. Pass ``sessions`` to
    unit-test without DataJoint; otherwise fetches all exp.Session rows.
    """
    if sessions is None:
        sessions = exp.Session().fetch(
            "mouse_name", "day", "attempt", "doe", as_dict=True
        )

    by_mouse: Dict[str, List[Dict[str, Any]]] = {}
    for row in sessions:
        by_mouse.setdefault(row["mouse_name"], []).append(row)

    mismatches: List[Dict[str, Any]] = []
    for mouse_name, rows in sorted(by_mouse.items()):
        start_doe = min(_as_date(r["doe"]) for r in rows)
        for row in rows:
            doe = _as_date(row["doe"])
            correct_day = (doe - start_doe).days + 1
            stored_day = int(row["day"])
            if stored_day != correct_day:
                mismatches.append(
                    {
                        "mouse_name": mouse_name,
                        "stored_day": stored_day,
                        "attempt": int(row["attempt"]),
                        "doe": doe.isoformat(),
                        "correct_day": correct_day,
                    }
                )
    return mismatches


def check_session_days(*, raise_on_mismatch: bool = True) -> List[Dict[str, Any]]:
    """
    Verify every exp.Session.day matches the mouse's doe timeline.

    Logs mismatches and optionally raises SessionDayMismatchError (exit 1 via
    run_base). Empty result means all sessions are consistent with that rule.
    """
    mismatches = find_session_day_mismatches()
    if not mismatches:
        logger.info(
            "check_session_days: all %d exp.Session row(s) match doe timeline.",
            len(exp.Session()),
        )
        return []

    logger.error(
        "check_session_days: %d session(s) have day != (doe - first doe) + 1:",
        len(mismatches),
    )
    for row in mismatches:
        logger.error(
            "  %s day=%s attempt=%s doe=%s -> correct_day=%s",
            row["mouse_name"],
            row["stored_day"],
            row["attempt"],
            row["doe"],
            row["correct_day"],
        )
    msg = (
        f"{len(mismatches)} exp.Session row(s) have wrong day "
        "(see log). Preview migrate: python run_base.py fix_session_days "
        "(then --force). Also run sync_days so .npy day matches."
    )
    if raise_on_mismatch:
        raise SessionDayMismatchError(msg)
    logger.warning(msg)
    return mismatches


def plan_session_day_fixes(
    sessions: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Build rekey plan: stored_day → correct_day, with PK conflict flags.

    Pass ``sessions`` for unit tests; otherwise fetches all exp.Session rows.
    """
    if sessions is None:
        sessions = list(
            exp.Session().fetch("mouse_name", "day", "attempt", "doe", as_dict=True)
        )
    else:
        sessions = list(sessions)

    mismatches = find_session_day_mismatches(sessions)
    by_key: Dict[Tuple[str, int, int], Dict[str, Any]] = {
        (r["mouse_name"], int(r["day"]), int(r["attempt"])): r for r in sessions
    }
    occupied = set(by_key)
    claimed: Set[Tuple[str, int, int]] = set()
    plans: List[Dict[str, Any]] = []

    for row in mismatches:
        target = (row["mouse_name"], int(row["correct_day"]), int(row["attempt"]))
        conflict: Optional[str] = None
        if target in occupied:
            occ = by_key[target]
            # Same doe → leftover from a partial prior rekey; allow resume.
            if _as_date(occ["doe"]) != _as_date(row["doe"]):
                conflict = (
                    f"target PK already exists with different doe "
                    f"(day={row['correct_day']} attempt={row['attempt']} "
                    f"doe={_as_date(occ['doe']).isoformat()})"
                )
        elif target in claimed:
            conflict = (
                f"another mismatch maps to the same PK "
                f"(day={row['correct_day']} attempt={row['attempt']})"
            )
        if conflict is None and target not in occupied:
            claimed.add(target)
        plans.append({**row, "conflict": conflict})
    return plans


def _rekey_session_day(
    *,
    mouse_name: str,
    stored_day: int,
    attempt: int,
    correct_day: int,
) -> None:
    """Move one Session (+ ScoreSheet + base.Base) to a new day PK.

    Resumes if a prior run already inserted the target row with the same doe.
    """
    old_key = {
        "mouse_name": mouse_name,
        "day": stored_day,
        "attempt": attempt,
    }
    new_key = {
        "mouse_name": mouse_name,
        "day": correct_day,
        "attempt": attempt,
    }
    if not (exp.Session() & old_key):
        if exp.Session() & new_key:
            return
        raise RuntimeError(f"Session disappeared before rekey: {old_key}")

    session_row = (exp.Session() & old_key).fetch1()
    old_doe = _as_date(session_row["doe"])

    if exp.Session() & new_key:
        existing = (exp.Session() & new_key).fetch1()
        if _as_date(existing["doe"]) != old_doe:
            raise RuntimeError(
                f"Target Session PK already exists with different doe: "
                f"{mouse_name} day={correct_day} attempt={attempt}"
            )
        logger.info(
            "Resuming rekey for %s day %s→%s attempt=%s (target already present).",
            mouse_name,
            stored_day,
            correct_day,
            attempt,
        )
    else:
        exp.Session.insert1({**session_row, "day": correct_day})

    try:
        from vr4mice.schema.base import Base

        for base_row in (Base() & old_key).fetch(as_dict=True):
            _dj_delete(Base() & {"dataset": base_row["dataset"]})
            Base.insert1(
                {**base_row, "day": correct_day},
                allow_direct_insert=True,
                skip_duplicates=True,
            )
    except Exception as err:
        logger.warning(
            "base.Base rekey skipped or partial for %s day %s→%s: %s: %s",
            mouse_name,
            stored_day,
            correct_day,
            type(err).__name__,
            err,
        )

    for sheet in (exp.SessionScoreSheet() & old_key).fetch(as_dict=True):
        exp.SessionScoreSheet.insert1(
            {**sheet, "day": correct_day},
            skip_duplicates=True,
        )
    if exp.SessionScoreSheet() & old_key:
        _dj_delete(exp.SessionScoreSheet() & old_key)

    _dj_delete(exp.Session() & old_key)


def fix_session_days(*, dry_run: bool = True) -> Tuple[int, int, int]:
    """
    Rekey exp.Session.day to match (doe − first doe) + 1.

    Dry-run by default. With dry_run=False, requires replication off.
    Also rekeys SessionScoreSheet and base.Base when present.

    Returns (ok_count, conflict_count, error_count).
    """
    if not dry_run:
        check_replication_off(log=logger)

    log_mutation_target(action="fix_session_days", dry_run=dry_run)

    plans = plan_session_day_fixes()
    if not plans:
        logger.info("fix_session_days: all Session.day values already match doe.")
        return (0, 0, 0)

    logger.info(
        "fix_session_days: %d session(s) to rekey (%s).",
        len(plans),
        "dry-run" if dry_run else "APPLY",
    )

    n_ok = n_conflict = n_err = 0
    for plan in plans:
        label = (
            f"{plan['mouse_name']} day {plan['stored_day']}→{plan['correct_day']} "
            f"attempt={plan['attempt']} doe={plan['doe']}"
        )
        if plan["conflict"]:
            logger.error("  CONFLICT %s — %s", label, plan["conflict"])
            n_conflict += 1
            continue
        if dry_run:
            logger.warning("  would rekey %s", label)
            n_ok += 1
            continue
        try:
            _rekey_session_day(
                mouse_name=plan["mouse_name"],
                stored_day=int(plan["stored_day"]),
                attempt=int(plan["attempt"]),
                correct_day=int(plan["correct_day"]),
            )
            logger.info("  rekeyed %s", label)
            n_ok += 1
        except Exception:
            logger.exception("  failed %s", label)
            n_err += 1

    logger.info(
        "fix_session_days summary: %d ok, %d conflict, %d error.",
        n_ok,
        n_conflict,
        n_err,
    )
    if dry_run and n_ok:
        logger.warning(
            "Dry run only. Re-run: python run_base.py fix_session_days --force"
        )
    if n_conflict or n_err:
        raise RuntimeError(
            f"fix_session_days incomplete: {n_conflict} conflict(s), {n_err} error(s)."
        )
    return (n_ok, n_conflict, n_err)


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

  4. Verify / fix Session.day vs doe timeline:
       python run_base.py check_session_days
       python run_base.py fix_session_days          # dry-run
       python run_base.py fix_session_days --force  # apply rekey

Never deletes on main. Orphan cleanup / fix_session_days --force need replication OFF.

MySQL diagnostics: make -f mysql.mk replication-summary
================================================================================
""".format(
    sync_mice=SYNC_MICE_COMMAND,
    cleanup_orphans=CLEANUP_ORPHANS_COMMAND,
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


def _sql_row_get(row: Any, key: str, *, index: Optional[int] = None, default=None):
    """Read a column from a DJ/pymysql row (dict or tuple)."""
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if index is not None and isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return default


def describe_connected_database() -> str:
    """Human-readable target for the current DataJoint connection (DJ_HOST)."""
    env_host = os.environ.get("DJ_HOST", "(DJ_HOST unset)")
    env_user = os.environ.get("DJ_USER", "(DJ_USER unset)")
    main_host = os.environ.get("DJ_MAIN_HOST", "")
    try:
        row = (
            dj.conn()
            .query(
                "SELECT @@hostname AS h, @@port AS p, @@server_uuid AS u, "
                "DATABASE() AS d"
            )
            .fetchone()
        )
        if isinstance(row, dict):
            hostname, port, uuid, db = (
                row.get("h"),
                row.get("p"),
                row.get("u"),
                row.get("d"),
            )
        else:
            hostname, port, uuid, db = row[0], row[1], row[2], row[3]
        uuid_s = str(uuid)[:8] + "..." if uuid else "?"
        live = f"{hostname}:{port} uuid={uuid_s} db={db}"
    except Exception as err:
        live = f"(could not read @@port: {type(err).__name__})"
    note = " (DJ_MAIN_HOST is set but unused by run_base)" if main_host else ""
    return f"DJ_HOST={env_host} user={env_user} → live MySQL {live}{note}"


def log_mutation_target(*, action: str, dry_run: bool = False, log=None) -> None:
    """Log exactly which database will be read/mutated (never DJ_MAIN_HOST)."""
    log = log or logger
    target = describe_connected_database()
    if dry_run:
        log.warning("DRY-RUN %s on %s — no deletes/writes applied.", action, target)
    else:
        log.warning(
            "APPLY %s on %s — mutations affect this DB only (not DJ_MAIN_HOST).",
            action,
            target,
        )


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

    if status is not None and not isinstance(status, dict):
        # Tuple rows lack column names; skip IO/SQL parse (read_only check still runs).
        log.warning(
            "Replication status row is not a mapping (%s); skipping IO/SQL check.",
            type(status).__name__,
        )
        status = None

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

    # SHOW VARIABLES → dict {"Value": ...} or tuple (Variable_name, Value)
    ro = _sql_row_get(
        read_only[0] if read_only else None, "Value", index=1, default="OFF"
    )
    sro = _sql_row_get(
        super_ro[0] if super_ro else None, "Value", index=1, default="OFF"
    )
    ro = "OFF" if ro is None else str(ro)
    sro = "OFF" if sro is None else str(sro)
    if ro.upper() == "ON" or sro.upper() == "ON":
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
        _dj_delete(exp.SessionScoreSheet() & key)
        _dj_delete(exp.Session() & key)

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
            _dj_delete(table() & restriction)
        _dj_delete(mice.Mouse() & restriction)

    logger.info("Deleted %d orphan mice.Mouse row(s).", len(names))
    return len(names)


def cleanup_orphan_exp_mice(*, dry_run: bool = True) -> Tuple[int, int]:
    """
    Remove **local** exp/mice rows that are not backed by a vr4mice.Dataset.

    Never touches the parent DB. Separate from ``recover_base`` — run via
    ``python run_base.py cleanup_orphans``.
    """
    log_mutation_target(action="cleanup_orphans", dry_run=dry_run)
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
    """Sync days and populate base/exp from all unpopulated GUI .npy files.

    Aborts if sync_days cannot apply required .npy day updates — otherwise
    populate would ingest wrong exp.Session.day values.
    """
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

    # keys2tables fills Manual mice/exp only; Base is Computed and needs populate().
    from vr4mice.schema.base import Base

    before = len(Base())
    Base.populate(display_progress=True)
    after = len(Base())
    logger.info(
        "base.Base.populate: %d → %d row(s) (+%d).", before, after, after - before
    )

    warn_incomplete_mice(log=logger)
    logger.info(POST_RECOVERY_NOTE)
