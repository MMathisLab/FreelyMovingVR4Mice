"""Git metadata helpers for analysis pipeline provenance."""

from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def parse_git_commit_file(filename="git_commit"):
    """Parse a git commit file into hash and modified file list."""
    commit_hash = None
    modified_files = []

    try:
        with open(filename, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if line.startswith("commit "):
                    commit_hash = line.split()[1]
                elif line.startswith("M "):
                    modified_files.append(line)

        return {"commit_hash": commit_hash, "changed_files": modified_files}

    except FileNotFoundError:
        logger.warning(f"Error: File '{filename}' not found.")
        return {"commit_hash": "", "changed_files": []}
