"""Unit tests for summary email helpers."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DJ_PIPELINE = PROJECT_ROOT / "dj_pipeline"


def _identity_schema_decorator(_name, _locals):
    def decorator(cls):
        return cls

    return decorator


@pytest.fixture(scope="module")
def summary_emails():
    """Load summary_emails without the vr4mice.schema mock from tests/conftest.py."""
    dj_path = str(DJ_PIPELINE)
    if dj_path not in sys.path:
        sys.path.insert(0, dj_path)

    mock_analysis = MagicMock()
    mock_logger = MagicMock()
    mock_logger.Logger.get_logger.return_value = MagicMock()

    stubs = {
        "datajoint": MagicMock(
            Manual=type("Manual", (), {}),
            DataJointError=Exception,
        ),
        "base_actions.send_email": MagicMock(),
        "vr4mice.schema.base_analysis": mock_analysis,
        "vr4mice.utils.logger": mock_logger,
        "vr4mice.utils.schema_config": MagicMock(get_schema=_identity_schema_decorator),
    }

    module_path = DJ_PIPELINE / "vr4mice" / "schema" / "summary_emails.py"
    spec = importlib.util.spec_from_file_location(
        "_summary_emails_unit_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs, clear=False):
        spec.loader.exec_module(module)
    return module


class TestConfirmSendSummaryEmail:
    def test_defaults_to_no(self, summary_emails):
        with patch("builtins.input", return_value=""):
            assert not summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )

    def test_accepts_yes(self, summary_emails):
        with patch("builtins.input", return_value="y"):
            assert summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )

    def test_retries_invalid_answer(self, summary_emails):
        with patch("builtins.input", side_effect=["maybe", "yes"]):
            assert summary_emails.confirm_send_summary_email(
                "Whale_2026-07-08_1", ["a@example.com"]
            )


class TestSendPendingSummaryEmails:
    def test_prompt_skips_declined_send(self, summary_emails):
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

    def test_no_prompt_sends_without_confirmation(self, summary_emails):
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


class TestRecordSummaryPlotEmail:
    def test_does_not_overwrite_successful_row(self, summary_emails):
        mock_cls = MagicMock()
        mock_query = MagicMock()
        mock_cls.return_value.__and__.return_value = mock_query
        mock_query.fetch.return_value = [{"send_error": None}]

        with patch.object(summary_emails, "SummaryPlotEmail", mock_cls):
            summary_emails.record_summary_plot_email(
                "Whale_2026-07-08_1",
                recipients=["a@example.com"],
                email_type="summary",
                send_error=None,
            )

        mock_cls.update1.assert_not_called()
        mock_cls.insert1.assert_not_called()

    def test_updates_failed_row_on_retry(self, summary_emails):
        mock_cls = MagicMock()
        mock_query = MagicMock()
        mock_cls.return_value.__and__.return_value = mock_query
        mock_query.fetch.return_value = [{"send_error": "smtp failed"}]

        with patch.object(summary_emails, "SummaryPlotEmail", mock_cls):
            summary_emails.record_summary_plot_email(
                "Whale_2026-07-08_1",
                recipients=["a@example.com"],
                email_type="summary",
                send_error=None,
            )

        mock_cls.update1.assert_called_once()
        mock_cls.insert1.assert_not_called()
