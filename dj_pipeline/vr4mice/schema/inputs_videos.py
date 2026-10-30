"""Video input schema: align the input video (what the mouse sees) to game steps.

Two recording setups, one end table:

- Old setup: OBS screen recording of the screens (``<dataset>.mkv`` or ``.mp4``).
  ``RawVideo`` -> ``RawVideoSync`` (sync square trace); frames are matched to
  steps with the photodiode, which sees the same sync square.
- 3-camera setup: camera 2 films the screens and saves per-frame timestamps on
  the game's host clock. ``InputVideo``; frames are matched to steps by
  timestamp. Used for every dataset with ``{prefix}_{dataset}_VIDEO2.avi`` and
  ``TS_{prefix}_{dataset}_CAMERA2.npy`` in ``INPUT_VIDEO_DIR``; those datasets
  are left out of ``RawVideo``.

``StepVideoFrame`` holds the result for both, with the same columns: the frame
of each game step and the mouse-view panel to crop, so analyses fetch frames the
same way whatever the setup (``StepVideoFrame.align_step_to_frames`` and
``StepVideoFrame.get_frame``).
"""

import pathlib

import cv2
import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "inputs_videos"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()

# OBS recordings: <dataset>.mkv (older) or <dataset>.mp4, 1920x1080
OBS_VIDEO_DIR = "/vr4mice_screen_recordings/raw_screen_recordings"
OBS_VIDEO_EXTENSIONS = (".mkv", ".mp4")
OBS_FRAME_SIZE = (1920, 1080)
# 3-camera setup: input videos sit next to the OBS recordings, on the same mount.
INPUT_VIDEO_DIR = "/vr4mice_screen_recordings/raw_input_videos"
INPUT_VIDEO_CAMERA = 2
INPUT_VIDEO_FRAME_SIZE = (640, 480)
# Mouse-view panel (bottom-left screen) in the 640x480 camera-2 video, as
# (x, y, width, height).
INPUT_VIDEO_VISUAL_ROI = (0, 243, 316, 237)
# Below this fraction of game steps inside the video, the alignment is rejected
# (e.g. a video from another session saved under the wrong name).
MIN_STEP_COVERAGE = 0.9
# Below this fraction of video sync edges matching photodiode edges, the video
# is rejected (wrong session, or video paired with the wrong timestamps).
MIN_SYNC_MATCH = 0.8


def input_video_files(input_video_dir: str = INPUT_VIDEO_DIR) -> dict:
    """Return {dataset: (video_path, timestamp_path)} for input videos on disk."""
    from vr4mice.actions.populate_rig import _img_src_candidates
    from vr4mice.analysis.inputs_videos import list_input_video_files

    if not pathlib.Path(input_video_dir).is_dir():
        # Expected until 3-camera input videos are copied to the server.
        logger.info("Input video folder not found: %s", input_video_dir)
        return {}
    return list_input_video_files(
        input_video_dir, _img_src_candidates(), camera=INPUT_VIDEO_CAMERA
    )


def input_video_datasets(input_video_dir: str = INPUT_VIDEO_DIR) -> list:
    """Return the datasets recorded with the 3-camera setup (see module docstring)."""
    return sorted(input_video_files(input_video_dir))


def _record_failure(dataset: str, table_name: str, error) -> None:
    """Record a failed session (message cut to the column size) and log it."""
    message = str(error)
    vr4mice.FailedSession().add_entry(dataset, table_name, message[:1024])
    logger.warning(f"Error {table_name}, dataset {dataset}; {message}")


@schema
class VideoFileIssue(dj.Manual):
    """Problems with the files in the input video folders, refreshed by
    ``check_video_files`` (also files of sessions not in vr4mice.Dataset,
    which FailedSession cannot hold)."""

    definition = """
    folder: varchar(32)          # raw_screen_recordings or raw_input_videos
    file_name: varchar(255)      # file in that folder
    ---
    issue: varchar(1024)         # what is wrong with it
    """


