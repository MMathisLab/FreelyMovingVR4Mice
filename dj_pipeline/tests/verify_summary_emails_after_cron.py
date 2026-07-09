"""Post-cron CI check: summary emails are sent/recorded outside SummaryPlots.populate()."""

import os
import sys
from unittest.mock import patch

from base_actions.connect import connect
from vr4mice.utils.bootstrap import configure_runtime


def main() -> int:
    configure_runtime()
    connect(tag="")

    from vr4mice.schema import base_analysis, summary_emails

    summary_plot_count = len(base_analysis.SummaryPlots())
    if summary_plot_count < 1:
        print(
            f"Expected SummaryPlots rows after cron, got {summary_plot_count}",
            file=sys.stderr,
        )
        return 1

    os.environ["EMAIL"] = "true"
    os.environ["VR4MICE_EMAIL_SINCE"] = "2026-01-01"
    os.environ["VR4MICE_EMAIL_RECIPIENTS"] = "ci-test"

    pending = summary_emails.pending_summary_email_keys()
    if not pending:
        print(
            "Expected pending summary emails after cron (EMAIL was false during cron)",
            file=sys.stderr,
        )
        return 1

    with patch("vr4mice.schema.summary_emails.email"), patch.object(
        summary_emails,
        "resolve_summary_email_recipients",
        return_value=["ci@example.com"],
    ):
        sent = summary_emails.send_pending_summary_emails(prompt=False)

    if sent < 1:
        print(
            f"Expected at least one summary email recorded, sent={sent}",
            file=sys.stderr,
        )
        return 1

    ok_rows = (summary_emails.SummaryPlotEmail() & "send_error IS NULL").fetch(
        "dataset", "recipients", as_dict=True
    )
    if not ok_rows:
        print("Expected a successful SummaryPlotEmail row", file=sys.stderr)
        return 1

    dataset = ok_rows[0]["dataset"]
    first_recipients = ok_rows[0]["recipients"]

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
        print(
            "Successful SummaryPlotEmail row was overwritten on resend", file=sys.stderr
        )
        return 1

    if len(summary_emails.SummaryPlotEmail() & {"dataset": dataset}) != 1:
        print("Expected exactly one SummaryPlotEmail row per dataset", file=sys.stderr)
        return 1

    print(
        "verify_summary_emails_after_cron: ok "
        f"({summary_plot_count} plots, {sent} sent, dataset={dataset})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise
