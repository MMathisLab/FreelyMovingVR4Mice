"""Mouse registry helpers: stubs for local ingest, sync from main DB, cleanup."""

from __future__ import annotations

import datetime
import os
import traceback
from contextlib import contextmanager
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import datajoint as dj
from base_schemas.schemas import exp, mice
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

STUB_MOUSE_ID = -1
STUB_DOB = datetime.date(1970, 1, 1)
SYNC_MICE_COMMAND = (
    "python run_base.py sync_mice  # or: sync_mice --mouse NAME; "
    "set DJ_MAIN_HOST (and optionally DJ_MAIN_USER/DJ_MAIN_PWD)"
)
SYNC_EXP_COMMAND = (
    "python run_base.py sync_exp  # optional; DJ_MAIN_HOST + write on main exp; "
    "local (non-collab) sessions only"
)
DEFAULT_GUI_PATHS = ("/data/data", "/data/processed")

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
    """
    Mouse names from GUI ``.npy`` stems under data/ and processed/.

    Lets ``sync_mice`` run before Dataset/Session rows exist (cold recover).
    """
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
    """
    Known local mice (Session, Dataset, and/or GUI files) that are missing/stubs.

    Used so sync_mice can run before base populate on a cold recover.
    """
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
    If a stub already exists and .npy now has full metadata, replace the stub.
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


def _require_dj_main_host() -> None:
    if not os.environ.get("DJ_MAIN_HOST"):
        raise ValueError(
            "DJ_MAIN_HOST is not set. Example: export DJ_MAIN_HOST=main.server:3306"
        )


@contextmanager
def _pymysql_disable_ssl():
    """
    Force plain MySQL (no TLS) for the next pymysql.connect().

    DataJoint 2.x ``use_tls=False`` still ends up SSL-wrapping on this stack.
    Patching pymysql is the reliable way to skip SSL for lab servers.
    """
    import pymysql

    original = pymysql.connect

    def connect_no_ssl(*args, **kwargs):
        kwargs["ssl"] = None
        kwargs["ssl_disabled"] = True
        for key in (
            "ssl_ca",
            "ssl_cert",
            "ssl_key",
            "ssl_verify_cert",
            "ssl_verify_identity",
            "ssl_key_password",
        ):
            kwargs.pop(key, None)
        return original(*args, **kwargs)

    pymysql.connect = connect_no_ssl
    try:
        yield
    finally:
        pymysql.connect = original


def _split_host_port(host_port: str, default_port: int = 3306) -> Tuple[str, int]:
    """Parse ``host`` or ``host:port`` (DataJoint-style)."""
    raw = (host_port or "").strip()
    if not raw:
        raise ValueError("Empty host")
    # IPv6 like [::1]:3306 — keep simple host:port for lab IPv4/hostname.
    if raw.count(":") == 1:
        host, _, port_s = raw.partition(":")
        return host, int(port_s) if port_s else default_port
    return raw, default_port


def _endpoint_from_config(host_value, port_value=None) -> Tuple[str, int]:
    """Resolve host/port from config (host may already be ``host:port``)."""
    host_s = "" if host_value is None else str(host_value).strip()
    if host_s.count(":") == 1:
        return _split_host_port(host_s)
    if port_value is None or port_value == "":
        return host_s, 3306
    return host_s, int(port_value)


def _active_endpoint() -> Tuple[str, int]:
    """Best-effort host:port from the live DataJoint connection."""
    conn = dj.conn()
    info = getattr(conn, "conn_info", None) or {}
    host = info.get("host") or dj.config["database.host"]
    port = info.get("port") or dj.config["database.port"]
    return _endpoint_from_config(host, port)


