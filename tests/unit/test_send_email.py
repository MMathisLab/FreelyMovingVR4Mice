"""
Unit tests for send_email.py

Tests the email() function used to send summary plot notifications.
All SMTP and filesystem interactions are mocked.
"""

import configparser
from unittest.mock import MagicMock, mock_open, patch

import pytest


SAMPLE_KEY = {"mouse_name": "Flamingo", "day": "2026-02-05", "attempt": 1}
FROM_ADDR = "pipeline@example.com"
EMAIL_PASSWORD = "test_password"


@pytest.fixture
def mock_config():
    """Mock configparser to return test email credentials."""
    with patch("base_actions.send_email.config") as mock_cfg:
        mock_cfg.get.side_effect = lambda section, key: {
            ("Email", "password"): EMAIL_PASSWORD,
            ("Email", "email"): FROM_ADDR,
        }[(section, key)]
        yield mock_cfg


@pytest.fixture
def mock_smtp():
    """Mock SMTP server."""
    with patch("base_actions.send_email.smtplib.SMTP") as mock_cls:
        server = MagicMock()
        mock_cls.return_value = server
        yield server


class TestEmailSuccess:
    """Tests for successful email sending."""

    def test_sends_summary_email(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        with patch("base_actions.send_email.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"fake_image_data")):
            email(SAMPLE_KEY, "recipient@example.com", "plot.png", message=None)

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with(FROM_ADDR, EMAIL_PASSWORD)
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.quit.assert_called_once()

        _, args, _ = mock_smtp.sendmail.mock_calls[0]
        assert args[0] == FROM_ADDR
        assert "recipient@example.com" in args[1]

    def test_sends_error_email(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        email(
            SAMPLE_KEY, "recipient@example.com", None,
            message="Pipeline failed", error=True,
        )

        mock_smtp.sendmail.assert_called_once()
        sent_text = mock_smtp.sendmail.call_args[0][2]
        assert "pipeline failed" in sent_text.lower() or "Failed" in sent_text

    def test_default_email_uses_from_address(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        with patch("base_actions.send_email.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"fake_image_data")):
            email(SAMPLE_KEY, "default", "plot.png", message=None)

        _, args, _ = mock_smtp.sendmail.mock_calls[0]
        # When email="default", recipient list should just be [fromaddr]
        assert args[1] == [FROM_ADDR]

    def test_recipient_list(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        with patch("base_actions.send_email.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"fake_image_data")):
            email(
                SAMPLE_KEY,
                ["alice@example.com", "bob@example.com"],
                "plot.png",
                message=None,
            )

        _, args, _ = mock_smtp.sendmail.mock_calls[0]
        assert FROM_ADDR in args[1]
        assert "alice@example.com" in args[1]
        assert "bob@example.com" in args[1]


class TestEmailSubject:
    """Tests for email subject line formatting."""

    def test_success_subject(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        with patch("base_actions.send_email.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=b"fake_image_data")):
            email(SAMPLE_KEY, FROM_ADDR, "plot.png", message=None)

        sent_text = mock_smtp.sendmail.call_args[0][2]
        assert "Flamingo" in sent_text
        assert "2026-02-05" in sent_text

    def test_error_subject(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        email(SAMPLE_KEY, FROM_ADDR, None, message="Error msg", error=True)

        sent_text = mock_smtp.sendmail.call_args[0][2]
        assert "failed" in sent_text.lower()
        assert "Flamingo" in sent_text


class TestEmailEdgeCases:
    """Tests for error handling and edge cases."""

    def test_missing_config_returns_early(self):
        from base_actions.send_email import email

        with patch("base_actions.send_email.config") as mock_cfg:
            mock_cfg.get.side_effect = configparser.NoSectionError("Email")
            with patch("base_actions.send_email.smtplib.SMTP") as smtp_cls:
                email(SAMPLE_KEY, "test@example.com", "plot.png", message=None)
                smtp_cls.assert_not_called()

    def test_missing_file_logs_warning(self, mock_config, mock_smtp):
        from base_actions.send_email import email

        with patch("base_actions.send_email.os.path.exists", return_value=False):
            email(SAMPLE_KEY, FROM_ADDR, "missing.png", message=None)

        # Should still send the email (just without attachment)
        mock_smtp.sendmail.assert_called_once()
