"""
Pure helpers for parsing session filenames and discovering related rig files.

Filename contract (examples, change checklist): gui_transfer/README.md → Rig filename contract.
"""

import re
from datetime import date, datetime
from fnmatch import fnmatch
from pathlib import Path

import numpy as np

SESSION_RE = re.compile(r"([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)")

# 3-camera setup: camera 2 films the input screen; the pipeline aligns VIDEO2 to the
# game with the CAMERA2 timestamps (vr4mice/schema/inputs_videos.py -> InputVideo)
INPUT_VIDEO_KEYS = ("input_video_path", "input_ts_path")
INPUT_VIDEO_FOLDER = "raw_input_videos"

PATH_KEYS_FOR_SEARCH = (
    "teensy_path",
    "dlc_path",
    "camera_path",
    "video_path",
    "proc_path",
    "input_video_path",
    "input_ts_path",
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


def check_input_video_pair(dataset, video, timestamps):
    """
    Check that an input video (VIDEO2) and its timestamps (CAMERA2) belong to a session.

    Args:
        dataset: Session name {mouse}_{yyyy-mm-dd}_{attempt} the files are sent with.
        video: Path to {prefix}_{dataset}_VIDEO2.avi, or None.
        timestamps: Path to TS_{prefix}_{dataset}_CAMERA2.npy, or None.

    Returns:
        list of str: The problems found, empty if the pair can be sent.
    """
    if video is None or timestamps is None:
        missing = "input video (VIDEO2)" if video is None else "timestamps (CAMERA2)"
        return [f"the {missing} is missing, both files are needed"]
    video, timestamps = Path(video), Path(timestamps)

    problems = []
    video_match = re.fullmatch(
        r"(.+)_" + re.escape(dataset) + r"_VIDEO2\.avi", video.name
    )
    ts_match = re.fullmatch(
        r"TS_(.+)_" + re.escape(dataset) + r"_CAMERA2\.npy", timestamps.name
    )
    if not video_match:
        problems.append(f"{video.name} is not named <prefix>_{dataset}_VIDEO2.avi")
    if not ts_match:
        problems.append(
            f"{timestamps.name} is not named TS_<prefix>_{dataset}_CAMERA2.npy"
        )
    if video_match and ts_match and video_match.group(1) != ts_match.group(1):
        problems.append(f"{video.name} and {timestamps.name} have different prefixes")
    if video.parent != timestamps.parent:
        problems.append("the video and the timestamps are in different folders")
    # rig folders are <dataset>/run_XXXX/: a file in another session's folder was
    # recorded in that session, whatever its name says
    for folder in (video.parent, video.parent.parent):
        if SESSION_RE.fullmatch(folder.name) and folder.name != dataset:
            problems.append(f"the files are in the folder of session {folder.name}")
            break
    if problems:
        return problems

    for path in (video, timestamps):
        if not path.is_file() or path.stat().st_size == 0:
            problems.append(f"{path.name} is missing or empty")
    if problems:
        return problems

    try:
        stamps = np.load(timestamps, mmap_mode="r")
    except Exception as e:
        return [f"{timestamps.name} cannot be read: {e}"]
    if stamps.ndim != 1 or len(stamps) < 2:
        return [
            f"{timestamps.name} is not a list of frame times (shape {stamps.shape})"
        ]
    first = float(stamps[0])
    if not np.isfinite(first) or first < 1e9:
        return [f"{timestamps.name} does not hold unix times (first value {first})"]
    session_day = date.fromisoformat(SESSION_RE.fullmatch(dataset).group(2))
    recorded = datetime.fromtimestamp(first).date()
    if abs((recorded - session_day).days) > 1:
        problems.append(
            f"{timestamps.name} was recorded on {recorded}, not on {session_day}"
        )
    if np.any(np.diff(stamps) <= 0):
        problems.append(f"{timestamps.name} times are not increasing")
    return problems
