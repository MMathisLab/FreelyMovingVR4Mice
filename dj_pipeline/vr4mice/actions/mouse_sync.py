"""Mouse registry helpers: stubs for local ingest, incomplete-mouse warnings, cleanup.

Parent → local mice registry sync is host-side mysqldump
(``make -f mysql.mk sync-mice-from-main``), not DataJoint.
"""

from __future__ import annotations

import datetime
import os
from typing import List, Optional, Sequence, Set

import datajoint as dj
from base_schemas.schemas import exp, mice
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

STUB_MOUSE_ID = -1
STUB_DOB = datetime.date(1970, 1, 1)
SYNC_MICE_COMMAND = (
    "make -f mysql.mk sync-mice-from-main  # host; optional MOUSE=Name1,Name2; "
    "set DJ_MAIN_HOST (and optionally DJ_MAIN_USER/DJ_MAIN_PWD)"
)
DEFAULT_GUI_PATHS = ("/data/data", "/data/processed")


def is_stub_mouse(row: dict) -> bool:
    """Return True for placeholder rows created during local ingest."""
    return row.get("mouse_id") == STUB_MOUSE_ID


def get_session_mouse_names() -> Set[str]:
    """Mouse names that have at least one Session row in this database."""
    names = exp.Session().fetch("mouse_name")
    return {name for name in names if name}


def get_dataset_mouse_names() -> Set[str]:
    """Mouse names inferred from local vr4mice.Dataset stems."""
    from vr4mice.schema import vr4mice
    from vr4mice.schema.base import parse_filename

    names: Set[str] = set()
    for row in vr4mice.Dataset().fetch("dataset", as_dict=True):
        try:
            names.add(parse_filename(row["dataset"])["mouse_name"])
        except ValueError as err:
            logger.warning("Skipping unparseable dataset %r: %s", row["dataset"], err)
    return names


def get_gui_mouse_names(paths: Optional[Sequence[str]] = None) -> Set[str]:
    """Mouse names from GUI ``.npy`` stems (cold recover before Dataset/Session)."""
    from vr4mice.actions.populate_rig import get_filenames
    from vr4mice.schema.base import parse_filename

    candidates = list(DEFAULT_GUI_PATHS if paths is None else paths)
    existing = [os.path.normpath(p) for p in candidates if os.path.isdir(p)]
    names: Set[str] = set()
    for folder in existing:
        for filename in get_filenames([".npy"], folder).get(".npy", []):
            stem = filename.rsplit(".", 1)[0]
            try:
                names.add(parse_filename(stem)["mouse_name"])
            except ValueError as err:
                logger.warning(
                    "Skipping unparseable GUI file %r in %s: %s", filename, folder, err
                )
    return names


def get_known_local_mouse_names(
    *, gui_paths: Optional[Sequence[str]] = None
) -> Set[str]:
    """Mouse names from Sessions, Datasets, and/or GUI .npy stems on disk."""
    return (
        get_session_mouse_names()
        | get_dataset_mouse_names()
        | get_gui_mouse_names(gui_paths)
    )


def get_incomplete_mouse_names(
    *, gui_paths: Optional[Sequence[str]] = None
) -> List[str]:
    """Known local mice (Session/Dataset/GUI) that are missing or stubs."""
    candidates = sorted(get_known_local_mouse_names(gui_paths=gui_paths))
    if not candidates:
        return []

    by_name = {
        row["mouse_name"]: row
        for row in mice.Mouse().fetch(as_dict=True)
        if row.get("mouse_name")
    }
    return [
        name
        for name in candidates
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

    return parse_filename(dataset).get("mouse_name")


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
    (mouse_id=-1) until host mysql.mk pulls records from the main DB.
    """
    log = log or logger
    mouse_name = _mouse_name_from_raw(raw_data, dataset)
    if not mouse_name:
        log.warning("Could not resolve mouse_name for dataset %s.", dataset)
        return False

    existing = (mice.Mouse() & {"mouse_name": mouse_name}).fetch(as_dict=True)
    if existing:
        if not is_stub_mouse(existing[0]):
            return False
        row = _mouse_row_from_raw(raw_data, mouse_name)
        if is_stub_mouse(row):
            return False
        mice.Mouse.insert1(row, replace=True)
        log.info("Upgraded stub Mouse for %s from session metadata.", mouse_name)
        return True

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
    """Log a warning for Dataset/session mice that still need a main-DB sync."""
    log = log or logger
    incomplete = get_incomplete_mouse_names()
    if incomplete:
        log.warning(
            "%d Dataset/session mice have stub or missing Mouse records: %s. Run: %s",
            len(incomplete),
            ", ".join(incomplete),
            SYNC_MICE_COMMAND,
        )
    return incomplete


def ensure_water_restriction_on_fk_table(row: dict, *, log=None) -> bool:
    """
    Mirror a water-restriction row into ``mouse_score_sheet__water_restriction``.

    Some local DBs have both ``mouse_score_sheet_water_restriction`` (``_``) and
    ``mouse_score_sheet__water_restriction`` (``__``). DataJoint may insert into
    ``_`` while ``exp.session_score_sheet`` FKs to ``__``, causing populate to
    fail after a successful WaterRestriction insert.
    """
    log = log or logger
    conn = dj.conn()
    fk_table = "mouse_score_sheet__water_restriction"
    rows = conn.query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'mice' AND table_name LIKE '%water_restriction%'"
    ).fetchall()
    tables = {r[0] for r in rows}
    if fk_table not in tables:
        return False

    key = {"mouse_name": row["mouse_name"], "doc": row["doc"]}
    payload = {
        "mouse_name": row["mouse_name"],
        "doc": row["doc"],
        "weight_percentage": row["weight_percentage"],
    }
    ft = dj.FreeTable(conn, f"`mice`.`{fk_table}`")
    if ft & key:
        return False
    ft.insert1(payload, skip_duplicates=True)
    log.debug(
        "Mirrored water restriction for %s doc=%s into %s (SessionScoreSheet FK).",
        key["mouse_name"],
        key["doc"],
        fk_table,
    )
    return True


def cleanup_mice_without_sessions(
    *, dry_run: bool = True, stubs_only: bool = True
) -> int:
    """
    Remove Mouse rows that are not referenced by any local Session.

    By default only stub rows (mouse_id=-1) are removed. For Dataset-based
    orphan Session/Mouse cleanup, use ``cleanup_orphans``.
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