def check_video_files(
    obs_dir: str = OBS_VIDEO_DIR, input_video_dir: str = INPUT_VIDEO_DIR
) -> list:
    """Audit both input video folders and refresh ``VideoFileIssue``.

    Flags unexpected names, half camera pairs (VIDEO2 without its CAMERA2
    timestamps or the reverse), other cameras' files, sessions not ingested in
    vr4mice.Dataset, and sessions with both an OBS and a camera video. Issues
    that are gone are removed. Half pairs of ingested sessions are also recorded
    in FailedSession for InputVideo.

    Returns:
        The current issues as (folder, file name, issue) tuples.
    """
    from vr4mice.actions.populate_rig import _img_src_candidates
    from vr4mice.analysis.inputs_videos import audit_video_files

    def names(folder):
        path = pathlib.Path(folder)
        return [p.name for p in path.iterdir() if p.is_file()] if path.is_dir() else []

    folders = {
        "obs": pathlib.Path(obs_dir).name,
        "camera": pathlib.Path(input_video_dir).name,
    }
    known = set(vr4mice.Dataset.fetch("dataset"))
    issues = [
        (folders[kind], name, issue)
        for kind, name, issue in audit_video_files(
            names(obs_dir),
            names(input_video_dir),
            known,
            _img_src_candidates(),
            camera=INPUT_VIDEO_CAMERA,
        )
    ]

    current = {(folder, name): issue for folder, name, issue in issues}
    for row in VideoFileIssue.fetch("KEY"):
        if (row["folder"], row["file_name"]) not in current:
            (VideoFileIssue & row).delete_quick()
    VideoFileIssue.insert(
        [
            {"folder": f, "file_name": n, "issue": i[:1024]}
            for (f, n), i in current.items()
        ],
        replace=True,
    )

    for folder, name, issue in issues:
        logger.warning("Input video file issue: %s/%s: %s", folder, name, issue)
        if folder == folders["camera"] and issue.startswith("no "):
            dataset = next((d for d in known if f"_{d}_" in name), None)
            if dataset and not issue.startswith("no session"):
                vr4mice.FailedSession().add_entry(
                    dataset, "InputVideo", f"{name}: {issue}"[:1024]
                )
    return issues


@schema
class ObsVideoLayout(dj.Lookup):
    """Mouse-view panel in the OBS recordings, per batch (screen layout changed)."""

    definition = """
    -> vr4mice.Batch
    ---
    visual_roi: <blob>   # (x, y, w, h) of the mouse-view panel in the 1920x1080 recording
    """

    contents = [
        # Measured on a batch1 recording (Jacana_2024-07-26_1).
        ("batch1", (0, 569, 926, 511)),
        # Measured on the 2026-06/07 batch2 recordings (Xestia/Whale 06-29..07-13).
        ("batch2", (0, 545, 948, 535)),
    ]


