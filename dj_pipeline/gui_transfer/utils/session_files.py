"""
Pure helpers for parsing session filenames and discovering related rig files.

Filename contract (examples, change checklist): gui_transfer/README.md → Rig filename contract.
"""

import re
from fnmatch import fnmatch
from pathlib import Path

SESSION_RE = re.compile(r"([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)")
CAMERA_NUMBER_RE = re.compile(r"(?:CAMERA|VIDEO)(\d+)", re.IGNORECASE)

# Rig always has exactly 3 cameras; this is the camera to default to when a
# picked file (e.g. DLC output) carries no camera number of its own.
DEFAULT_CAMERA_NUMBER = 3

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


def camera_number_from_filename(filename):
    """
    Extract the camera index from a rig filename (e.g. "..._CAMERA3.npy" or
    "..._VIDEO3.avi" -> 3). Returns None for filenames with no camera suffix
    (single-camera rigs, or non-camera files like DLC/PROC/teensy).
    """
    match = CAMERA_NUMBER_RE.search(Path(filename).stem)
    if not match:
        return None
    return int(match.group(1))


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


def find_related_files(dataset_stem, path_by_key, get_type_fn, camera_number=None):
    """
    Find one file per transfer type that belongs to the same session.

    Args:
        dataset_stem: e.g. Testmouse_2023-02-22_2
        path_by_key: mapping config key -> directory path string
        get_type_fn: callable(filename) -> transfer key string
        camera_number: if set, on a rig with multiple cameras (files
            suffixed "..._CAMERA3.npy" / "..._VIDEO3.avi"), only match
            candidate files for that camera index. Files with no camera
            suffix (single-camera rigs, DLC/PROC/teensy) are unaffected.
            If None (the file that was picked has no camera suffix, e.g.
            DLC/PROC/teensy), a role with several different camera numbers
            present is ambiguous; DEFAULT_CAMERA_NUMBER is used to resolve
            it. If DEFAULT_CAMERA_NUMBER isn't among the candidates, there is
            no safe default to autocomplete to, so that role is left out of
            the result entirely (no fallback to e.g. the max camera number).
            A role where every match shares the same number (or none has a
            number at all) is unaffected.

    Returns:
        dict mapping transfer key -> Path
    """
    if not dataset_stem:
        return {}

    candidates = {}
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
            file_camera_number = camera_number_from_filename(filepath.name)
            if (
                camera_number is not None
                and file_camera_number is not None
                and file_camera_number != camera_number
            ):
                continue
            file_key = get_type_fn(filepath.name)
            candidates.setdefault(file_key, []).append((file_camera_number, filepath))

    found = {}
    for file_key, matches in candidates.items():
        if camera_number is None:
            distinct_numbers = {n for n, _ in matches if n is not None}
            if len(distinct_numbers) > 1:
                if DEFAULT_CAMERA_NUMBER not in distinct_numbers:
                    continue
                matches = [m for m in matches if m[0] == DEFAULT_CAMERA_NUMBER]
        else:
            exact = [m for m in matches if m[0] == camera_number]
            if exact:
                matches = exact
        found[file_key] = matches[0][1]

    return found
