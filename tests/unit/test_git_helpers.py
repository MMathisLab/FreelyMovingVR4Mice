"""Unit tests for git_helpers.py."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock


def _import_git_helpers():
    """Import git_helpers from utils path used in unit tests."""
    import sys

    project_root = Path(__file__).resolve().parents[2]
    utils_path = project_root / "dj_pipeline" / "vr4mice" / "utils"
    if str(utils_path) not in sys.path:
        sys.path.insert(0, str(utils_path))
    return importlib.import_module("git_helpers")


def test_parse_git_commit_file_reads_existing_file(tmp_path):
    module = _import_git_helpers()

    commit_file = tmp_path / "git_commit"
    commit_file.write_text(
        "commit abcdef1234567890\n"
        "M dj_pipeline/vr4mice/actions/populate_rig.py\n"
        "?? scratch.txt\n"
    )

    ret = module.parse_git_commit_file(filename=str(commit_file))

    assert ret["commit_hash"] == "abcdef1234567890"
    assert ret["changed_files"] == ["M dj_pipeline/vr4mice/actions/populate_rig.py"]


def test_parse_git_commit_file_missing_returns_empty_and_logs_once(tmp_path):
    module = _import_git_helpers()

    # Reset module-level one-shot guard for deterministic test behavior.
    module._missing_commit_file_logged = False
    module.logger.warning = MagicMock()

    missing_file = tmp_path / "does_not_exist_git_commit"

    # Force no git fallback so we exercise warning/empty-return path.
    module._collect_git_metadata_from_repo = lambda: None

    ret1 = module.parse_git_commit_file(filename=str(missing_file))
    ret2 = module.parse_git_commit_file(filename=str(missing_file))

    assert ret1 == {"commit_hash": "", "changed_files": []}
    assert ret2 == {"commit_hash": "", "changed_files": []}

    # Should only log the missing-file notice once.
    assert module.logger.warning.call_count == 1
    warning_args = module.logger.warning.call_args[0]
    assert "Checked:" in warning_args[0]
    assert str(missing_file) in warning_args[2]


def test_parse_git_commit_file_uses_git_fallback_when_file_missing(tmp_path):
    module = _import_git_helpers()

    module._missing_commit_file_logged = False
    module.logger.warning = MagicMock()

    missing_file = tmp_path / "does_not_exist_git_commit"
    expected = {
        "commit_hash": "abc123",
        "changed_files": [" M dj_pipeline/vr4mice/utils/git_helpers.py"],
    }
    module._collect_git_metadata_from_repo = lambda: expected

    ret = module.parse_git_commit_file(filename=str(missing_file))

    assert ret == expected
    assert module.logger.warning.call_count == 0
