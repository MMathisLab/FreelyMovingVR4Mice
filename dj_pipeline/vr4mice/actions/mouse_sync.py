"""Mouse registry helpers: stubs for local ingest, sync from main DB, cleanup."""

from __future__ import annotations

import datetime
import os
from contextlib import contextmanager
from typing import Iterable, List, Optional, Set

import datajoint as dj
from base_schemas.schemas import exp, mice
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

STUB_MOUSE_ID = -1
STUB_DOB = datetime.date(1970, 1, 1)
SYNC_MICE_COMMAND = "python run_base.py sync_mice  # set DJ_MAIN_HOST (and optionally DJ_MAIN_USER/DJ_MAIN_PWD)"
SYNC_EXP_COMMAND = "python run_base.py sync_exp  # set DJ_MAIN_HOST; requires write access on main exp schema"

MOUSE_SYNC_TABLES = (
    mice.Mouse,
    mice.Surgery,
    mice.MouseScoreSheet,
    mice.MouseScoreSheet_WaterRestriction,
)


def is_stub_mouse(row: dict) -> bool:
    """Return True for placeholder rows created during local ingest."""
    return row.get("mouse_id") == STUB_MOUSE_ID


def get_session_mouse_names() -> Set[str]:
    """Mouse names that have at least one Session row in this database."""
    names = exp.Session().fetch("mouse_name")
    return {name for name in names if name}


def get_incomplete_mouse_names() -> List[str]:
    """Session mice that are missing or still have stub Mouse records."""
    session_mice = sorted(get_session_mouse_names())
    if not session_mice:
        return []

    by_name = {
        row["mouse_name"]: row
        for row in mice.Mouse().fetch(as_dict=True)
        if row.get("mouse_name")
    }
    return [
        name
        for name in session_mice
        if name not in by_name or is_stub_mouse(by_name[name])
    ]


def _mouse_name_from_raw(
    raw_data: dict, dataset: Optional[str] = None
) -> Optional[str]:
    mouse_name = raw_data.get("mouse_name")
    if mouse_name:
        return mouse_name
    if not dataset:
        return None
    from vr4mice.schema.base import parse_filename

    parsed = parse_filename(dataset)
    return parsed.get("mouse_name")


def _mouse_row_from_raw(raw_data: dict, mouse_name: str) -> dict:
    required = ("mouse_id", "dob", "sex", "strain")
    if all(raw_data.get(key) not in (None, "") for key in required):
        dob = raw_data["dob"]
        if isinstance(dob, str):
            dob = datetime.date.fromisoformat(dob)
        return {
            "mouse_name": mouse_name,
            "mouse_id": int(raw_data["mouse_id"]),
            "dob": dob,
            "sex": raw_data["sex"],
            "strain": raw_data["strain"],
        }

    mice.Strain.insert1(
        {"strain": "N/A", "formal_name": "N/A", "stock_number": "N/A"},
        skip_duplicates=True,
    )
    return {
        "mouse_name": mouse_name,
        "mouse_id": STUB_MOUSE_ID,
        "dob": STUB_DOB,
        "sex": raw_data.get("sex") or "U",
        "strain": raw_data.get("strain") or "N/A",
    }


def ensure_mouse_for_session(
    raw_data: dict,
    *,
    dataset: Optional[str] = None,
    log=None,
) -> bool:
    """
    Ensure a Mouse row exists so exp.Session can be populated.

    Inserts a full row when .npy metadata is available, otherwise a stub
    identified by mouse_id=-1 until sync_mice pulls records from the main DB.
    """
    log = log or logger
    mouse_name = _mouse_name_from_raw(raw_data, dataset)
    if not mouse_name:
        log.warning("Could not resolve mouse_name for dataset %s.", dataset)
        return False

    if mice.Mouse() & {"mouse_name": mouse_name}:
        return False

    row = _mouse_row_from_raw(raw_data, mouse_name)
    mice.Mouse.insert1(row, skip_duplicates=True)

    if is_stub_mouse(row):
        log.warning(
            "Inserted stub Mouse for %s (mouse_id=%s). "
            "Sync full metadata from the main database with: %s",
            mouse_name,
            STUB_MOUSE_ID,
            SYNC_MICE_COMMAND,
        )
    else:
        log.info("Inserted Mouse for %s from session metadata.", mouse_name)
    return True


def warn_incomplete_mice(log=None) -> List[str]:
    """Log a warning for session mice that still need a main-DB sync."""
    log = log or logger
    incomplete = get_incomplete_mouse_names()
    if incomplete:
        log.warning(
            "%d session mice have stub or missing Mouse records: %s. Run: %s",
            len(incomplete),
            ", ".join(incomplete),
            SYNC_MICE_COMMAND,
        )
    return incomplete


def _require_dj_main_host() -> None:
    if not os.environ.get("DJ_MAIN_HOST"):
        raise ValueError(
            "DJ_MAIN_HOST is not set. Example: export DJ_MAIN_HOST=main.server:3306"
        )


@contextmanager
def _main_database():
    """Temporarily point DataJoint at DJ_MAIN_HOST, then restore local config."""
    keys = ("database.host", "database.user", "database.password")
    saved = {key: dj.config[key] for key in keys}
    dj.config["database.host"] = os.environ["DJ_MAIN_HOST"]
    dj.config["database.user"] = os.environ.get("DJ_MAIN_USER", saved["database.user"])
    dj.config["database.password"] = os.environ.get(
        "DJ_MAIN_PWD", saved["database.password"]
    )
    dj.conn(reset=True)
    try:
        yield
    finally:
        for key, value in saved.items():
            dj.config[key] = value
        dj.conn(reset=True)


