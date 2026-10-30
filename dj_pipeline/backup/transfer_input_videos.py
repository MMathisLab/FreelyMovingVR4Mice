"""Copy input videos to the server share, in the folders the pipeline reads.

Two kinds of input video (see ``vr4mice/schema/inputs_videos.py``):

- method 1, OBS screen recordings ``<dataset>.mkv`` / ``<dataset>.mp4`` ->
  ``<dest>/raw_screen_recordings/``
- method 2, 3-camera setup: ``{prefix}_<dataset>_VIDEO2.avi`` and
  ``TS_{prefix}_<dataset>_CAMERA2.npy``, found in
  ``<videos_dlc>/<dataset>/run_XXXX/`` -> ``<dest>/raw_input_videos/`` (flat)

``<dest>`` is the share mounted as SCREEN_RECORDINGS_PATH on the server.

Nothing is copied without ``--run``: by default the script only prints what it
would do. Existing files are never overwritten: a destination file with the same
size counts as already copied, a different size is reported as a conflict. Each
file is copied to ``<name>.part`` and renamed once its size matches, so the
pipeline never sees a partial video.

Example (Windows, from the repo root)::

    python dj_pipeline/backup/transfer_input_videos.py ^
        --dest "\\\\neuropixels_backup\\vr4mice\\raw_screen_recordings" ^
        --obs-src "C:\\Users\\Windows\\Videos" ^
        --camera-src "D:\\AR_data\\raw_data\\Videos_dlc"

Add ``--run`` to copy, ``--datasets`` / ``--since`` to restrict the sessions,
``--fix-names`` to copy camera files whose name has another dataset than their
session folder under the folder's name.
"""

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

DATASET_RE = re.compile(r"([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)")
# OBS names, tolerating stray spaces around the separators (e.g. "Jacana_2024-07-26 _1.mkv")
OBS_RE = re.compile(
    r"^([A-Za-z0-9]+)\s*_\s*(\d{4}-\d{2}-\d{2})\s*_\s*(\d+)\s*\.(mkv|mp4)$",
    re.IGNORECASE,
)
OBS_FOLDER = "raw_screen_recordings"
CAMERA_FOLDER = "raw_input_videos"
CAMERA = 2


@dataclass
class Copy:
    """One file to copy."""

    method: str
    dataset: str
    src: Path
    dst: Path
    note: str = ""


def _dataset_date(dataset: str) -> Optional[date]:
    match = DATASET_RE.fullmatch(dataset)
    return date.fromisoformat(match.group(2)) if match else None


def _selected(dataset: str, datasets: Optional[List[str]], since: Optional[date]):
    if datasets and dataset not in datasets:
        return False
    if since is not None:
        day = _dataset_date(dataset)
        if day is None or day < since:
            return False
    return True


def plan_obs(obs_src: Path, dest: Path, datasets, since) -> List[Copy]:
    """OBS recordings ``<dataset>.mkv/.mp4`` directly inside ``obs_src``."""
    copies = []
    for path in sorted(obs_src.iterdir()):
        match = OBS_RE.match(path.name)
        if not path.is_file() or not match:
            continue
        dataset = f"{match.group(1)}_{match.group(2)}_{match.group(3)}"
        if not _selected(dataset, datasets, since):
            continue
        name = f"{dataset}.{match.group(4).lower()}"
        note = f"renamed from '{path.name}'" if name != path.name else ""
        copies.append(Copy("obs", dataset, path, dest / OBS_FOLDER / name, note))
    return copies


