"""
Pure helpers for parsing session filenames and discovering related rig files.

Filename contract (examples, change checklist): gui_transfer/README.md → Rig filename contract.
"""

import re
from fnmatch import fnmatch
from pathlib import Path

SESSION_RE = re.compile(r"([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)")

PATH_KEYS_FOR_SEARCH = (
    "teensy_path",
    "dlc_path",
    "camera_path",
    "video_path",
    "proc_path",
    "raw_data_src",
)


def dataset_stem_from_filename(filename):
    """
    Extract {mouse}_{yyyy-mm-dd}_{attempt} from a rig filename, if present.
    """
    match = SESSION_RE.search(Path(filename).stem)
    if not match:
        return None
    return f"{match.group(1)}_{match.group(2)}_{match.group(3)}"


def parse_session_from_filename(filename):
    """
    Parse mouse name, attempt, and date from a filename.

    Returns:
        tuple (mouse_name, attempt, date) or False if not parseable.
    """
    match = SESSION_RE.search(Path(filename).stem)
    if not match:
        return False
    return match.group(1), match.group(3), match.group(2)


def _format_matches(filename, format_spec):
    name = Path(filename).name
    if isinstance(format_spec, (list, tuple)):
        return any(fnmatch(name, pattern) for pattern in format_spec)
    return fnmatch(name, format_spec)


def check_file_format(key, filename, format_spec, current_mouse=None):
    """
    Validate filename against expected pattern(s) and return session fields.
    """
    if not filename:
        return False

    if isinstance(filename, (list, tuple)):
        if not filename:
            return False
        parsed = check_file_format(key, filename[0], format_spec, current_mouse)
        if parsed is False:
            return False
        for extra in filename[1:]:
            if not _format_matches(extra, format_spec):
                return False
            if dataset_stem_from_filename(extra) != dataset_stem_from_filename(
                filename[0]
            ):
                return False
        return parsed

    if not _format_matches(filename, format_spec):
        return False

    parsed = parse_session_from_filename(filename)
    if parsed is False:
        return False

    mouse_name, attempt, date = parsed
    if current_mouse and mouse_name.lower() != str(current_mouse).lower():
        return False
    return mouse_name, attempt, date


def find_related_files(dataset_stem, path_by_key, get_type_fn):
    """
    Find one file per transfer type that belongs to the same session.

    Args:
        dataset_stem: e.g. Testmouse_2023-02-22_2
        path_by_key: mapping config key -> directory path string
        get_type_fn: callable(filename) -> transfer key string

    Returns:
        dict mapping transfer key -> Path
    """
    if not dataset_stem:
        return {}

    found = {}
    seen_dirs = set()

    for path_key in PATH_KEYS_FOR_SEARCH:
        directory = path_by_key.get(path_key)
        if not directory:
            continue
        parent = Path(directory)
        try:
            resolved = parent.resolve()
        except OSError:
            continue
        if resolved in seen_dirs or not parent.is_dir():
            continue
        seen_dirs.add(resolved)

        for filepath in parent.iterdir():
            if not filepath.is_file():
                continue
            if dataset_stem_from_filename(filepath.name) != dataset_stem:
                continue
            file_key = get_type_fn(filepath.name)
            if file_key not in found:
                found[file_key] = filepath

    return found
