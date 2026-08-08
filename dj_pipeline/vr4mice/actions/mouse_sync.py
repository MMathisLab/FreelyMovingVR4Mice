"""Mouse registry helpers: stubs for local ingest, incomplete-mouse warnings, sync_exp, cleanup.

Parent → local mice registry sync is host-side mysqldump (``make -f mysql.mk
sync-mice-from-main``), not DataJoint dual-connect.
"""

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
    "make -f mysql.mk sync-mice-from-main  # host; optional MOUSE=Name1,Name2; "
    "set DJ_MAIN_HOST (and optionally DJ_MAIN_USER/DJ_MAIN_PWD)"
)
SYNC_EXP_COMMAND = (
    "python run_base.py sync_exp  # optional; DJ_MAIN_HOST + write on main exp; "
    "local (non-collab) sessions only"
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
    """
    Live host:port for the current DataJoint connection.

    Prefer MySQL ``@@port`` over ``conn_info`` / config — DJ2 may leave the
    TCP session on the previous port after ``reset=True`` while config already
    shows the new port.
    """
    conn = dj.conn()
    info = getattr(conn, "conn_info", None) or {}
    host = info.get("host") or dj.config["database.host"]
    live_port = _mysql_port(conn)
    if live_port is not None:
        host_only, _ = _endpoint_from_config(host, live_port)
        return host_only, live_port
    port = info.get("port") or dj.config["database.port"]
    return _endpoint_from_config(host, port)


def _rebind_schema_connection(conn) -> None:
    """
    Point base ``mice`` (and related) schemas at ``conn``.

    ``dj.Schema`` keeps the Connection from first import/connect. After
    ``dj.conn(reset=True)`` to main (``sync_exp``), tables can still query the
    old local conn unless we rebind.
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


def _mysql_connection_id(conn) -> Optional[int]:
    """MySQL ``CONNECTION_ID()`` for a live session, or None."""
    if conn is None:
        return None
    try:
        return int(conn.query("SELECT CONNECTION_ID()").fetchone()[0])
    except Exception:
        return None


def _ensure_schemas_on_connection(
    conn,
    *,
    expected_ep: Tuple[str, int],
    forbidden_connection_id: Optional[int] = None,
    label: str = "connection",
    log=None,
) -> None:
    """
    Rebind mice/exp schemas to ``conn`` and abort if still on another session.

    DJ2 leaves ``schema.connection`` on the previous MySQL session after
    ``dj.conn(reset=True)``. Comparing ``CONNECTION_ID()`` catches that even
    when host/port look plausible.
    """
    log = log or logger
    if conn is None:
        raise RuntimeError("%s: no DataJoint connection" % label)

    _rebind_schema_connection(conn)
    active = _active_endpoint()
    if active != expected_ep:
        raise RuntimeError(
            "%s: dj.conn() is %s:%s, expected %s:%s"
            % (label, active[0], active[1], expected_ep[0], expected_ep[1])
        )

    conn_id = _mysql_connection_id(conn)
    conn_port = _mysql_port(conn)
    if conn_id is None:
        raise RuntimeError("%s: could not read CONNECTION_ID() from dj.conn()" % label)
    if forbidden_connection_id is not None and conn_id == forbidden_connection_id:
        raise RuntimeError(
            "%s: dj.conn() still on previous MySQL session CONNECTION_ID=%s"
            % (label, conn_id)
        )
    if conn_port is not None and conn_port != expected_ep[1]:
        raise RuntimeError(
            "%s: dj.conn() @@port=%s, expected %s"
            % (label, conn_port, expected_ep[1])
        )

    schema_conn = getattr(getattr(mice, "schema", None), "connection", None)
    schema_id = _mysql_connection_id(schema_conn)
    if schema_id != conn_id:
        log.warning(
            "%s: mice.schema CONNECTION_ID=%s != dj.conn()=%s — rebinding again",
            label,
            schema_id,
            conn_id,
        )
        _rebind_schema_connection(conn)
        schema_conn = getattr(getattr(mice, "schema", None), "connection", None)
        schema_id = _mysql_connection_id(schema_conn)

    if schema_id != conn_id:
        raise RuntimeError(
            "%s: mice.schema still on CONNECTION_ID=%s after rebind; "
            "dj.conn() is %s (forbidden/previous session was %s). "
            "Refusing to continue — would read/write the wrong DB."
            % (label, schema_id, conn_id, forbidden_connection_id)
        )
    if (
        forbidden_connection_id is not None
        and schema_id == forbidden_connection_id
    ):
        raise RuntimeError(
            "%s: mice.schema still on previous MySQL session CONNECTION_ID=%s"
            % (label, schema_id)
        )

    exp_schema = getattr(exp, "schema", None)
    if exp_schema is not None:
        exp_id = _mysql_connection_id(getattr(exp_schema, "connection", None))
        if exp_id is not None and exp_id != conn_id:
            _rebind_schema_connection(conn)
            exp_id = _mysql_connection_id(
                getattr(getattr(exp, "schema", None), "connection", None)
            )
            if exp_id != conn_id:
                raise RuntimeError(
                    "%s: exp.schema still on CONNECTION_ID=%s; dj.conn() is %s"
                    % (label, exp_id, conn_id)
                )

    log.info(
        "%s OK: endpoint %s:%s CONNECTION_ID=%s (schemas rebound)",
        label,
        expected_ep[0],
        expected_ep[1],
        conn_id,
    )


def _full_table_name(table_cls) -> Optional[str]:
    full = getattr(table_cls, "full_table_name", None)
    if isinstance(full, str) and "`" in full:
        return full
    try:
        inst_full = getattr(table_cls(), "full_table_name", None)
    except Exception:
        return None
    if isinstance(inst_full, str) and "`" in inst_full:
        return inst_full
    return None




def _table_on_conn(conn, table_cls, *, full_name: Optional[str] = None):
    """
    Return a queryable table bound to ``conn``.

    When ``conn`` is set, uses ``dj.FreeTable`` so we never accidentally read
    through the schema's imported local Connection. Falls back to
    ``table_cls()`` when ``conn`` is None or ``full_table_name`` is unavailable
    (unit-test mocks).
    """
    if conn is None:
        return table_cls()
    full = full_name or _full_table_name(table_cls)
    if not full:
        return table_cls()
    return dj.FreeTable(conn, full)




def _close_dj_connection() -> None:
    """Drop the current DJ Connection so the next ``conn(reset=True)`` reconnects."""
    try:
        prev = dj.conn()
    except Exception:
        prev = None
    if prev is not None:
        for meth in ("close", "disconnect"):
            fn = getattr(prev, meth, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
    # DJ keeps a singleton on the ``conn`` callable / Connection class.
    for holder in (getattr(dj, "conn", None), getattr(dj, "Connection", None)):
        if holder is None:
            continue
        for attr in ("connection", "_connection", "_conn"):
            if not hasattr(holder, attr):
                continue
            try:
                setattr(holder, attr, None)
            except Exception:
                try:
                    object.__setattr__(holder, attr, None)
                except Exception:
                    pass


def _dj_connect(*, host: str, port: int, user: str, password: str, disable_ssl: bool):
    """
    Connect with explicit host/port and verify the live MySQL ``@@port``.

    Same IP with different ports (local :3309 vs main :3306) is common. DJ2
    ``conn(reset=True)`` often keeps the previous TCP session unless we close
    it first; ``database.host=host:port`` also helps some stacks.
    """
    host_only, _ = _endpoint_from_config(host, port)
    port = int(port)
    host_port = "%s:%s" % (host_only, port)

    dj.config["database.host"] = host_port
    dj.config["database.port"] = port
    dj.config["database.user"] = user
    dj.config["database.password"] = password

    _close_dj_connection()

    def _call():
        try:
            return dj.conn(
                host=host_port,
                user=user,
                password=password,
                port=port,
                reset=True,
            )
        except TypeError:
            try:
                return dj.conn(
                    host=host_only,
                    user=user,
                    password=password,
                    port=port,
                    reset=True,
                )
            except TypeError:
                return dj.conn(reset=True)

    if disable_ssl:
        with _pymysql_disable_ssl():
            conn = _call()
    else:
        # Lab MySQL is often plain TCP on both local and main — try SSL-off
        # first so restore does not silently keep the previous session.
        try:
            with _pymysql_disable_ssl():
                conn = _call()
        except Exception:
            conn = _call()

    live = _mysql_port(conn)
    if live is not None and live != port:
        raise RuntimeError(
            "Requested MySQL %s but session @@port=%s (DJ did not switch ports). "
            "Close/reconnect failed."
            % (host_port, live)
        )
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
        main_conn_id = _mysql_connection_id(conn)
        schema_conn = getattr(getattr(mice, "schema", None), "connection", None)
        schema_port = _mysql_port(schema_conn)
        schema_conn_id = _mysql_connection_id(schema_conn)
        try:
            sql_count = conn.query("SELECT COUNT(*) FROM mice.mouse").fetchone()[0]
        except Exception as err:
            sql_count = "err:%s" % err
        logger.info(
            "Main MySQL session: conn @@port=%s CONNECTION_ID=%s "
            "schema @@port=%s CONNECTION_ID=%s SQL mice.mouse COUNT(*)=%s",
            conn_port,
            main_conn_id,
            schema_port,
            schema_conn_id,
            sql_count,
        )
        if schema_conn_id is not None and schema_conn_id != main_conn_id:
            logger.warning(
                "mice.schema CONNECTION_ID=%s != main conn %s — "
                "fetches use FreeTable on main conn (DJ2 sticky schema).",
                schema_conn_id,
                main_conn_id,
            )
    except Exception:
        traceback.print_exc()
        raise
    main_conn_id = _mysql_connection_id(conn)
    try:
        yield conn
    finally:
        for key, value in saved.items():
            dj.config[key] = value
        # Restore local and hard-fail if schemas still point at the main session.
        loc_host, loc_port = local_ep
        loc_user = saved.get("database.user")
        loc_password = saved.get("database.password")
        if loc_user is None or loc_password is None:
            raise RuntimeError(
                "Cannot restore local DB connection: missing saved database.user/password"
            )
        logger.info(
            "Restoring local DB connection %s:%s (leaving main CONNECTION_ID=%s)",
            loc_host,
            loc_port,
            main_conn_id,
        )
        loc_conn = _dj_connect(
            host=loc_host,
            port=loc_port,
            user=loc_user,
            password=loc_password,
            disable_ssl=True,
        )
        _ensure_schemas_on_connection(
            loc_conn,
            expected_ep=local_ep,
            forbidden_connection_id=main_conn_id,
            label="local restore after main",
        )




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
