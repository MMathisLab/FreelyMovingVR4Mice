"""Schema for tracking and sending summary plot notification emails."""

import os
import re
from datetime import date, datetime
from typing import List, Optional

import datajoint as dj
from base_actions.send_email import email

from vr4mice.schema import base_analysis
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "summary_emails"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()

_SESSION_DATE_RE = re.compile(r"(?:(?P<mouse>[^_]+)_)?(?P<day>\d{4}-\d{2}-\d{2})")


def summary_email_recipient_names() -> List[str]:
    """Experimenter names from VR4MICE_EMAIL_RECIPIENTS (comma-separated, set in .env)."""
    raw = os.getenv("VR4MICE_EMAIL_RECIPIENTS", "").strip()
    if not raw:
        return []
    return [name.strip() for name in raw.split(",") if name.strip()]


@schema
class SummaryPlotEmail(dj.Manual):
    """Tracks summary plot notification emails sent per session."""

    definition = """
    -> base_analysis.SummaryPlots
    ---
    sent_at: datetime
    recipients: varchar(1024)
    email_type: varchar(32)
    send_error=NULL: varchar(512)
    """


def session_date_from_dataset(dataset: str) -> Optional[date]:
    """Return the session date encoded in a dataset name, if present."""
    match = _SESSION_DATE_RE.search(dataset)
    if not match:
        return None
    return datetime.strptime(match.group("day"), "%Y-%m-%d").date()


def summary_email_since() -> Optional[date]:
    """
    Cutoff date for automatic summary emails.

    Set VR4MICE_EMAIL_SINCE=YYYY-MM-DD on the rig so only new sessions are
    emailed; older sessions with existing SummaryPlots rows are ignored.
    """
    raw = os.getenv("VR4MICE_EMAIL_SINCE", "").strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


def summary_email_enabled() -> bool:
    return os.environ.get("EMAIL", "false").lower() in ["true", "1", "yes"]


def summary_email_allowed(dataset: str, *, logger=None) -> bool:
    """Return True when this dataset is eligible for a summary email."""
    log = logger or globals()["logger"]
    since = summary_email_since()
    if since is None:
        log.debug(
            "VR4MICE_EMAIL_SINCE not set; skipping summary email for %s",
            dataset,
        )
        return False

    session_day = session_date_from_dataset(dataset)
    if session_day is None:
        log.warning(
            "Could not parse session date from %s; summary email skipped",
            dataset,
        )
        return False

    if session_day < since:
        log.debug(
            "Session %s (%s) is before VR4MICE_EMAIL_SINCE=%s; email skipped",
            dataset,
            session_day.isoformat(),
            since.isoformat(),
        )
        return False

    return True


def build_summary_email_key(dataset: str) -> Optional[dict]:
    """Build the key dict expected by base_actions.send_email.email."""
    parsed = base_analysis.SummaryPlots().parse_dataset(dataset)
    if not parsed or not parsed.get("mouse_name"):
        return None
    return {
        "dataset": dataset,
        "mouse_name": parsed["mouse_name"],
        "day": parsed["day"],
        "attempt": parsed["attempt"],
    }


def resolve_summary_email_recipients(dataset: str) -> List[str]:
    """Resolve recipient addresses for a summary plot email."""
    from base_schemas.schemas import exp

    key = {"dataset": dataset}
    toaddr: List[str] = []

    recipient_names = summary_email_recipient_names()

    for name in recipient_names:
        rows = (exp.Experimenter & {"experimenter_name": name}).fetch("mail")
        if rows and rows[0]:
            toaddr.append(rows[0])

    try:
        if len(exp.Session() & key) > 0:
            user = (exp.Session() & key).fetch("experimenter_name", as_dict=True)[0]
            if user:
                rows = (exp.Experimenter & user).fetch("mail")
                if rows and rows[0] and rows[0] not in toaddr:
                    toaddr.append(rows[0])
    except dj.DataJointError as err:
        logger.warning("Error fetching experimenter email for %s: %s", dataset, err)

    return toaddr


def record_summary_plot_email(
    dataset: str,
    *,
    recipients: List[str],
    email_type: str,
    send_error: Optional[str] = None,
) -> None:
    """Record the email outcome for a dataset without overwriting a prior success."""
    key = {"dataset": dataset}
    row = (SummaryPlotEmail() & key).fetch(as_dict=True)
    data = {
        **key,
        "sent_at": datetime.utcnow(),
        "recipients": ", ".join(recipients),
        "email_type": email_type,
        "send_error": send_error,
    }
    if row:
        if row[0].get("send_error") is None:
            return
        SummaryPlotEmail.update1(data)
        return
    SummaryPlotEmail.insert1(data, skip_duplicates=True)