@schema
class RawVideo(dj.Imported):
    """Stores the raw OBS recording path for a dataset (old setup)."""

    definition = """
    -> vr4mice.Dataset             # source dataset key
    ---
    video_path: varchar(255)       # absolute path to the raw OBS recording
    """

    @property
    def key_source(self):
        # 3-camera datasets go through InputVideo instead.
        camera_datasets = input_video_datasets()
        if not camera_datasets:
            return vr4mice.Dataset.proj()
        return vr4mice.Dataset.proj() - [{"dataset": d} for d in camera_datasets]

    def make(self, key):
        """Insert the raw OBS recording path (.mkv or .mp4) after checking it."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        candidates = [
            pathlib.Path(OBS_VIDEO_DIR) / f"{key['dataset']}{extension}"
            for extension in OBS_VIDEO_EXTENSIONS
        ]
        video_path = next((path for path in candidates if path.is_file()), None)
        if video_path is None:
            # Not an error: many sessions have no OBS recording.
            logger.debug("No OBS recording for %s: %s", key["dataset"], candidates)
            return

        try:
            cap = cv2.VideoCapture(str(video_path))
            try:
                if not cap.isOpened():
                    raise IOError(f"Cannot open {video_path} (corrupt or incomplete?)")
                n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                size = (
                    int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                )
                readable, _ = cap.read()
            finally:
                cap.release()
            if n_frames <= 0 or not readable:
                raise IOError(f"No readable frames in {video_path} (incomplete copy?)")
            if size != OBS_FRAME_SIZE:
                raise ValueError(
                    f"{video_path} is {size[0]}x{size[1]}, OBS recordings are "
                    f"{OBS_FRAME_SIZE[0]}x{OBS_FRAME_SIZE[1]}: not an OBS recording?"
                )
            self.insert1({**key, "video_path": str(video_path)})
        except Exception as err:
            _record_failure(key["dataset"], self.__class__.__name__, err)
            return None


@schema
class RawVideoSync(dj.Computed):
    """Sync square of an OBS recording: its location and per-frame intensity."""

    definition = """
    -> RawVideo
    ---
    fps: float64           # nominal frame rate of the recording (frames evenly spaced)
    n_frames: int32        # frames read from the recording
    sync_roi: <blob>       # (x, y, w, h) of the sync square, found in the recording
    sync_trace: <blob>     # mean intensity inside the sync square, per frame (uint8)
    seek_offset: int32     # frames cv2 seeking lands from the requested one (corrected on read)
    """

    def make(self, key):
        """Locate the sync square and read its intensity in every frame."""
        from vr4mice.analysis.inputs_videos import (
            find_sync_square,
            measure_seek_offset,
            read_sync_trace,
        )

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            video_path = (RawVideo & key).fetch1("video_path")
            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    raise IOError(f"Failed to open video file: {video_path}")
                fps = float(cap.get(cv2.CAP_PROP_FPS))
            finally:
                cap.release()

            sync_roi = find_sync_square(video_path)
            sync_trace = read_sync_trace(video_path, sync_roi)
            low, high = np.percentile(sync_trace, [5, 95])
            if high - low < 50:
                raise ValueError(
                    f"Sync square {sync_roi} in {video_path} does not switch between "
                    f"two levels (5th/95th percentiles {low:.0f}/{high:.0f})"
                )

            self.insert1(
                {
                    **key,
                    "fps": fps,
                    "n_frames": len(sync_trace),
                    "sync_roi": sync_roi,
                    "sync_trace": sync_trace,
                    "seek_offset": measure_seek_offset(video_path),
                }
            )
        except Exception as err:
            _record_failure(key["dataset"], self.__class__.__name__, err)
            return None


@schema
class InputVideo(dj.Imported):
    """Input video filmed by camera 2 (3-camera setup) and its frame timestamps."""

    definition = """
    -> vr4mice.Dataset              # source dataset key
    ---
    video_path: varchar(255)        # camera-2 input video ({prefix}_{dataset}_VIDEO2.avi)
    timestamp_path: varchar(255)    # its timestamps (TS_{prefix}_{dataset}_CAMERA2.npy)
    n_frames: int32                 # frame count, equal to the number of timestamps
    width: int32                    # frame width (pixels)
    height: int32                   # frame height (pixels)
    timestamps: <blob>              # unix time of each frame (s), game host clock
    visual_roi: <blob>              # (x, y, w, h) of the mouse-view panel in the frame
    sync_roi: <blob>                # (x, y, w, h) of the sync square, found in the video
    seek_offset: int32              # frames cv2 seeking lands from the requested one (corrected on read)
    """

    @property
    def key_source(self):
        return vr4mice.Dataset.proj() & [{"dataset": d} for d in input_video_datasets()]

    def make(self, key):
        """Insert the input video path, frame count and frame timestamps."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        files = input_video_files().get(key["dataset"])
        if files is None:
            logger.warning(
                "Transient missing file for %s, key: %s. No VIDEO%d/CAMERA%d pair in %s",
                self.__class__.__name__,
                key,
                INPUT_VIDEO_CAMERA,
                INPUT_VIDEO_CAMERA,
                INPUT_VIDEO_DIR,
            )
            return

        video_path, timestamp_path = files
        try:
            from vr4mice.analysis.inputs_videos import (
                check_camera_timestamps,
                find_sync_square,
                measure_seek_offset,
            )

            timestamps = np.asarray(np.load(timestamp_path), dtype=float)
            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    raise IOError(f"Cannot open {video_path} (corrupt or incomplete?)")
                n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            finally:
                cap.release()

            problems = []
            if (width, height) != INPUT_VIDEO_FRAME_SIZE:
                problems.append(
                    f"video is {width}x{height}, camera {INPUT_VIDEO_CAMERA} records "
                    f"{INPUT_VIDEO_FRAME_SIZE[0]}x{INPUT_VIDEO_FRAME_SIZE[1]}: "
                    "another camera's video?"
                )
            if timestamps.ndim != 1 or timestamps.size != n_frames:
                problems.append(
                    f"video has {n_frames} frames but the timestamps file has "
                    f"{timestamps.size} values: video and timestamps from different "
                    "cameras or sessions?"
                )
            problems += check_camera_timestamps(timestamps, key["dataset"])
            if problems:
                raise ValueError(
                    f"{pathlib.Path(video_path).name} / "
                    f"{pathlib.Path(timestamp_path).name}: " + "; ".join(problems)
                )
            try:
                sync_roi = find_sync_square(video_path)
            except ValueError:
                raise ValueError(
                    f"{video_path}: no sync square, so it does not film the "
                    "screens: another camera's video?"
                )

            self.insert1(
                {
                    **key,
                    "video_path": video_path,
                    "timestamp_path": timestamp_path,
                    "n_frames": n_frames,
                    "width": width,
                    "height": height,
                    "visual_roi": INPUT_VIDEO_VISUAL_ROI,
                    "sync_roi": sync_roi,
                    "seek_offset": measure_seek_offset(video_path),
                    "timestamps": timestamps,
                }
            )
        except Exception as err:
            _record_failure(key["dataset"], self.__class__.__name__, err)
            return None