def _rebind_schema_connection(conn) -> None:
    """
    Point base ``mice`` (and related) schemas at ``conn``.

    ``dj.Schema`` keeps the Connection from first import/connect. After
    ``dj.conn(reset=True)`` to main, ``mice.Mouse()`` can still query the old
    local conn unless we rebind — and setattr on a read-only ``connection``
    property is often a no-op. Prefer ``_table_on_conn`` for main fetches.
    """
    schemas = []
    try:
        schemas.append(mice.schema)
    except Exception:
        pass
    try:
        schemas.append(exp.schema)
    except Exception:
        pass
    for schema in schemas:
        for attr in ("connection", "_connection", "_conn"):
            try:
                object.__setattr__(schema, attr, conn)
            except Exception:
                pass
            try:
                schema.__dict__[attr] = conn
            except Exception:
                pass
            try:
                setattr(schema, attr, conn)
            except Exception:
                pass


def _mysql_port(conn) -> Optional[int]:
    """``@@port`` for a live Connection, or None."""
    if conn is None:
        return None
    try:
        row = conn.query("SELECT @@port").fetchone()
        return int(row[0])
    except Exception:
        return None


def _table_on_conn(conn, table_cls):
    """
    Return a queryable table bound to ``conn``.

    When ``conn`` is set, uses ``dj.FreeTable`` so we never accidentally read
    through the schema's imported local Connection. Falls back to
    ``table_cls()`` when ``conn`` is None or ``full_table_name`` is unavailable
    (unit-test mocks).
    """
    if conn is None:
        return table_cls()
    full = getattr(table_cls, "full_table_name", None)
    if not isinstance(full, str) or "`" not in full:
        inst_full = getattr(table_cls(), "full_table_name", None)
        if isinstance(inst_full, str) and "`" in inst_full:
            full = inst_full
        else:
            return table_cls()
    return dj.FreeTable(conn, full)


def _dj_connect(*, host: str, port: int, user: str, password: str, disable_ssl: bool):
    """Connect with explicit host/port (do not leave local port stuck at 3309)."""
    dj.config["database.host"] = host
    dj.config["database.port"] = int(port)
    dj.config["database.user"] = user
    dj.config["database.password"] = password

    def _call():
        try:
            return dj.conn(
                host=host,
                user=user,
                password=password,
                port=int(port),
                reset=True,
            )
        except TypeError:
            return dj.conn(reset=True)

    if disable_ssl:
        with _pymysql_disable_ssl():
            conn = _call()
    else:
        conn = _call()
    _rebind_schema_connection(conn)
    return conn


@contextmanager
def _main_database():
    """Temporarily point DataJoint at DJ_MAIN_HOST; yield that Connection."""
    # Never use `key in dj.config` — DJ Config.__contains__ breaks (int keys).
    # Must switch host AND port: local is often :3309 while main is :3306 on the
    # same IP. Leaving port at 3309 made sync query the local DB.
    keys = ("database.host", "database.user", "database.password", "database.port")
    saved = {}
    for key in keys:
        try:
            saved[key] = dj.config[key]
        except Exception:
            pass

    local_ep = _endpoint_from_config(
        saved.get("database.host", dj.config["database.host"]),
        saved.get("database.port"),
    )
    main_host, main_port = _split_host_port(os.environ["DJ_MAIN_HOST"])
    main_user = os.environ.get("DJ_MAIN_USER", saved.get("database.user"))
    main_password = os.environ.get("DJ_MAIN_PWD", saved.get("database.password"))
    main_ep = (main_host, main_port)

    if main_ep == local_ep:
        logger.error(
            "DJ_MAIN_HOST=%s resolves to the same endpoint as local (%s:%s). "
            "Sync would read the local DB. Set DJ_MAIN_HOST to the parent host:port.",
            os.environ["DJ_MAIN_HOST"],
            local_ep[0],
            local_ep[1],
        )

    try:
        conn = _dj_connect(
            host=main_host,
            port=main_port,
            user=main_user,
            password=main_password,
            disable_ssl=True,
        )
        active = _active_endpoint()
        logger.info(
            "Main DB connection requested %s:%s → active %s:%s (user=%s)",
            main_host,
            main_port,
            active[0],
            active[1],
            main_user,
        )
        if active == local_ep:
            raise RuntimeError(
                "Still connected to local endpoint %s:%s after switching to main. "
                "Check DJ_MAIN_HOST (include :3306) and database.port."
                % (local_ep[0], local_ep[1])
            )
        conn_port = _mysql_port(conn)
        schema_conn = getattr(getattr(mice, "schema", None), "connection", None)
        schema_port = _mysql_port(schema_conn)
        try:
            sql_count = conn.query("SELECT COUNT(*) FROM mice.mouse").fetchone()[0]
        except Exception as err:
            sql_count = "err:%s" % err
        logger.info(
            "Main MySQL session: conn @@port=%s schema @@port=%s "
            "SQL mice.mouse COUNT(*)=%s",
            conn_port,
            schema_port,
            sql_count,
        )
        if schema_port is not None and conn_port is not None and schema_port != conn_port:
            logger.warning(
                "mice.schema is still on @@port=%s (local) while main conn is "
                "@@port=%s — fetches will use FreeTable on main conn.",
                schema_port,
                conn_port,
            )
    except Exception:
        traceback.print_exc()
        raise
    try:
        yield conn
    finally:
        for key, value in saved.items():
            dj.config[key] = value
        try:
            # Restore local; host may be stored as host:port in config.
            loc_host, loc_port = local_ep
            loc_user = saved.get("database.user")
            loc_password = saved.get("database.password")
            if loc_user is not None and loc_password is not None:
                _dj_connect(
                    host=loc_host,
                    port=loc_port,
                    user=loc_user,
                    password=loc_password,
                    disable_ssl=False,
                )
            else:
                dj.conn(reset=True)
        except Exception:
            pass