def _upsert_rows(table, rows: Iterable[dict]) -> int:
    count = 0
    pk = table.primary_key
    for row in rows:
        key = {field: row[field] for field in pk if field in row}
        if key and table & key:
            (table & key).delete()
        table.insert1(row)
        count += 1
    return count


def sync_mice_from_main(log=None) -> int:
    """
    Copy Mouse-related rows from the main database onto this local DB.

    Fetches on DJ_MAIN_HOST, then upserts locally. Only incomplete/stub mice
    that already have a local exp.Session are synced.
    """
    log = log or logger
    _require_dj_main_host()

    mouse_names = sorted(get_session_mouse_names())
    if not mouse_names:
        log.info("No local sessions found; nothing to sync.")
        return 0

    targets = get_incomplete_mouse_names()
    if not targets:
        log.info(
            "All %d session mice already have full local Mouse records.",
            len(mouse_names),
        )
        return 0

    log.info(
        "Fetching %d/%d session mice from main DB (%s): %s",
        len(targets),
        len(mouse_names),
        os.environ["DJ_MAIN_HOST"],
        ", ".join(targets),
    )

    fetched: List[tuple] = []
    with _main_database():
        for name in targets:
            restriction = {"mouse_name": name}
            for table in MOUSE_SYNC_TABLES:
                rows = (table() & restriction).fetch(as_dict=True)
                if rows:
                    fetched.append((table, rows))

    inserted = 0
    for table, rows in fetched:
        inserted += _upsert_rows(table(), rows)

    log.info("Synced mouse metadata onto local DB (%d rows upserted).", inserted)
    remaining = get_incomplete_mouse_names()
    if remaining:
        log.warning(
            "Still incomplete after sync: %s. "
            "Those mice may not exist on the main database.",
            ", ".join(remaining),
        )
    return inserted


def _session_primary_key(row: dict) -> dict:
    return {field: row[field] for field in exp.Session.primary_key if field in row}


def _pk_tuple(key: dict) -> tuple:
    return tuple(key[field] for field in exp.Session.primary_key)


def sync_exp_to_main(log=None) -> int:
    """
    Push local exp.Session (+ SessionScoreSheet) rows that are missing on parent.

    Requires DJ_MAIN_HOST and write access on main ``exp``. Does not overwrite
    existing parent sessions. Mouse must already exist on main.
    """
    log = log or logger
    _require_dj_main_host()

    local_sessions = exp.Session().fetch(as_dict=True)
    if not local_sessions:
        log.info("No local exp.Session rows; nothing to push.")
        return 0

    sheets_by_key = {
        _pk_tuple(_session_primary_key(row)): row
        for row in exp.SessionScoreSheet().fetch(as_dict=True)
    }

    log.info(
        "Pushing missing local exp.Session row(s) to main DB (%s) "
        "(%d local session(s) to consider)",
        os.environ["DJ_MAIN_HOST"],
        len(local_sessions),
    )

    inserted = 0
    skipped_missing_mouse: List[str] = []
    skipped_existing = 0
    failed: List[str] = []

    with _main_database():
        for row in local_sessions:
            key = _session_primary_key(row)
            mouse_name = row.get("mouse_name")
            if not (mice.Mouse() & {"mouse_name": mouse_name}):
                skipped_missing_mouse.append(mouse_name or "?")
                continue

            if exp.Session() & key:
                skipped_existing += 1
                continue

            try:
                exp.Session.insert1(row)
                inserted += 1
                sheet_row = sheets_by_key.get(_pk_tuple(key))
                if sheet_row is not None and not (exp.SessionScoreSheet() & key):
                    exp.SessionScoreSheet.insert1(sheet_row)
                    inserted += 1
            except Exception as err:
                failed.append(f"{key}: {err}")

    if skipped_missing_mouse:
        missing = sorted(set(skipped_missing_mouse))
        log.warning(
            "Skipped %d session(s): mouse not on main DB: %s. "
            "Ensure mice exist on parent, then re-run: %s",
            len(skipped_missing_mouse),
            ", ".join(missing),
            SYNC_EXP_COMMAND,
        )
    if skipped_existing:
        log.info("Skipped %d session(s) already present on main.", skipped_existing)
    if failed:
        log.warning("Failed to push %d row(s): %s", len(failed), "; ".join(failed[:10]))
    log.info("Pushed %d exp row(s) to main DB.", inserted)
    return inserted


def cleanup_mice_without_sessions(
    *, dry_run: bool = True, stubs_only: bool = True
) -> int:
    """
    Remove Mouse rows that are not referenced by any local Session.

    By default only stub rows (mouse_id=-1) are removed. For Dataset-based
    orphan Session/Mouse cleanup, use recover_base instead.
    """
    session_mice = get_session_mouse_names()
    candidates = []
    for row in mice.Mouse().fetch(as_dict=True):
        if row["mouse_name"] in session_mice:
            continue
        if stubs_only and not is_stub_mouse(row):
            continue
        candidates.append(row["mouse_name"])

    if not candidates:
        logger.info("No mouse rows to clean up.")
        return 0

    if dry_run:
        logger.warning(
            "Dry run: would delete %d Mouse rows without local sessions: %s. "
            "Re-run with: python run_base.py cleanup_mice --force",
            len(candidates),
            ", ".join(sorted(candidates)),
        )
        return len(candidates)

    deleted = 0
    for name in candidates:
        (mice.Mouse() & {"mouse_name": name}).delete()
        deleted += 1
    logger.info("Deleted %d Mouse rows without local sessions.", deleted)
    return deleted
