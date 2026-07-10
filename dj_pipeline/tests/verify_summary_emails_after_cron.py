"""Post-cron CI check: summary emails are sent/recorded outside SummaryPlots.populate()."""

import os
import subprocess
import sys
import warnings
from pathlib import Path
from unittest.mock import patch

# Headless matplotlib before any schema import pulls in summary_dj.
os.environ.setdefault("MPLBACKEND", "Agg")

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
os.chdir(APP_ROOT)

warnings.filterwarnings("ignore", message="No datajoint.json found")


def _log(step: str) -> None:
    print(f"verify_summary_emails_after_cron: {step}", file=sys.stderr, flush=True)


def _fail(message: str, *, exc: BaseException | None = None) -> int:
    print(f"VERIFY_SUMMARY_EMAILS_FAILED: {message}", file=sys.stderr, flush=True)
    if exc is not None:
        print(f"  {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
    return 1


def _require_env(*names: str) -> bool:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        _fail(f"missing required env vars: {', '.join(missing)}")
        return False
    return True


def _mysql_scalar(query: str) -> int:
    result = subprocess.run(
        [
            "mysql",
            "-h",
            os.environ["DJ_HOST"],
            "-P",
            os.environ["DJ_PORT"],
            "-u",
            os.environ["DJ_USER"],
            f"-p{os.environ['DJ_PWD']}",
            "-N",
            "-e",
            query,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def main() -> int:
    _log("starting")
    if not _require_env("DJ_HOST", "DJ_PORT", "DJ_USER", "DJ_PWD"):
        return 1

    try:
        from base_actions.connect import connect
        from vr4mice.utils.bootstrap import configure_runtime

        configure_runtime()
        _log("connecting to database (tag='' — must match cron_scenario.py)")
        connect(tag="")

        _log("preflight mysql")
        summary_plot_count = _mysql_scalar(
            "SELECT COUNT(*) FROM base_analysis.__summary_plots"
        )
        if summary_plot_count < 1:
            return _fail(
                "expected SummaryPlots rows after cron "
                f"(base_analysis.__summary_plots), got {summary_plot_count}. "
                "Cron may have failed before SummaryPlots.populate."
            )

        _log("importing schemas")
        from vr4mice.schema import base_analysis, summary_emails

        _log("checking SummaryPlots via DataJoint")
        dj_summary_plot_count = len(base_analysis.SummaryPlots())
        if dj_summary_plot_count < 1:
            return _fail(
                "SummaryPlots query returned no rows via DataJoint "
                f"(mysql count={summary_plot_count}). "
                "Check database prefix / schema name matches cron."
            )

        os.environ["EMAIL"] = "true"
        os.environ["VR4MICE_EMAIL_SINCE"] = "2026-01-01"
        os.environ["VR4MICE_EMAIL_RECIPIENTS"] = "ci-test"

        _log("listing pending summary emails")
        pending = summary_emails.pending_summary_email_keys()
        if not pending:
            return _fail(
                "expected pending summary emails after cron "
                "(EMAIL was false during cron). "
                f"SummaryPlots={dj_summary_plot_count}, pending=0. "
                "Check VR4MICE_EMAIL_SINCE and dataset session dates."
            )

        _log(f"sending and recording mocked summary emails ({len(pending)} pending)")
        with patch("vr4mice.schema.summary_emails.email"), patch.object(
            summary_emails,
            "resolve_summary_email_recipients",
            return_value=["ci@example.com"],
        ):
            sent = summary_emails.send_pending_summary_emails(prompt=False)

        if sent < 1:
            return _fail(
                f"expected at least one summary email recorded, sent={sent}. "
                "Inspect summary_emails.__summary_plot_email for send_error rows."
            )

        _log("checking SummaryPlotEmail rows")
        ok_rows = (summary_emails.SummaryPlotEmail() & "send_error IS NULL").fetch(
            "dataset", "recipients", as_dict=True
        )
        if not ok_rows:
            email_count = _mysql_scalar(
                "SELECT COUNT(*) FROM summary_emails.__summary_plot_email "
                "WHERE send_error IS NULL"
            )
            failed_count = _mysql_scalar(
                "SELECT COUNT(*) FROM summary_emails.__summary_plot_email "
                "WHERE send_error IS NOT NULL"
            )
            return _fail(
                "expected a successful SummaryPlotEmail row "
                f"(mysql ok={email_count}, failed={failed_count})"
            )

        dataset = ok_rows[0]["dataset"]
        first_recipients = ok_rows[0]["recipients"]

        _log("resending to verify successful rows are not overwritten")
        with patch("vr4mice.schema.summary_emails.email"), patch.object(
            summary_emails,
            "resolve_summary_email_recipients",
            return_value=["ci@example.com"],
        ):
            summary_emails.send_pending_summary_emails(prompt=False)

        row = (summary_emails.SummaryPlotEmail() & {"dataset": dataset}).fetch(
            "recipients", as_dict=True
        )[0]
        if row["recipients"] != first_recipients:
            return _fail(
                "successful SummaryPlotEmail row was overwritten on resend "
                f"(was {first_recipients!r}, now {row['recipients']!r})"
            )

        if len(summary_emails.SummaryPlotEmail() & {"dataset": dataset}) != 1:
            return _fail("expected exactly one SummaryPlotEmail row per dataset")

        _log(
            f"ok ({summary_plot_count} plots, {sent} sent, dataset={dataset})",
        )
        return 0
    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        return _fail("unexpected exception during verification", exc=exc)


if __name__ == "__main__":
    sys.exit(main())