def plan_camera(camera_src: Path, dest: Path, datasets, since, fix_names, problems):
    """VIDEO2 + CAMERA2 pairs from ``<camera_src>/<dataset>/run_XXXX/``."""
    copies = []
    for folder in sorted(camera_src.iterdir()):
        if not folder.is_dir() or not DATASET_RE.fullmatch(folder.name):
            continue
        dataset = folder.name
        if not _selected(dataset, datasets, since):
            continue

        pairs = []
        for run in sorted([folder] + [p for p in folder.iterdir() if p.is_dir()]):
            videos = sorted(run.glob(f"*_VIDEO{CAMERA}.avi"))
            stamps = sorted(run.glob(f"TS_*_CAMERA{CAMERA}.npy"))
            if len(videos) == 1 and len(stamps) == 1:
                pairs.append((videos[0], stamps[0]))
        if not pairs:
            continue  # old-setup session or nothing recorded with camera 2
        if len(pairs) > 1:
            problems.append(
                f"{dataset}: VIDEO{CAMERA}/CAMERA{CAMERA} in several runs "
                f"({', '.join(str(v.parent.name) for v, _ in pairs)}); skipped, "
                "copy the right run by hand"
            )
            continue

        video, stamps = pairs[0]
        named = {DATASET_RE.search(p.name).group(0) for p in (video, stamps)}
        video_dataset = DATASET_RE.search(video.name).group(0)
        prefix = video.name[: video.name.index(video_dataset)].rstrip("_")
        note = ""
        if named != {dataset}:
            if not fix_names:
                problems.append(
                    f"{dataset}: files are named {sorted(named)} but sit in the "
                    f"{dataset} folder; skipped (check them, then --fix-names "
                    "copies them under the folder's name)"
                )
                continue
            note = f"renamed from {sorted(named)} (--fix-names)"
        prefix = prefix or "vr4mice"
        copies.append(
            Copy(
                "camera",
                dataset,
                video,
                dest / CAMERA_FOLDER / f"{prefix}_{dataset}_VIDEO{CAMERA}.avi",
                note,
            )
        )
        copies.append(
            Copy(
                "camera",
                dataset,
                stamps,
                dest / CAMERA_FOLDER / f"TS_{prefix}_{dataset}_CAMERA{CAMERA}.npy",
                note,
            )
        )
    return copies


def copy_file(copy: Copy) -> str:
    """Copy one file via ``<dst>.part``; returns what happened."""
    size = copy.src.stat().st_size
    if copy.dst.exists():
        if copy.dst.stat().st_size == size:
            return "already there"
        return f"CONFLICT: {copy.dst} exists with another size, not overwritten"
    copy.dst.parent.mkdir(parents=True, exist_ok=True)
    part = copy.dst.with_name(copy.dst.name + ".part")
    shutil.copy2(copy.src, part)
    if part.stat().st_size != size:
        part.unlink()
        return "FAILED: size mismatch after copy, removed the partial file"
    os.replace(part, copy.dst)
    return "copied"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dest",
        type=Path,
        required=True,
        help="Share mounted as SCREEN_RECORDINGS_PATH on the server",
    )
    parser.add_argument(
        "--obs-src", type=Path, help="Folder with <dataset>.mkv/.mp4 OBS recordings"
    )
    parser.add_argument(
        "--camera-src",
        type=Path,
        help="Videos_dlc folder with one <dataset>/run_XXXX/ folder per session",
    )
    parser.add_argument("--datasets", nargs="+", help="Only these datasets")
    parser.add_argument(
        "--since", type=date.fromisoformat, help="Only sessions on/after YYYY-MM-DD"
    )
    parser.add_argument(
        "--fix-names",
        action="store_true",
        help="Copy camera files named after another dataset under their folder's name",
    )
    parser.add_argument(
        "--run", action="store_true", help="Copy (default: only print the plan)"
    )
    args = parser.parse_args(argv)

    if not args.obs_src and not args.camera_src:
        parser.error("give --obs-src and/or --camera-src")
    for source in (args.obs_src, args.camera_src):
        if source is not None and not source.is_dir():
            parser.error(f"source folder not found: {source}")

    problems: List[str] = []
    copies: List[Copy] = []
    if args.obs_src:
        copies += plan_obs(args.obs_src, args.dest, args.datasets, args.since)
    if args.camera_src:
        copies += plan_camera(
            args.camera_src,
            args.dest,
            args.datasets,
            args.since,
            args.fix_names,
            problems,
        )

    both = {c.dataset for c in copies if c.method == "obs"} & {
        c.dataset for c in copies if c.method == "camera"
    }
    for dataset in sorted(both):
        problems.append(
            f"{dataset}: has both an OBS recording and camera files; the pipeline "
            "uses the camera files"
        )

    for copy in copies:
        size_gb = copy.src.stat().st_size / 1e9
        note = f"  ({copy.note})" if copy.note else ""
        print(f"[{copy.method}] {copy.src} -> {copy.dst}  {size_gb:.2f} GB{note}")
    total = sum(c.src.stat().st_size for c in copies) / 1e9
    print(
        f"\n{len(copies)} files, {total:.1f} GB "
        f"({len({c.dataset for c in copies})} datasets)"
    )
    for problem in problems:
        print(f"WARNING {problem}")

    if not args.run:
        print("\nDry run: nothing copied. Add --run to copy.")
        return 0

    failures = 0
    for i, copy in enumerate(copies, 1):
        result = copy_file(copy)
        failures += result.startswith(("CONFLICT", "FAILED"))
        print(f"[{i}/{len(copies)}] {copy.dst.name}: {result}", flush=True)
    print(f"\nDone, {failures} problem(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