@schema
class StepVideoFrame(dj.Computed):
    """Input video frame of each game step, for OBS and camera recordings alike.

    ``frame_ids[i]`` is the first frame captured at or after game step ``i``
    (``State.step_time``), -1 outside the video. Frames are indexed in
    ``video_path`` and cropped to ``visual_roi`` by ``get_frame``.

    - camera (3-camera setup): matched on the camera timestamps
      (``State.start_time + step_time``, same host clock).
    - obs (old setup): sync square edges in the recording are matched with
      photodiode edges to fit video time = offset + drift * game time (see
      ``align_steps_to_frames_by_photodiode``); needs the photodiode in
      ``vr4mice.SignalsPhotodiode``. pulse_geo trains are anchored on their
      irregular intervals; regular "pulse" trains (batch1) on their first edge,
      so the recording must start before the pulses.

    NOTE(celia): on Xestia_2026-08-21_1 the screen showed the sync square a
    median 62 ms after PROC sent it, so a step's content appears ~60 ms after
    its frame.
    """

    definition = """
    -> vr4mice.State                    # game steps
    ---
    video_source: enum('obs', 'camera') # recording setup of the input video
    align_method: enum('photodiode', 'timestamps') # how frames were matched to steps
    video_path: varchar(255)            # video indexed by frame_ids
    visual_roi: <blob>                  # (x, y, w, h) mouse-view panel, cropped on read
    seek_offset: int32                  # frames cv2 seeking lands from the requested one
    n_steps: int32                      # number of game steps
    step: <blob>                        # step indices (State.step)
    step_time: <blob>                   # step times, game seconds (State.step_time)
    frame_ids: <blob>                   # frame of each step, -1 outside the video
    n_steps_outside_video: int32        # steps without a frame (frame_ids == -1)
    pair_count=null: int32              # obs: paired sync/photodiode edges
    rms=null: float64                   # obs: residual RMS of the edge fit (s)
    offset=null: float64                # obs: video time at game time 0 (s)
    drift=null: float64                 # obs: video/game clock rate
    median_abs_gap=null: float64        # camera: median |frame time - step time| (s)
    sync_match_fraction=null: float64   # video sync edges matching photodiode edges
    """

    @property
    def key_source(self):
        keys = InputVideo.fetch("KEY") + RawVideoSync.fetch("KEY")
        return vr4mice.State.proj() & keys

    def make(self, key):
        """Match each game step to an input video frame and store QA."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            start_time, step, step_time = (vr4mice.State & key).fetch1(
                "start_time", "step", "step_time"
            )
            start_time = float(np.ravel(start_time)[0])
            step_time = np.asarray(step_time, dtype=float)

            if InputVideo & key:
                row = self._align_camera(key, start_time, step_time)
            else:
                row = self._align_obs(key, start_time, step_time)

            frame_ids = row["frame_ids"]
            n_outside = int((frame_ids < 0).sum())
            coverage = 1 - n_outside / max(len(frame_ids), 1)
            if coverage < MIN_STEP_COVERAGE:
                raise ValueError(
                    f"{pathlib.Path(row['video_path']).name} covers {coverage:.1%} "
                    f"of the game steps ({len(step_time)} steps over "
                    f"{step_time[-1] - step_time[0]:.0f} s; minimum "
                    f"{MIN_STEP_COVERAGE:.0%}): another session's video, or a cut "
                    "recording?"
                )

            self.insert1(
                {
                    **key,
                    **row,
                    "n_steps": len(step_time),
                    "step": step,
                    "step_time": step_time,
                    "n_steps_outside_video": n_outside,
                }
            )
        except Exception as err:
            _record_failure(key["dataset"], self.__class__.__name__, err)
            return None

    @staticmethod
    def _align_camera(key, start_time, step_time):
        """Camera recording: match steps to frames on the camera timestamps."""
        from vr4mice.analysis.inputs_videos import (
            align_steps_to_frames_by_timestamps,
            step_alignment_qa,
            verify_sync_against_photodiode,
        )

        video_path, timestamps, visual_roi, sync_roi, seek_offset = (
            InputVideo & key
        ).fetch1("video_path", "timestamps", "visual_roi", "sync_roi", "seek_offset")
        step_unix_times = start_time + step_time
        frame_ids = align_steps_to_frames_by_timestamps(step_unix_times, timestamps)
        qa = step_alignment_qa(step_unix_times, timestamps, frame_ids)

        # The video and its timestamps must show the photodiode's sync pulses
        # at the photodiode's times (same clock)
        sync_match = None
        photodiode = vr4mice.SignalsPhotodiode & key
        if photodiode:
            pd_time, pd_read = photodiode.fetch1("photodiode_time", "photodiode_read")
            check = verify_sync_against_photodiode(
                video_path,
                sync_roi,
                timestamps,
                np.asarray(pd_time, dtype=float),
                np.asarray(pd_read, dtype=float),
                seek_offset=seek_offset,
            )
            sync_match = check["match_fraction"]
            if sync_match < MIN_SYNC_MATCH:
                raise ValueError(
                    f"{pathlib.Path(video_path).name}: sync square edges at the "
                    f"camera timestamps match the photodiode for {sync_match:.0%} "
                    f"of {check['n_edges']} edges (median gap "
                    f"{check['median_gap'] * 1000:.0f} ms; minimum "
                    f"{MIN_SYNC_MATCH:.0%}): video and timestamps not from the "
                    "same recording, or another session?"
                )
        else:
            logger.warning(
                "%s: no SignalsPhotodiode, camera video not checked against it",
                key["dataset"],
            )
        return {
            "sync_match_fraction": sync_match,
            "seek_offset": seek_offset,
            "video_source": "camera",
            "align_method": "timestamps",
            "video_path": video_path,
            "visual_roi": visual_roi,
            "frame_ids": frame_ids,
            "median_abs_gap": qa["median_abs_gap"],
        }

    @staticmethod
    def _align_obs(key, start_time, step_time):
        """OBS recording: match steps to frames with the photodiode sync edges."""
        from vr4mice.analysis.inputs_videos import (
            align_steps_to_frames_by_photodiode,
            binarize_sync_trace,
        )

        photodiode = vr4mice.SignalsPhotodiode & key
        if not photodiode:
            raise ValueError("No SignalsPhotodiode row: OBS videos need the photodiode")
        pd_time, pd_read, signal_type = photodiode.fetch1(
            "photodiode_time", "photodiode_read", "signal_type"
        )
        # Older PROC files have no signal_type; they used regular pulses
        signal_type = signal_type or "pulse"
        if signal_type not in ("pulse_geo", "pulse"):
            raise ValueError(
                f"Photodiode alignment needs a pulse or pulse_geo sync signal, "
                f"got {signal_type}"
            )
        batch = vr4mice.DatasetBatch & key
        if not batch:
            raise ValueError("No DatasetBatch row: run vr4mice.DatasetBatch.populate()")
        batch_name = batch.fetch1("batch_name")
        visual_roi = (ObsVideoLayout & {"batch_name": batch_name}).fetch1("visual_roi")

        video_path = (RawVideo & key).fetch1("video_path")
        fps, sync_trace, seek_offset = (RawVideoSync & key).fetch1(
            "fps", "sync_trace", "seek_offset"
        )
        n_frames = len(sync_trace)
        video_df = pd.DataFrame(
            {
                "frame_ids": np.arange(n_frames),
                "timestamps": np.arange(n_frames) / fps,
                "signals": binarize_sync_trace(sync_trace),
            }
        )
        photodiode_df = pd.DataFrame(
            {
                # unix time -> game time, the clock of step_time
                "time_stamp": np.asarray(pd_time, dtype=float) - start_time,
                "photodiode_read": np.asarray(pd_read, dtype=float),
            }
        )
        frames, qa = align_steps_to_frames_by_photodiode(
            video_df,
            photodiode_df,
            step_time,
            regular_pulses=signal_type == "pulse",
        )
        # First frame at or after each step; -1 outside the recording
        frame_ids = np.full(len(step_time), -1, dtype=np.int64)
        inside = np.isfinite(frames)
        frame_ids[inside] = np.ceil(frames[inside] - 1e-9).astype(np.int64)
        frame_ids[(frame_ids < 0) | (frame_ids >= n_frames)] = -1
        return {
            "video_source": "obs",
            "align_method": "photodiode",
            "video_path": video_path,
            "visual_roi": visual_roi,
            "frame_ids": frame_ids,
            "seek_offset": seek_offset,
            "pair_count": int(qa["pair_count"]),
            "sync_match_fraction": qa["pair_fraction"],
            "rms": qa["rms"],
            "offset": qa["offset"],
            "drift": qa["drift"],
        }

    @classmethod
    def align_step_to_frames(cls, key, timepoints: list):
        """Return the input video frame for each timepoint (game seconds).

        Timepoints are in the ``State.step_time`` base and must lie within the
        session's step times (ValueError otherwise). Returns None for a
        timepoint outside the input video.
        """
        step_time, frame_ids = (cls & key).fetch1("step_time", "frame_ids")
        step_time = np.asarray(step_time, dtype=float)
        frame_ids = np.asarray(frame_ids)
        min_time, max_time = np.min(step_time), np.max(step_time)

        for tp in timepoints:
            if not isinstance(tp, (int, float)):
                raise TypeError(f"Timepoint {tp} is not a number.")
            if tp < min_time or tp > max_time:
                raise ValueError(
                    f"Timepoint {tp} is out of bounds. Valid range: [{min_time:.3f}, {max_time:.3f}] seconds."
                )

        inside = frame_ids >= 0
        times, frames = step_time[inside], frame_ids[inside]
        result = []
        for tp in timepoints:
            if not times.size or tp < times[0] or tp > times[-1]:
                result.append(None)
            else:
                result.append(int(np.ceil(np.interp(tp, times, frames) - 1e-9)))
        return result

    @classmethod
    def get_frame(cls, key, frame_index: int):
        """Return the mouse-view panel of frame `frame_index` (BGR, as read by OpenCV)."""
        from vr4mice.analysis.inputs_videos import crop_frame, read_video_frame

        video_path, visual_roi, seek_offset = (cls & key).fetch1(
            "video_path", "visual_roi", "seek_offset"
        )
        frame = read_video_frame(video_path, frame_index, seek_offset=seek_offset)
        return crop_frame(frame, visual_roi)