def _upsert_rows(table, rows: Iterable[dict]) -> int:
    """
    Insert or replace rows locally without cascading deletes.

    Uses ``replace=True`` (not delete-then-insert) so refreshing a Mouse stub
    cannot wipe dependent local ``exp.Session`` rows.
    """
    count = 0
    for row in rows:
        table.insert1(row, replace=True)
        count += 1
    return count


def sync_mice_from_main(
    log=None,
    *,
    gui_paths: Optional[Sequence[str]] = None,
    mouse_names: Optional[Sequence[str]] = None,
) -> int:
    """
    Pull Mouse metadata from main for selected or locally needed mice.

    If ``mouse_names`` is set, sync those names from main (for preloading
    before recordings). Otherwise sync incomplete/stub names from local
    ``vr4mice.Dataset``, ``exp.Session``, and/or GUI ``.npy`` stems.

    Fetches on ``DJ_MAIN_HOST``, then upserts locally (``replace=True``; never
    deletes on main). Strain rows are pulled first.
    """
    log = log or logger
    _require_dj_main_host()

    explicit = [n.strip() for n in (mouse_names or []) if n and str(n).strip()]
    if explicit:
        targets = sorted(set(explicit))
        log.info(
            "Fetching %d named mice from main DB (%s): %s",
            len(targets),
            os.environ["DJ_MAIN_HOST"],
            ", ".join(targets),
        )
    else:
        known = sorted(get_known_local_mouse_names(gui_paths=gui_paths))
        if not known:
            log.info(
                "No local Dataset, Session, or GUI .npy mice found; nothing to sync. "
                "Pass --mouse NAME to preload a mouse before recordings."
            )
            return 0

        targets = get_incomplete_mouse_names(gui_paths=gui_paths)
        if not targets:
            log.info(
                "All %d known local mice already have full Mouse records.",
                len(known),
            )
            return 0

        log.info(
            "Fetching %d/%d known local mice from main DB (%s): %s",
            len(targets),
            len(known),
            os.environ["DJ_MAIN_HOST"],
            ", ".join(targets),
        )

    fetched: List[tuple] = []
    strain_names: Set[str] = set()
    strain_rows: List[dict] = []
    found_on_main: Set[str] = set()
    name_on_main: dict = {}  # local/target name -> canonical mouse_name on main
    try:
        # Yielded conn is the main endpoint; never use mice.Mouse() here — that
        # table object often still points at the local schema Connection.
        with _main_database() as main_conn:

            def _norm_name(raw) -> Optional[str]:
                if raw is None:
                    return None
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="replace")
                text = str(raw).strip()
                return text or None

            mouse_main = _table_on_conn(main_conn, mice.Mouse)
            main_names = [
                n for n in (_norm_name(x) for x in mouse_main.fetch("mouse_name")) if n
            ]
            main_exact = set(main_names)
            main_by_lower = {}
            for n in main_names:
                main_by_lower.setdefault(n.lower(), n)
            sample = ", ".join(sorted(main_exact)[:12])
            log.info(
                "Main mice.Mouse row count (via main conn): %d (sample: %s)",
                len(main_exact),
                sample,
            )

            for name in targets:
                name = _norm_name(name) or name
                canonical = (
                    name if name in main_exact else main_by_lower.get(name.lower())
                )
                if canonical is None:
                    try:
                        needle = "%" + name.lower() + "%"
                        like = main_conn.query(
                            "SELECT mouse_name FROM mice.mouse "
                            "WHERE mouse_name = %s OR LOWER(mouse_name) LIKE %s "
                            "LIMIT 8",
                            (name, needle),
                        ).fetchall()
                        log.warning(
                            "No Mouse row for %r on main; SQL near-matches: %s",
                            name,
                            like,
                        )
                    except Exception as err:
                        log.warning(
                            "No Mouse row for %r on main (SQL probe failed: %s)",
                            name,
                            err,
                        )
                    continue

                if canonical != name:
                    log.info(
                        "Main name for %r is %r (case/spelling map)", name, canonical
                    )
                name_on_main[name] = canonical
                restriction = {"mouse_name": canonical}
                for table in MOUSE_SYNC_TABLES:
                    rows = list(
                        (_table_on_conn(main_conn, table) & restriction).fetch(
                            as_dict=True
                        )
                    )
                    if not rows:
                        continue
                    # Keep local/GUI spelling when main only differs by case.
                    if canonical != name:
                        rows = [
                            {**row, "mouse_name": name} if "mouse_name" in row else row
                            for row in rows
                        ]
                    fetched.append((table, rows))
                    if table is mice.Mouse:
                        found_on_main.add(name)
                        for row in rows:
                            strain = row.get("strain")
                            if strain:
                                strain_names.add(strain)
            for strain in sorted(strain_names):
                strain_rows.extend(
                    list(
                        (
                            _table_on_conn(main_conn, mice.Strain)
                            & {"strain": strain}
                        ).fetch(as_dict=True)
                    )
                )
    except Exception:
        traceback.print_exc()
        log.exception(
            "Failed fetching mice from main DB (%s). "
            "Check DJ_MAIN_HOST (include :port) and DJ_MAIN_USER/PWD.",
            os.environ["DJ_MAIN_HOST"],
        )
        raise

    missing_on_main = [n for n in targets if n not in found_on_main]
    if missing_on_main:
        log.warning(
            "Not found on main DB: %s.",
            ", ".join(missing_on_main),
        )

    inserted = 0
    if strain_rows:
        inserted += _upsert_rows(mice.Strain(), strain_rows)
    for table, rows in fetched:
        inserted += _upsert_rows(table(), rows)

    log.info("Synced mouse metadata onto local DB (%d rows upserted).", inserted)
    if not explicit:
        remaining = get_incomplete_mouse_names(gui_paths=gui_paths)
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