def send_and_record_summary_email(
    dataset: str,
    email_key: dict,
    plot_path: str,
    *,
    err_msg: Optional[str] = None,
    logger=None,
) -> bool:
    """Send a summary or error email and record the outcome in SummaryPlotEmail."""
    log = logger or globals()["logger"]
    if not summary_email_allowed(dataset, logger=log):
        return False

    toaddr = resolve_summary_email_recipients(dataset)
    if not toaddr:
        message = "No recipient addresses resolved"
        log.warning("Summary email for %s skipped: %s", dataset, message)
        record_summary_plot_email(
            dataset,
            recipients=[],
            email_type="error",
            send_error=message,
        )
        return False

    email_type = "summary" if err_msg is None else "error"
    log.info("Sending %s email for %s to %s", email_type, dataset, toaddr)
    try:
        email(
            email_key,
            toaddr,
            plot_path,
            message=err_msg,
            error=err_msg is not None,
        )
    except Exception as err:
        log.warning("Failed to send %s email for %s: %s", email_type, dataset, err)
        record_summary_plot_email(
            dataset,
            recipients=toaddr,
            email_type=email_type,
            send_error=str(err),
        )
        return False

    record_summary_plot_email(
        dataset,
        recipients=toaddr,
        email_type=email_type,
        send_error=None,
    )
    return True


def pending_summary_email_keys(*, since: Optional[date] = None) -> List[dict]:
    """
    Return SummaryPlots rows that still need a successful summary email.

    Includes sessions with no tracking row and sessions whose last send failed.
    """
    since = since if since is not None else summary_email_since()
    if since is None:
        return []

    try:
        sent_ok = {
            row["dataset"]
            for row in (SummaryPlotEmail() & "send_error IS NULL").fetch(
                "dataset", as_dict=True
            )
        }
    except dj.DataJointError as err:
        logger.debug("SummaryPlotEmail not available yet: %s", err)
        sent_ok = set()

    pending: List[dict] = []
    for row in base_analysis.SummaryPlots().fetch("dataset", "filename", as_dict=True):
        dataset = row["dataset"]
        if dataset in sent_ok:
            continue
        session_day = session_date_from_dataset(dataset)
        if session_day is None or session_day < since:
            continue
        pending.append(row)
    return pending


def confirm_send_summary_email(dataset: str, recipients: List[str]) -> bool:
    """Ask whether to send a summary email for one dataset (interactive runs)."""
    if recipients:
        recipient_text = ", ".join(recipients)
    else:
        recipient_text = "(no recipients resolved)"
    while True:
        answer = (
            input(f"Send summary email for {dataset} to {recipient_text}? [y/N]: ")
            .strip()
            .lower()
        )
        if answer in ("", "n", "no"):
            return False
        if answer in ("y", "yes"):
            return True
        print("Please answer y or n.")


def send_pending_summary_emails(*, logger=None, prompt: bool = False) -> int:
    """Send summary emails for eligible new sessions missing a successful send.

    When ``prompt`` is True (``run.py summary``), ask before each send.
    Cron runs leave ``prompt`` False and send all eligible pending sessions.
    """
    log = logger or globals()["logger"]
    if not summary_email_enabled():
        log.debug("EMAIL disabled; skipping pending summary emails")
        return 0

    pending = pending_summary_email_keys()
    log.info("SummaryPlotEmail: %d pending sends", len(pending))
    sent = 0
    for row in pending:
        dataset = row["dataset"]
        email_key = build_summary_email_key(dataset)
        if not email_key:
            log.warning(
                "Skipping summary email for %s: could not parse metadata", dataset
            )
            continue
        if prompt and not confirm_send_summary_email(
            dataset, resolve_summary_email_recipients(dataset)
        ):
            log.info("Skipped summary email for %s (user declined)", dataset)
            continue
        if send_and_record_summary_email(
            dataset,
            email_key,
            row["filename"],
            logger=log,
        ):
            sent += 1
    return sent


def insert_send_email(key, filename, err_msg):
    """Backward-compatible wrapper; prefer send_and_record_summary_email."""
    dataset = key.get("dataset")
    if not dataset:
        logger.warning("insert_send_email called without dataset in key: %s", key)
        return
    send_and_record_summary_email(
        dataset,
        key,
        filename,
        err_msg=err_msg,
        logger=logger,
    )
