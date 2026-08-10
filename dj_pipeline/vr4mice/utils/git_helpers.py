"""Git metadata helpers for analysis pipeline provenance."""

import os
import subprocess
from pathlib import Path

from vr4mice.utils.logger import Logger

logger = Logger.get_logger()
_missing_commit_file_logged = False


def _candidate_git_commit_paths(filename: str):
    """Return likely locations for the git commit metadata file."""
    # utils -> vr4mice -> dj_pipeline
    dj_pipeline_root = Path(__file__).resolve().parents[2]

    env_path = os.environ.get("GIT_COMMIT_FILE")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(filename),
            Path.cwd().joinpath(filename),
            dj_pipeline_root.joinpath(filename),
            Path("/app").joinpath(filename),
        ]
    )

    # Deduplicate while preserving order.
    seen = set()
    unique_candidates = []
    for candidate in candidates:
        normalized = str(candidate)
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(candidate)
    return unique_candidates


def _candidate_git_roots():
    """Return likely repository roots for git metadata fallback."""
    # utils -> vr4mice -> dj_pipeline
    dj_pipeline_root = Path(__file__).resolve().parents[2]
    workspace_root = dj_pipeline_root.parent

    env_root = os.environ.get("GIT_REPO_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))

    candidates.extend([Path.cwd(), dj_pipeline_root, workspace_root])

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        normalized = str(candidate)
        if normalized not in seen:
            seen.add(normalized)
            unique_candidates.append(candidate)
    return unique_candidates


def _run_git(repo_root: Path, args):
    """Run a git command for a specific repo root and return stdout or None."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None

    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _collect_git_metadata_from_repo():
    """Collect commit hash and changed files directly from git when available."""
    for root in _candidate_git_roots():
        commit_hash = _run_git(root, ["rev-parse", "HEAD"])
        if not commit_hash:
            continue

        status = _run_git(root, ["status", "--porcelain"]) or ""
        changed_files = [line for line in status.splitlines() if line.strip()]
        return {"commit_hash": commit_hash, "changed_files": changed_files}

    return None


def _collect_git_metadata_from_env():
    """Collect commit hash from CI/env vars when repo metadata is unavailable."""
    env_commit_keys = (
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
        "GIT_COMMIT",
        "BUILD_VCS_NUMBER",
    )
    for key in env_commit_keys:
        value = os.environ.get(key)
        if value:
            return {"commit_hash": value.strip(), "changed_files": []}
    return None


def parse_git_commit_file(filename="git_commit"):
    """Parse a git commit file into hash and modified file list."""
    global _missing_commit_file_logged

    commit_hash = None
    modified_files = []
    selected_path = None

    try:
        for candidate in _candidate_git_commit_paths(filename):
            if candidate.exists():
                selected_path = candidate
                break

        if selected_path is None:
            env_fallback = _collect_git_metadata_from_env()
            if env_fallback is not None:
                return env_fallback

            fallback = _collect_git_metadata_from_repo()
            if fallback is not None:
                return fallback

            if not _missing_commit_file_logged:
                searched = ", ".join(
                    str(path) for path in _candidate_git_commit_paths(filename)
                )
                roots = ", ".join(str(path) for path in _candidate_git_roots())
                logger.warning(
                    "Git commit metadata file '%s' not found and git fallback failed; provenance fields will be empty. Checked: %s. Git roots tried: %s",
                    filename,
                    searched,
                    roots,
                )
                _missing_commit_file_logged = True
            return {"commit_hash": "", "changed_files": []}

        with open(selected_path, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if line.startswith("commit "):
                    commit_hash = line.split()[1]
                elif line.startswith("M "):
                    modified_files.append(line)

        return {"commit_hash": commit_hash, "changed_files": modified_files}

    except FileNotFoundError:
        # Defensive fallback if a discovered path disappears between exists() and open().
        if not _missing_commit_file_logged:
            logger.warning(
                "Git commit metadata file '%s' disappeared during read; provenance fields will be empty.",
                filename,
            )
            _missing_commit_file_logged = True
        return {"commit_hash": "", "changed_files": []}