def _session_identity(row: dict) -> Tuple[str, str, int]:
    """(mouse_name, doe_iso, attempt) — matches recover_base / Dataset naming."""
    doe = row["doe"]
    if hasattr(doe, "isoformat"):
        doe = doe.isoformat()
    return (row["mouse_name"], str(doe), int(row["attempt"]))


def _dataset_lab_by_session_key(log=None) -> dict:
    """
    Map session identity → collaborating lab name for local vr4mice.Dataset rows.

    Sessions without a Dataset are omitted (not push candidates).
    Lab is None when Collab has not been populated for that dataset yet.
    """
    log = log or logger
    from vr4mice.schema import vr4mice
    from vr4mice.schema.base import parse_filename

    lab_by_key: dict = {}
    collab_lab = {
        row["dataset"]: row["lab"]
        for row in (vr4mice.Collab() * vr4mice.Labs()).fetch(
            "dataset", "lab", as_dict=True
        )
    }

    for row in vr4mice.Dataset().fetch("dataset", as_dict=True):
        dataset = row["dataset"]
        try:
            parsed = parse_filename(dataset)
        except ValueError as err:
            log.warning("Skipping unparseable dataset %r: %s", dataset, err)
            continue
        key = (parsed["mouse_name"], parsed["date"], int(parsed["attempt"]))
        lab_by_key[key] = collab_lab.get(dataset)
    return lab_by_key


