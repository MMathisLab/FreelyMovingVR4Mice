"""Unit tests for summary email helpers."""

from unittest.mock import patch

from vr4mice.schema import summary_emails


class TestConfirmSendSummaryEmail:
    def test_defaults_to_no(self):
        with patch("builtins.input", return_value=""):
            assert not summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )

    def test_accepts_yes(self):
        with patch("builtins.input", return_value="y"):
            assert summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )

    def test_retries_invalid_answer(self):
        with patch("builtins.input", side_effect=["maybe", "yes"]):
            assert summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )


class TestSendPendingSummaryEmails:
    def test_prompt_skips_declined_send(self):
        pending = [{"dataset": "Whale_2026-07-08_1", "filename": "/tmp/plot.png"}]
        with patch.object(
            summary_emails, "summary_email_enabled", return_value=True
        ), patch.object(
            summary_emails, "pending_summary_email_keys", return_value=pending
        ), patch.object(
            summary_emails,
            "build_summary_email_key",
            return_value={"dataset": "Whale_2026-07-08_1"},
        ), patch.object(
            summary_emails, "resolve_summary_email_recipients", return_value=["a@x.com"]
        ), patch.object(
            summary_emails, "confirm_send_summary_email", return_value=False
        ) as confirm, patch.object(
            summary_emails, "send_and_record_summary_email"
        ) as send:
            sent = summary_emails.send_pending_summary_emails(prompt=True)

        confirm.assert_called_once_with("Whale_2026-07-08_1", ["a@x.com"])
        send.assert_not_called()
        assert sent == 0

    def test_no_prompt_sends_without_confirmation(self):
        pending = [{"dataset": "Whale_2026-07-08_1", "filename": "/tmp/plot.png"}]
        with patch.object(
            summary_emails, "summary_email_enabled", return_value=True
        ), patch.object(
            summary_emails, "pending_summary_email_keys", return_value=pending
        ), patch.object(
            summary_emails,
            "build_summary_email_key",
            return_value={"dataset": "Whale_2026-07-08_1"},
        ), patch.object(
            summary_emails, "confirm_send_summary_email"
        ) as confirm, patch.object(
            summary_emails, "send_and_record_summary_email", return_value=True
        ) as send:
            sent = summary_emails.send_pending_summary_emails(prompt=False)

        confirm.assert_not_called()
        send.assert_called_once()
        assert sent == 1
