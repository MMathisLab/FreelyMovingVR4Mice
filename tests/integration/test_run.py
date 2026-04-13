"""
Integration tests for run.py

Tests the utility functions and argument parser used in the CLI entry point.
These tests require the database configuration to be available for imports.
"""

import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add dj_pipeline to path for imports
TESTS_DIR = Path(__file__).parent.parent
DJ_PIPELINE_PATH = TESTS_DIR.parent / "dj_pipeline"
if str(DJ_PIPELINE_PATH) not in sys.path:
    sys.path.insert(0, str(DJ_PIPELINE_PATH))


# ==============================================================================
# Import run module (requires dj_config fixture for DB connection)
# ==============================================================================

@pytest.fixture
def run_module(dj_config, mysql_container):
    """Import run module after DB is configured."""
    import datajoint as dj

    # Set DJ env vars - LoginUser reads these at class definition time
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    os.environ["DJ_HOST"] = f"{host}:{port}"
    os.environ["DJ_USER"] = "root"
    os.environ["DJ_PWD"] = "simple"

    # Clear cached imports that may have failed or used wrong config
    modules_to_clear = [
        "run",
        "base_actions",
        "base_actions.connect",
        "base_actions.utils",
        "base_actions.utils.login",
    ]
    for mod in modules_to_clear:
        if mod in sys.modules:
            del sys.modules[mod]

    import run
    return run


# ==============================================================================
# Tests for create_folder_if_not_exist
# ==============================================================================

class TestCreateFolderIfNotExist:
    """Tests for create_folder_if_not_exist function."""

    def test_creates_folder_when_not_exists(self, run_module, tmp_path):
        """Should create folder when it doesn't exist."""
        new_folder = tmp_path / "new_folder"

        assert not new_folder.exists()
        run_module.create_folder_if_not_exist(str(new_folder))
        assert new_folder.exists()
        assert new_folder.is_dir()

    def test_handles_existing_folder(self, run_module, tmp_path):
        """Should handle existing folder gracefully."""
        existing_folder = tmp_path / "existing"
        existing_folder.mkdir()

        # Should not raise
        run_module.create_folder_if_not_exist(str(existing_folder))

        # Folder should still exist
        assert existing_folder.exists()

    def test_creates_nested_folders(self, run_module, tmp_path):
        """Should create nested folder structure."""
        nested_folder = tmp_path / "level1" / "level2" / "level3"

        assert not nested_folder.exists()
        run_module.create_folder_if_not_exist(str(nested_folder))
        assert nested_folder.exists()

    def test_exits_on_permission_error(self, run_module):
        """Should exit with code 1 on OSError."""
        with patch("os.makedirs", side_effect=OSError("Permission denied")):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    run_module.create_folder_if_not_exist("/some/path")

                assert exc_info.value.code == 1


# ==============================================================================
# Tests for check_folder_existence
# ==============================================================================

class TestCheckFolderExistence:
    """Tests for check_folder_existence function."""

    def test_passes_when_folder_exists(self, run_module, tmp_path):
        """Should pass through when folder exists."""
        existing_folder = tmp_path / "existing"
        existing_folder.mkdir()

        # Should not raise
        run_module.check_folder_existence(str(existing_folder))

    def test_exits_when_folder_missing(self, run_module, tmp_path):
        """Should exit with code 1 when folder doesn't exist."""
        missing_folder = tmp_path / "nonexistent"

        with pytest.raises(SystemExit) as exc_info:
            run_module.check_folder_existence(str(missing_folder))

        assert exc_info.value.code == 1


# ==============================================================================
# Tests for argument parser
# ==============================================================================

class TestArgumentParser:
    """Tests for CLI argument parsing.

    Note: These tests don't need the run_module fixture since we're testing
    argparse directly, but we include dj_config to ensure consistent test
    environment.
    """

    @pytest.fixture
    def parser(self, dj_config):
        """Create the argument parser used in run.py."""
        parser = argparse.ArgumentParser(
            description="Script to handle AWS or local execution."
        )
        parser.add_argument(
            "--aws", action="store_true", help="Enable AWS-specific execution."
        )
        parser.add_argument(
            "mode",
            choices=[
                "connect",
                "populate",
                "analysis",
                "summary",
                "fetch",
                "dlc",
                "interp",
                "latency",
                "sync_days",
            ],
            help="Mode to execute",
        )
        return parser

    @pytest.mark.parametrize("mode", [
        "connect",
        "populate",
        "analysis",
        "summary",
        "fetch",
        "dlc",
        "interp",
        "latency",
        "sync_days",
    ])
    def test_accepts_valid_modes(self, parser, mode):
        """Should accept all valid mode arguments."""
        args = parser.parse_args([mode])
        assert args.mode == mode
        assert args.aws is False

    def test_aws_flag_defaults_false(self, parser):
        """--aws flag should default to False."""
        args = parser.parse_args(["connect"])
        assert args.aws is False

    def test_aws_flag_sets_true(self, parser):
        """--aws flag should set to True when provided."""
        args = parser.parse_args(["--aws", "populate"])
        assert args.aws is True
        assert args.mode == "populate"

    def test_aws_flag_works_before_mode(self, parser):
        """--aws flag should work when placed before mode."""
        args = parser.parse_args(["--aws", "analysis"])
        assert args.aws is True
        assert args.mode == "analysis"

    def test_rejects_invalid_mode(self, parser):
        """Should reject invalid mode arguments."""
        with pytest.raises(SystemExit):
            parser.parse_args(["invalid_mode"])

    def test_requires_mode_argument(self, parser):
        """Should require mode argument."""
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_rejects_unknown_flags(self, parser):
        """Should reject unknown flags."""
        with pytest.raises(SystemExit):
            parser.parse_args(["--unknown", "connect"])

    def test_help_flag_exits(self, parser):
        """--help flag should exit."""
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0