def get_pushable_local_session_keys(log=None) -> Set[Tuple[str, str, int]]:
    """
    Session keys safe to push with sync_exp: local Dataset, this lab only.

    Excludes collaborator datasets (vr4mice.Collab → Labs.lab != DJ_LAB).
    Requires DJ_LAB when any Collab row is present so collab sessions are not
    pushed by accident.
    """
    log = log or logger
    lab_by_key = _dataset_lab_by_session_key(log=log)
    if not lab_by_key:
        log.info("No local vr4mice.Dataset rows; sync_exp will not push any sessions.")
        return set()

    dj_lab = os.environ.get("DJ_LAB")
    has_collab = any(lab is not None for lab in lab_by_key.values())
    if has_collab and not dj_lab:
        raise ValueError(
            "DJ_LAB must be set to run sync_exp when vr4mice.Collab is populated "
            "(needed to exclude collaborator datasets)."
        )

    pushable: Set[Tuple[str, str, int]] = set()
    skipped_collab = 0
    for key, lab in lab_by_key.items():
        if lab is None:
            # Dataset present, Collab not yet populated — treat as local ingest.
            pushable.add(key)
            continue
        if lab == dj_lab:
            pushable.add(key)
        else:
            skipped_collab += 1

    if skipped_collab:
        log.info(
            "Excluding %d collaborator dataset session(s) from sync_exp "
            "(Collab lab != DJ_LAB=%r).",
            skipped_collab,
            dj_lab,
        )
    return pushable


def _doe_str(doe) -> str:
    if hasattr(doe, "isoformat"):
        return doe.isoformat()
    return str(doe)[:10]


def _as_date(doe) -> datetime.date:
    if isinstance(doe, datetime.date) and not isinstance(doe, datetime.datetime):
        return doe
    if isinstance(doe, datetime.datetime):
        return doe.date()
    return datetime.date.fromisoformat(_doe_str(doe))


def _prepare_session_row_for_main(
    row: dict, log=None, *, conn=None
) -> Tuple[str, Optional[dict]]:
    """
    Adapt a local Session row for insert on main (caller must be on main).

    Existence is judged by (mouse_name, doe, attempt), not local day.
    Returns (status, row) where status is ``exists``, ``conflict``, or ``ready``.
    Pass ``conn`` (main Connection) so Session is not read via the local schema.
    """
    log = log or logger
    Session = _table_on_conn(conn, exp.Session)
    mouse_name = row["mouse_name"]
    attempt = int(row["attempt"])
    doe_s = _doe_str(row["doe"])
    doe_date = _as_date(row["doe"])

    if (
        Session
        & {"mouse_name": mouse_name, "attempt": attempt}
        & f'doe="{doe_s}"'
    ):
        return "exists", None

    main_sessions = (Session & {"mouse_name": mouse_name}).fetch(as_dict=True)
    same_doe_days = [
        int(s["day"]) for s in main_sessions if _doe_str(s["doe"]) == doe_s
    ]
    if same_doe_days:
        day = same_doe_days[0]
    elif main_sessions:
        start = min(_as_date(s["doe"]) for s in main_sessions)
        day = (doe_date - start).days + 1
        if day < 1:
            log.warning(
                "Cannot push %s doe=%s attempt=%s: date is before the mouse's "
                "first session on main (start=%s); resolve day numbering manually.",
                mouse_name,
                doe_s,
                attempt,
                start.isoformat(),
            )
            return "conflict", None
    else:
        day = 1

    if Session & {
        "mouse_name": mouse_name,
        "day": day,
        "attempt": attempt,
    }:
        log.warning(
            "Cannot push %s doe=%s attempt=%s: main already has "
            "(day=%s, attempt=%s) for a different session.",
            mouse_name,
            doe_s,
            attempt,
            day,
            attempt,
        )
        return "conflict", None

    out = dict(row)
    out["day"] = day
    out["doe"] = doe_date
    return "ready", out


def sync_exp_to_main(log=None) -> int:
    """
    Optional: push missing local (non-collab) exp.Session rows to parent.

    Only sessions backed by a local ``vr4mice.Dataset`` for this lab (``DJ_LAB``)
    are candidates — collaborator Collab datasets are never pushed.
    Requires ``DJ_MAIN_HOST`` and write access on main ``exp``.

    Matches existing parent sessions by ``(mouse_name, doe, attempt)`` (not local
    ``day``). Assigns ``day`` from the parent mouse timeline when inserting.
    Inserts missing parent rows only — never deletes or overwrites on main.
    Mouse must already exist on main.
    """
    log = log or logger
    _require_dj_main_host()

    local_sessions = exp.Session().fetch(as_dict=True)
    if not local_sessions:
        log.info("No local exp.Session rows; nothing to push.")
        return 0

    pushable = get_pushable_local_session_keys(log=log)
    candidates = [row for row in local_sessions if _session_identity(row) in pushable]
    skipped_non_local = len(local_sessions) - len(candidates)
    if skipped_non_local:
        log.info(
            "Skipped %d session(s) without a local (non-collab) Dataset "
            "(registry/replica/collab only — not pushed).",
            skipped_non_local,
        )
    if not candidates:
        log.info("No local non-collab sessions to push.")
        return 0

    sheets_by_local_pk = {
        _pk_tuple(_session_primary_key(row)): row
        for row in exp.SessionScoreSheet().fetch(as_dict=True)
    }

    log.info(
        "Pushing missing local (non-collab) exp.Session row(s) to main DB (%s) "
        "(%d candidate session(s); match by mouse/doe/attempt)",
        os.environ["DJ_MAIN_HOST"],
        len(candidates),
    )

    inserted = 0
    skipped_missing_mouse: List[str] = []
    skipped_existing = 0
    skipped_conflict = 0
    failed: List[str] = []

    with _main_database() as main_conn:
        Mouse = _table_on_conn(main_conn, mice.Mouse)
        Session = _table_on_conn(main_conn, exp.Session)
        ScoreSheet = _table_on_conn(main_conn, exp.SessionScoreSheet)
        for row in candidates:
            mouse_name = row.get("mouse_name")
            if not (Mouse & {"mouse_name": mouse_name}):
                skipped_missing_mouse.append(mouse_name or "?")
                continue

            status, main_row = _prepare_session_row_for_main(
                row, log=log, conn=main_conn
            )
            if status == "exists":
                skipped_existing += 1
                continue
            if status == "conflict" or main_row is None:
                skipped_conflict += 1
                continue

            local_pk = _session_primary_key(row)
            try:
                Session.insert1(main_row)
                inserted += 1
                sheet_row = sheets_by_local_pk.get(_pk_tuple(local_pk))
                if sheet_row is not None:
                    main_sheet = dict(sheet_row)
                    main_sheet["day"] = main_row["day"]
                    sheet_key = _session_primary_key(main_sheet)
                    if not (ScoreSheet & sheet_key):
                        ScoreSheet.insert1(main_sheet)
                        inserted += 1
            except Exception as err:
                failed.append(
                    f"{mouse_name} doe={_doe_str(row.get('doe'))} "
                    f"attempt={row.get('attempt')}: {err}"
                )

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
        log.info(
            "Skipped %d session(s) already present on main (same mouse/doe/attempt).",
            skipped_existing,
        )
    if skipped_conflict:
        log.warning(
            "Skipped %d session(s) due to day/PK conflicts on main "
            "(see warnings above).",
            skipped_conflict,
        )
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
