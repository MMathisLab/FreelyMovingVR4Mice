"""Video input schema: align the input video (what the mouse sees) to game steps.

Two recording setups, one end table:

- Old setup: OBS screen recording of the screens (``<dataset>.mkv`` or ``.mp4``).
  ``RawVideo`` -> ``RawVideoSync`` (sync square trace); frames are matched to
  steps with the photodiode, which sees the same sync square, or, without a
  photodiode, with the generated sync signal that drives the square.
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

# Where the recordings are found (pipeline container mount), needed before any
# table row exists; the file used is stored per row (video_path).
OBS_VIDEO_DIR = "/vr4mice_screen_recordings/raw_screen_recordings"
INPUT_VIDEO_DIR = "/vr4mice_screen_recordings/raw_input_videos"
# 3-camera setup: the camera filming the screens (<prefix>_<dataset>_VIDEO2.avi)
INPUT_VIDEO_CAMERA = 2


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


def load_generated_signal(key: dict) -> tuple:
    """Return (send_time, signal, signal_type) of the generated sync signal.

    For sessions without a photodiode (no ``vr4mice.SignalsPhotodiode`` row),
    read from ``dlc.DLCProcessor`` (the session's PROC file; any DLC model, they
    share the signal). ``send_time`` is in unix seconds, the clock of
    ``State.start_time``. The signal type comes from DLCProcessor's
    ``signal_type`` column when it has one and it is set; otherwise it is
    inferred: regular intervals between pulses are a "pulse" train (batch1),
    irregular ones "pulse_geo".
    """
    from vr4mice.schema import dlc

    attrs = ["time_stamp", "signal"]
    if "signal_type" in dlc.DLCProcessor.heading.names:
        attrs.append("signal_type")
    rows = (dlc.DLCProcessor & key).fetch(*attrs, as_dict=True)
    rows = [r for r in rows if r["time_stamp"] is not None and r["signal"] is not None]
    if not rows:
        raise ValueError(
            "No photodiode (SignalsPhotodiode) and no generated sync signal "
            "(dlc.DLCProcessor) for this session"
        )
    send_time = np.asarray(rows[0]["time_stamp"], dtype=float).ravel()
    signal = np.asarray(rows[0]["signal"], dtype=float).ravel()
    n = min(len(send_time), len(signal))
    send_time, signal = send_time[:n], signal[:n]

    high = signal > (np.nanmin(signal) + np.nanmax(signal)) / 2
    onsets = send_time[1:][high[1:] & ~high[:-1]]
    intervals = np.diff(onsets)
    if len(intervals) < 10:
        raise ValueError(f"Generated sync signal has {len(onsets)} pulses only")
    stored = rows[0].get("signal_type")
    if stored:
        return send_time, signal, stored
    regular = np.std(intervals) < 0.1 * np.mean(intervals)
    return send_time, signal, "pulse" if regular else "pulse_geo"


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
    vr4mice.Dataset, and sessions with both an OBS and a camera video. Missing
    partners are tracked in ``VideoFileIssue`` and cleared on the next audit
    after both files arrive. The audit also removes other resolved issues.

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

    # One row per file: a file with several problems keeps them all
    current = {}
    for folder, name, issue in issues:
        key = (folder, name)
        current[key] = f"{current[key]}; {issue}" if key in current else issue
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

        # <dataset>.mkv (older recordings) or <dataset>.mp4
        candidates = [
            pathlib.Path(OBS_VIDEO_DIR) / f"{key['dataset']}{extension}"
            for extension in (".mkv", ".mp4")
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
            # OBS records the whole 1920x1080 screen; ObsVideoLayout's panels
            # are positions in that frame, so another size cannot be cropped.
            if size != (1920, 1080):
                raise ValueError(
                    f"{video_path} is {size[0]}x{size[1]}, OBS recordings are "
                    "1920x1080: not an OBS recording?"
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
    video_path: varchar(255)        # camera-2 input video (<prefix>_<dataset>_VIDEO2.avi)
    timestamp_path: varchar(255)    # its timestamps (TS_<prefix>_<dataset>_CAMERA2.npy)
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
            # Camera 2's recording resolution; visual_roi below is a position in
            # this frame, so another size (another camera's video) cannot be
            # cropped.
            if (width, height) != (640, 480):
                problems.append(
                    f"video is {width}x{height}, camera {INPUT_VIDEO_CAMERA} records "
                    "640x480: another camera's video?"
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
                    # Mouse-view panel (bottom-left screen) in the 640x480 frame:
                    # the batch2 OBS panel (ObsVideoLayout) scaled from 1920x1080
                    # (x / 3, y * 4 / 9), down to the bottom edge.
                    "visual_roi": (0, 243, 316, 237),
                    "sync_roi": sync_roi,
                    "seek_offset": measure_seek_offset(video_path),
                    "timestamps": timestamps,
                }
            )
        except Exception as err:
            _record_failure(key["dataset"], self.__class__.__name__, err)
            return None


@schema
class AlignmentParams(dj.Lookup):
    """Parameters of StepVideoFrame.make: what each does and why its value.

    Each column's comment says what it changes and where its value comes from
    (``AlignmentParams.heading``). StepVideoFrame (and FrameVisibility) hold one
    row per session and parameter set, like the decision tables with
    ``ModelParams``: every set here is populated for every session. A set's
    values never change once populated: add a new set instead.
    """

    definition = """
    params_version: int16
    ---
    description: varchar(255)  # what changed from the previous version
    min_sync_match: float64  # camera videos rejected below this fraction of sync square edges matching photodiode edges (wrong recording). Judgement call, not measured: compare with StepVideoFrame.sync_match_fraction
    min_step_coverage: float64  # rejected below this fraction of game steps inside the video (another session's video, cut recording). Judgement call, not measured
    generated_signal_display_delay: float64  # s, OBS without photodiode: added to the generated sync signal's send times (PROC). Measured on Xestia_2026-08-21_1: 62 ms, within ~2 ms of the photodiode
    display_lag_trials: int16  # display lag: trial starts measured, spread over the session. Judgement call: jitter ~1 refresh (17 ms), so the median of 40 is within a few ms
    min_display_lag_trials: int16  # display lag: with fewer clear scene changes, default_display_lag is used. Judgement call: fewer is not robust to one wrong detection
    default_display_lag: float64  # s, display lag when it cannot be measured. Measured on Xestia_2026-07-30_1: 54 ms (44-61 ms 10th-90th percentile)
    max_display_lag: float64  # s, a lag outside (0, this) means misaligned video: the session fails. Lags measured so far are 49-54 ms
    max_display_lag_spread: float64  # s, trial starts' lags spread more (median absolute deviation) means misaligned video: the session fails. Correct sessions jitter ~1 refresh (17 ms); 25 ms is 1.5 refreshes
    lag_search_before: float64  # s, display lag: video read from this long before each trial start step's frame, so an early change (negative lag, misaligned) is seen and rejected
    lag_search_after: float64  # s, display lag: video read up to this long after each start step's frame. Must hold the change even in a misaligned video so it is rejected, not missed: 2.5x max_display_lag
    scene_onset_margin: float64  # s, trial scene onsets searched up to the session display_lag plus this. 4x max_display_lag_spread; short because the largest change in the window wins (fast turns)
    scene_change_min_change: float64  # grey levels, a trial start's scene change must change the 80x60 panel thumbnail by this much on average. Judgement call: a switch changes it by tens of levels
    scene_change_min_contrast: float64  # the scene change must be this many times the window's median frame-to-frame change. Judgement call: separates switches from the mouse's own movement
    """
    contents = [
        dict(
            params_version=1,
            description=(
                "Constants of commit 466a3ab7 (2026-11-02); lag search window in "
                "seconds; trial scene onsets searched up to display lag + margin"
            ),
            min_sync_match=0.8,
            min_step_coverage=0.9,
            generated_signal_display_delay=0.062,
            display_lag_trials=40,
            min_display_lag_trials=5,
            default_display_lag=0.054,
            max_display_lag=0.2,
            max_display_lag_spread=0.025,
            lag_search_before=0.1,
            lag_search_after=0.5,
            scene_onset_margin=0.1,
            scene_change_min_change=2.0,
            scene_change_min_contrast=10.0,
        ),
    ]


@schema
class StepVideoFrame(dj.Computed):
    """Input video frame of each game step, for OBS and camera recordings alike.

    ``frame_ids[i]`` is the frame showing game step ``i`` on screen, the one the
    mouse reacts to: the first frame captured at or after ``step_time[i] +
    display_lag``. ``step_frame_ids[i]`` is the first frame captured at or after
    the step's own time, which still shows earlier steps. -1 outside the video.
    Frames are indexed in ``video_path`` and cropped to ``visual_roi`` by
    ``get_frame``. ``display_lag`` is measured per session at the trial starts,
    and also checks the alignment: a lag outside (0, ``max_display_lag``) s
    means misaligned frames. Each trial's own scene onset is stored too
    (``scene_onset_frames``): single trials reach the screen about a refresh
    before or after the session's lag. The parameters used are in
    ``AlignmentParams``; one row per session and parameter set
    (``params_version``), so restrict to a version when several exist.

    The step's content comes from the pose the task read at the step; that pose
    was captured by the DLC camera earlier still (~94 ms before the screen on
    Xestia_2026-07-30_1, vs 54 ms for display_lag).

    Clocks:

    - camera (3-camera setup): matched on the camera timestamps
      (``State.start_time + step_time``, same host clock).
    - obs (old setup): sync square edges in the recording are matched with
      photodiode edges to fit video time = offset + drift * game time (see
      ``align_steps_to_frames_by_photodiode``), photodiode from
      ``vr4mice.SignalsPhotodiode``. pulse_geo trains are anchored on their
      irregular intervals; regular "pulse" trains (batch1) on their first edge,
      so the recording must start before the pulses.
    - obs without photodiode (align_method "generated_signal"): the same fit on
      the generated sync signal that drives the square (PROC send times from
      ``dlc.DLCProcessor``, plus ``generated_signal_display_delay``, stored in
      ``generated_signal_delay``), so frames match photodiode-aligned sessions
      up to the delay's variation.
    """

    definition = """
    -> vr4mice.State                    # game steps
    -> AlignmentParams                  # parameters used
    ---
    video_source: enum('obs', 'camera') # recording setup of the input video
    align_method: enum('photodiode', 'timestamps', 'generated_signal') # how frames were matched to steps
    video_path: varchar(255)            # video indexed by frame_ids
    visual_roi: <blob>                  # (x, y, w, h) mouse-view panel, cropped on read
    seek_offset: int32                  # frames cv2 seeking lands from the requested one
    n_steps: int32                      # number of game steps
    step: <blob>                        # step indices (State.step)
    step_time: <blob>                   # step times, game seconds (State.step_time)
    step_video_time: <blob>             # each step's time on the video clock (s): camera timestamps, or the residual-corrected OBS fit (frame / fps); NaN outside the video
    frame_ids: <blob>                   # frame showing each step on screen (step_time + display_lag), -1 outside the video
    step_frame_ids: <blob>              # frame captured at each step's time (no display lag), -1 outside the video
    display_lag: float64                # step to screen delay (s), median over trial starts
    display_lag_trials: int32           # trial starts measured (0 when default_display_lag is used)
    trial_start_steps: <blob>           # step index of each trial start (first non-ITI step after an ITI)
    scene_onset_frames: <blob>          # per trial start: first frame showing the trial's scene, -1 without a clear change
    scene_onset_delay: <blob>           # per trial start: time (s) from the start step to that frame (video clock), NaN without one
    n_steps_outside_video: int32        # steps without a frame (frame_ids == -1)
    pair_count=null: int32              # obs: paired sync/photodiode edges
    rms=null: float64                   # obs: residual RMS of the edge fit (s)
    offset=null: float64                # obs: video time at game time 0 (s)
    drift=null: float64                 # obs: video/game clock rate
    median_abs_gap=null: float64        # camera: median |frame time - step time| (s)
    sync_match_fraction=null: float64   # video sync edges matching photodiode edges
    generated_signal_delay=null: float64 # generated_signal: delay added to send times (s)
    """

    @property
    def key_source(self):
        # Wait for the session's PROC (dlc.DLCProcessor, populated before
        # SignalsPhotodiode in the same run): it can arrive after the pickle, and
        # aligning before it would skip the photodiode check for good.
        from vr4mice.schema import dlc

        keys = InputVideo.fetch("KEY") + RawVideoSync.fetch("KEY")
        sessions = vr4mice.State.proj() & keys & dlc.DLCProcessor.proj()
        return sessions * AlignmentParams.proj()

    def make(self, key):
        """Match each game step to an input video frame and store QA."""
        from vr4mice.analysis.inputs_videos import align_steps_to_frames_by_timestamps

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        # Missing inputs that are added later (a new batch): not a failure,
        # or FailedSession would skip the session for good. Retried next time.
        missing = None if InputVideo & key else self._obs_layout_missing(key)
        if missing:
            logger.warning(
                "Skipping %s for %s until %s",
                self.__class__.__name__,
                key["dataset"],
                missing,
            )
            return

        try:
            params = (AlignmentParams & key).fetch1()
            start_time, step, step_time = (vr4mice.State & key).fetch1(
                "start_time", "step", "step_time"
            )
            start_time = float(np.ravel(start_time)[0])
            step_time = np.asarray(step_time, dtype=float)

            if InputVideo & key:
                row = self._align_camera(key, start_time, step_time, params)
            else:
                row = self._align_obs(key, start_time, step_time, params)

            # Steps and frames on the video clock (s); frames shown on screen.
            # step_video_time is kept so lookups match frame_ids (OBS: includes
            # the residual correction for dropped frames).
            step_video_time = row["step_video_time"]
            frame_times = row.pop("frame_times")
            row["step_frame_ids"] = row.pop("frame_ids")
            lag, n_trials = self._measure_display_lag(
                key, row, step_video_time, frame_times, params
            )
            row["frame_ids"] = align_steps_to_frames_by_timestamps(
                step_video_time + lag, frame_times
            )
            row["display_lag"] = lag
            row["display_lag_trials"] = n_trials
            row.update(
                self._measure_scene_onsets(
                    key, row, step_video_time, frame_times, params
                )
            )

            frame_ids = row["frame_ids"]
            n_outside = int((frame_ids < 0).sum())
            coverage = 1 - n_outside / max(len(frame_ids), 1)
            if coverage < params["min_step_coverage"]:
                raise ValueError(
                    f"{pathlib.Path(row['video_path']).name} covers {coverage:.1%} "
                    f"of the game steps ({len(step_time)} steps over "
                    f"{step_time[-1] - step_time[0]:.0f} s; minimum "
                    f"{params['min_step_coverage']:.0%}): another session's "
                    "video, or a cut recording?"
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
    def _obs_layout_missing(key):
        """What an OBS session still lacks to know its mouse-view panel, or None."""
        batch = vr4mice.DatasetBatch & key
        if not batch:
            return "it has a DatasetBatch row (run vr4mice.DatasetBatch.populate())"
        batch_name = batch.fetch1("batch_name")
        if not ObsVideoLayout & {"batch_name": batch_name}:
            return (
                f"ObsVideoLayout has a row for {batch_name} (its mouse-view panel "
                "in the recordings)"
            )
        return None

    @staticmethod
    def _scene_changes(row, frames, frame_times, before, after, params):
        """``find_scene_changes`` at ``frames``, from ``before`` frames to ``after`` s.

        ``after`` is converted to frames with the video's median frame interval.
        """
        from vr4mice.analysis.inputs_videos import find_scene_changes

        frame_interval = float(np.median(np.diff(frame_times)))
        return find_scene_changes(
            row["video_path"],
            row["visual_roi"],
            frames,
            seek_offset=row["seek_offset"],
            before=before,
            after=int(np.ceil(after / frame_interval)),
            min_change=params["scene_change_min_change"],
            min_contrast=params["scene_change_min_contrast"],
        )

    @classmethod
    def _measure_display_lag(cls, key, row, step_video_time, frame_times, params):
        """Step to screen delay (s) and trial starts measured (``AlignmentParams``).

        The median of (frame of the scene change - start step time) over up to
        ``display_lag_trials`` trial starts, where the scene switches at once.
        """
        from vr4mice.analysis.inputs_videos import trial_start_steps

        step_frame_ids = np.asarray(row["step_frame_ids"])
        frame_times = np.asarray(frame_times, dtype=float)
        iti = np.asarray((vr4mice.MouseState & key).fetch1("iti"), dtype=float).ravel()
        n = min(len(iti), len(step_frame_ids))
        starts = trial_start_steps(iti[:n])
        starts = starts[step_frame_ids[starts] >= 0]
        n_trials = int(params["display_lag_trials"])
        if len(starts) > n_trials:
            starts = starts[
                np.unique(np.linspace(0, len(starts) - 1, n_trials).astype(int))
            ]
        changes = []
        if len(starts) and len(frame_times) > 1:
            frame_interval = float(np.median(np.diff(frame_times)))
            changes = cls._scene_changes(
                row,
                step_frame_ids[starts],
                frame_times,
                before=int(np.ceil(params["lag_search_before"] / frame_interval)),
                after=params["lag_search_after"],
                params=params,
            )
        # The scene switched between frame j - 1 (old scene) and j: timed at
        # their midpoint, as sync edges, not half a frame late at frame j
        lags = np.array(
            [
                (frame_times[j - 1] + frame_times[j]) / 2 - step_video_time[s]
                for s, j in zip(starts, changes)
                if j is not None and 0 < j < len(frame_times)
            ]
        )
        if len(lags) < params["min_display_lag_trials"]:
            logger.warning(
                "%s: display lag measured at %d trial starts only, using %.0f ms",
                key["dataset"],
                len(lags),
                params["default_display_lag"] * 1000,
            )
            return params["default_display_lag"], 0
        lag = float(np.median(lags))
        spread = float(np.median(np.abs(lags - lag)))
        max_lag, max_spread = (
            params["max_display_lag"],
            params["max_display_lag_spread"],
        )
        if not 0 < lag < max_lag or spread > max_spread:
            raise ValueError(
                f"Trial starts appear {lag * 1000:.0f} ms (spread "
                f"{spread * 1000:.0f} ms, {len(lags)} trials) after their steps "
                f"in {pathlib.Path(row['video_path']).name}; expected 0-"
                f"{max_lag * 1000:.0f} ms, spread under "
                f"{max_spread * 1000:.0f} ms: misaligned video?"
            )
        return lag, len(lags)

    @classmethod
    def _measure_scene_onsets(cls, key, row, step_video_time, frame_times, params):
        """Columns with the frame and delay of every trial's scene onset.

        Found like the display lag (largest scene change after the start step's
        frame), from the frame before the start step's (so a change on that
        frame is seen) to ``display_lag + scene_onset_margin`` after it.
        """
        from vr4mice.analysis.inputs_videos import scene_onsets, trial_start_steps

        step_frame_ids = np.asarray(row["step_frame_ids"])
        frame_times = np.asarray(frame_times, dtype=float)
        iti = np.asarray((vr4mice.MouseState & key).fetch1("iti"), dtype=float).ravel()
        starts = trial_start_steps(iti[: min(len(iti), len(step_frame_ids))])
        changes = [None] * len(starts)
        in_video = np.flatnonzero(step_frame_ids[starts] >= 0)
        if len(in_video) and len(frame_times) > 1:
            found = cls._scene_changes(
                row,
                step_frame_ids[starts[in_video]],
                frame_times,
                before=1,  # a change between this frame and the start's is seen
                after=row["display_lag"] + params["scene_onset_margin"],
                params=params,
            )
            for i, frame in zip(in_video, found):
                changes[i] = frame
        onset_frames, delays = scene_onsets(
            starts, changes, step_video_time, frame_times
        )
        return {
            "trial_start_steps": starts,
            "scene_onset_frames": onset_frames,
            "scene_onset_delay": delays,
        }

    @staticmethod
    def _frame_times(key, source):
        """Each input video frame's time on the video clock (s)."""
        if source == "camera":
            return np.asarray((InputVideo & key).fetch1("timestamps"), dtype=float)
        fps, n_frames = (RawVideoSync & key).fetch1("fps", "n_frames")
        return np.arange(n_frames) / fps

    @staticmethod
    def _align_camera(key, start_time, step_time, params):
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
            if sync_match < params["min_sync_match"]:
                raise ValueError(
                    f"{pathlib.Path(video_path).name}: sync square edges at the "
                    f"camera timestamps match the photodiode for {sync_match:.0%} "
                    f"of {check['n_edges']} edges (median gap "
                    f"{check['median_gap'] * 1000:.0f} ms; minimum "
                    f"{params['min_sync_match']:.0%}): video and timestamps not "
                    "from the same recording, or another session?"
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
            "step_video_time": step_unix_times,
            "frame_times": np.asarray(timestamps, dtype=float),
        }

    @staticmethod
    def _align_obs(key, start_time, step_time, params):
        """OBS recording: match steps to frames with the photodiode sync edges.

        Without a photodiode, the generated sync signal stands in for it.
        """
        from vr4mice.analysis.inputs_videos import (
            align_steps_to_frames_by_photodiode,
            binarize_sync_trace,
        )

        photodiode = vr4mice.SignalsPhotodiode & key
        if photodiode:
            sync_time, sync_level, signal_type = photodiode.fetch1(
                "photodiode_time", "photodiode_read", "signal_type"
            )
            align_method, display_delay = "photodiode", None
            signal_options = {}
        else:
            sync_time, sync_level, signal_type = load_generated_signal(key)
            align_method = "generated_signal"
            display_delay = params["generated_signal_display_delay"]
            sync_time = sync_time + display_delay
            # clean 0/1 signal, possibly short pulses: no filter, min/max levels
            signal_options = {"pd_lowpass": False, "pd_level_percentiles": (0, 100)}
            logger.info(
                "%s: no photodiode, aligning on the generated sync signal",
                key["dataset"],
            )
        # Older PROC files have no signal_type; they used regular pulses
        signal_type = signal_type or "pulse"
        if signal_type not in ("pulse_geo", "pulse"):
            raise ValueError(
                f"Sync alignment needs a pulse or pulse_geo sync signal, "
                f"got {signal_type}"
            )
        sync_time = np.asarray(sync_time, dtype=float) - start_time
        if not (sync_time[0] < step_time[-1] and sync_time[-1] > step_time[0]):
            raise ValueError(
                f"{align_method} times ({sync_time[0]:.0f} to {sync_time[-1]:.0f} s "
                "game time) do not overlap the game steps: not on the game clock?"
            )
        # Present: checked by _obs_layout_missing before make's try
        batch_name = (vr4mice.DatasetBatch & key).fetch1("batch_name")
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
                # game time, the clock of step_time
                "time_stamp": sync_time,
                "photodiode_read": np.asarray(sync_level, dtype=float),
            }
        )
        frames, qa = align_steps_to_frames_by_photodiode(
            video_df,
            photodiode_df,
            step_time,
            regular_pulses=signal_type == "pulse",
            **signal_options,
        )
        # First frame at or after each step; -1 outside the recording
        frame_ids = np.full(len(step_time), -1, dtype=np.int64)
        inside = np.isfinite(frames)
        frame_ids[inside] = np.ceil(frames[inside] - 1e-9).astype(np.int64)
        frame_ids[(frame_ids < 0) | (frame_ids >= n_frames)] = -1
        return {
            "video_source": "obs",
            "align_method": align_method,
            "generated_signal_delay": display_delay,
            "video_path": video_path,
            "visual_roi": visual_roi,
            "frame_ids": frame_ids,
            "seek_offset": seek_offset,
            "pair_count": int(qa["pair_count"]),
            "sync_match_fraction": qa["pair_fraction"],
            "rms": qa["rms"],
            "offset": qa["offset"],
            "drift": qa["drift"],
            # video clock: frame / fps, steps at their fitted (fractional) frame
            "step_video_time": frames / fps,
            "frame_times": np.arange(n_frames) / fps,
        }

    @classmethod
    def align_step_to_frames(cls, key, timepoints: list, displayed: bool = True):
        """Return the first input video frame at or after each query time.

        Timepoints are in the ``State.step_time`` base and must lie within the
        session's step times (ValueError otherwise). Query times are mapped to
        the video clock by interpolating ``step_video_time``, the mapping
        ``frame_ids`` was built from, so a step's own time returns its
        ``step_frame_ids`` (or ``frame_ids`` when displayed) entry. When
        ``displayed`` is True, the display lag is added on the recording clock.
        Returns None for a query outside the input video.
        """
        from vr4mice.analysis.inputs_videos import align_steps_to_frames_by_timestamps

        step_time, step_video_time, source, display_lag = (cls & key).fetch1(
            "step_time", "step_video_time", "video_source", "display_lag"
        )
        step_time = np.asarray(step_time, dtype=float)
        min_time, max_time = np.min(step_time), np.max(step_time)

        for tp in timepoints:
            if not isinstance(tp, (int, float)):
                raise TypeError(f"Timepoint {tp} is not a number.")
            if not min_time <= tp <= max_time:
                raise ValueError(
                    f"Timepoint {tp} is out of bounds. Valid range: [{min_time:.3f}, {max_time:.3f}] seconds."
                )

        query_times = np.asarray(timepoints, dtype=float)
        if not query_times.size:
            return []

        frame_times = cls._frame_times(key, source)

        # Piecewise linear between steps; NaN next to steps outside the video
        order = np.argsort(step_time, kind="stable")
        video_times = np.interp(
            query_times,
            step_time[order],
            np.asarray(step_video_time, dtype=float)[order],
        )
        if displayed:
            video_times += display_lag
        frames = align_steps_to_frames_by_timestamps(video_times, frame_times)
        return [int(frame) if frame >= 0 else None for frame in frames]

    @classmethod
    def trial_frames(cls, key, trial: int, decision_xy=None) -> dict:
        """Displayed frames at the initiation, decision and end of a trial.

        Steps come from ``base_analysis.DataFrame`` (trial, iti, reward, x, y).
        Initiation is the trial's first non-ITI step; Decision the active step
        closest to ``decision_xy`` (x, y of ``DecisionPoints10Windows``), left
        out when None; Reward the first rewarded step, or "End (no reward)" the
        last active step of an unrewarded trial.

        Returns:
            {label: frame index (``frame_ids``), or None outside the video}
        """
        from vr4mice.schema.base_analysis import DataFrame

        df = DataFrame().get_data(
            key=key, columns=["step_time", "trial", "iti", "reward", "x", "y"]
        )
        if df is None or df is False:
            raise ValueError(f"No base_analysis.DataFrame for {key}")
        step_time, frame_ids = (cls & key).fetch1("step_time", "frame_ids")
        steps = pd.merge_asof(
            df.sort_values("step_time").reset_index(drop=True),
            pd.DataFrame(
                {
                    "step_time": np.asarray(step_time, dtype=float),
                    "frame_id": np.asarray(frame_ids),
                }
            ),
            on="step_time",
            direction="nearest",
        )
        in_trial = steps[steps["trial"] == trial]
        active = in_trial[in_trial["iti"] == 0]
        if active.empty:
            raise ValueError(f"Trial {trial} has no active steps in {key}")

        frames = {"Initiation": active["frame_id"].iloc[0]}
        if decision_xy is not None:
            x, y = (float(v) for v in decision_xy)
            distance = np.hypot(active["x"] - x, active["y"] - y)
            frames["Decision"] = active["frame_id"].loc[distance.idxmin()]
        rewarded = in_trial[in_trial["reward"] > 0]
        if len(rewarded):
            frames["Reward"] = rewarded["frame_id"].iloc[0]
        else:
            frames["End (no reward)"] = active["frame_id"].iloc[-1]
        return {k: (int(f) if f >= 0 else None) for k, f in frames.items()}

    @classmethod
    def plot_trial_frames(
        cls, key, trial: int, decision_xy=None, axes=None, size="common"
    ):
        """Plot the displayed frames of ``trial_frames`` (one axis per frame).

        Args:
            key: StepVideoFrame key.
            trial: Trial number (``base_analysis.DataFrame.trial``).
            decision_xy: (x, y) of the decision point, or None.
            axes: Axes to draw in (as many as frames); new figure when None.
            size: (width, height) of the panels, see ``get_frame``.

        Returns:
            The axes.
        """
        import matplotlib.pyplot as plt

        frames = cls.trial_frames(key, trial, decision_xy)
        if axes is None:
            _, axes = plt.subplots(1, len(frames), figsize=(4 * len(frames), 2.6))
        for ax, (label, frame) in zip(np.ravel(axes), frames.items()):
            ax.axis("off")
            if frame is None:
                ax.set_title(f"{label}\n(outside the video)")
                continue
            ax.imshow(cls.get_frame(key, frame, size=size)[..., ::-1])  # BGR -> RGB
            ax.set_title(label)
        return axes

    @classmethod
    def get_frame(cls, key, frame_index: int, size="common"):
        """Return the mouse-view panel of frame `frame_index` (BGR, as read by OpenCV).

        Args:
            key: StepVideoFrame key.
            frame_index: Frame in ``video_path`` (from ``frame_ids``).
            size: (width, height) of the returned panel; "common" for the
                largest OBS panel (``ObsVideoLayout``, batch2: 948x535), the same
                for every setup so frames compare directly (the 316x237 camera
                panel, squeezed from 16:9 into 640x480, is stretched back); None
                for the native crop.
        """
        from vr4mice.analysis.inputs_videos import (
            crop_frame,
            read_video_frame,
            resize_frame,
        )

        video_path, visual_roi, seek_offset = (cls & key).fetch1(
            "video_path", "visual_roi", "seek_offset"
        )
        frame = read_video_frame(video_path, frame_index, seek_offset=seek_offset)
        panel = crop_frame(frame, visual_roi)
        if size is None:
            return panel
        if isinstance(size, str) and size == "common":
            rois = ObsVideoLayout.fetch("visual_roi")
            size = max((int(roi[2]), int(roi[3])) for roi in rois)
        return resize_frame(panel, size)


@schema
class FrameVisibility(dj.Computed):
    """Step-aligned visibility of the target and distractor in contrast videos.

    Pixel counts refer to a 316×237 panel for both video sources. Surface novelty
    is a fraction of the predicted 2-D silhouette first seen in the trial.
    Populated by the input video pipeline on machines with access to the recordings.
    """

    definition = """
    -> StepVideoFrame
    ---
    descriptors: <blob>  # aligned column arrays for steps with a displayed frame
    calibration: <blob>  # panel geometry, segmentation parameters and sample frames
    surface_fit: <blob>   # per-object fit status and fitted silhouette coefficients
    """

    @property
    def key_source(self):
        from vr4mice.schema.decision import SessionLabel

        labels = (SessionLabel & self._contrast_sets).fetch("KEY")
        return StepVideoFrame.proj() & (vr4mice.Dataset & labels).proj()

    _contrast_sets = [
        {"set_name": "contrast_white_target"},
        {"set_name": "contrast_black_target"},
    ]

    def make(self, key, *, frame_workers=1):
        """Populate one supported session and record session-specific failures."""
        from vr4mice.analysis.frame_visibility import validate_frame_workers
        from vr4mice.schema.decision import SessionLabel

        table_name = self.__class__.__name__
        if vr4mice.FailedSession.should_skip(key, table_name, logger):
            return

        label = (vr4mice.Dataset & key).fetch1("session_label")
        contrast = SessionLabel & {"session_label": label} & self._contrast_sets
        if not contrast:
            logger.warning(
                "Skipping FrameVisibility for %s: unsupported task %s",
                key["dataset"],
                label,
            )
            return

        set_name, stage_name = contrast.fetch1("set_name", "stage_name")
        frame_workers = validate_frame_workers(frame_workers)
        try:
            self._make_session(key, label, set_name, stage_name, frame_workers)
        except Exception as err:
            _record_failure(key["dataset"], table_name, err)

    def _make_session(self, key, label, set_name, stage_name, frame_workers):
        from vr4mice.analysis.frame_visibility import PANEL_SIZE, describe_steps
        from vr4mice.analysis.inputs_videos import iter_video_panels

        video = (StepVideoFrame & key).fetch1()
        steps = np.asarray(video["step"], dtype=np.int64).ravel()
        times = np.asarray(video["step_time"], dtype=float).ravel()
        if steps.size != times.size or steps.size != np.size(video["frame_ids"]):
            raise ValueError(
                "Step and time arrays must align with the displayed-frame mapping"
            )
        episode, occlusion_type = (vr4mice.State & key).fetch1(
            "episode", "occlusion_type"
        )
        iti, x, z, target_left = (vr4mice.MouseState & key).fetch1(
            "iti", "x_pos", "z_pos", "obj_left"
        )
        gui = vr4mice.GuiParams & key
        distractor = gui.fetch1("distractor") if gui else None
        has_distractor = not label.startswith(("ar_det_", "ar_detection_"))
        if distractor is not None and np.size(distractor):
            flags = np.asarray(distractor, dtype=float)
            known = np.isfinite(flags)
            if known.any():
                has_distractor = bool(np.any(flags[known] != 0))
        has_occluders = stage_name in ("dual_occlusion", "multi_occlusion")
        if occlusion_type is not None and np.size(occlusion_type):
            modes = np.asarray(occlusion_type, dtype=float)
            if np.isfinite(modes).any():
                has_occluders = bool(np.any(np.isfinite(modes) & (modes != 0)))

        def read_panels(frame_ids):
            for panel in iter_video_panels(
                video["video_path"],
                frame_ids,
                video["visual_roi"],
                PANEL_SIZE,
                seek_offset=video["seek_offset"],
            ):
                yield cv2.cvtColor(panel, cv2.COLOR_BGR2RGB)

        descriptors, calibration, surface_fit = describe_steps(
            read_panels,
            video["frame_ids"],
            episode,
            iti,
            np.column_stack((np.ravel(x), np.ravel(z))),
            target_left,
            target_is_white=set_name == "contrast_white_target",
            has_distractor=has_distractor,
            has_occluders=has_occluders,
            frame_workers=frame_workers,
        )
        step_index = descriptors["step_index"]
        descriptors.update(step=steps[step_index], step_time=times[step_index])
        self.insert1(
            {
                **key,
                "descriptors": descriptors,
                "calibration": calibration,
                "surface_fit": surface_fit,
            }
        )

    def fetch_dataframe(self):
        """Return the descriptor rows for a restriction to one dataset."""
        return pd.DataFrame(self.fetch1("descriptors"))

    def trial_progress(self):
        """Return visibility on the InterpolatedTrials samples of each trial.

        Sample times come from ``interpolated_trajectories.TrialSampleTimes``,
        so ``trial_step`` is the same moment as in InterpolatedTrials. Each
        sample takes the frame on screen at its time (``display_lag`` after the
        frame's step).

        Returns:
            One row per dataset, ``params_version``, trial and ``trial_step``
            (``trial_length * n_points``) with the sample's ``step_time``, the ``t_px``, ``d_px``
            and ``total_visible_px`` of the frame on screen (NaN without a
            frame), and ``scene_shown``: False while the screen still shows the
            previous scene (display lag and the trial's own scene onset,
            ``StepVideoFrame.scene_onset_frames``; the display lag alone for
            trials without a detected onset). Sessions without TrialSampleTimes
            are skipped.
        """
        from vr4mice.analysis.frame_visibility import (
            trial_scene_shown,
            visibility_at_times,
        )
        from vr4mice.schema.interpolated_trajectories import TrialSampleTimes

        keys = self.fetch("KEY")
        with_samples = (self & TrialSampleTimes).fetch("KEY")
        if len(with_samples) < len(keys):
            logger.warning(
                "%d of %d sessions have no TrialSampleTimes yet: populate it",
                len(keys) - len(with_samples),
                len(keys),
            )
        parts = []
        for key in with_samples:
            trial, trial_step, sample_time = (TrialSampleTimes & key).fetch1(
                "trial", "trial_step", "step_time"
            )
            descriptors = (self & key).fetch1("descriptors")
            step_time, display_lag, starts, onset_frames = (
                StepVideoFrame & key
            ).fetch1(
                "step_time", "display_lag", "trial_start_steps", "scene_onset_frames"
            )
            iti = np.asarray(
                (vr4mice.MouseState & key).fetch1("iti"), dtype=float
            ).ravel()
            values = visibility_at_times(
                descriptors,
                step_time,
                sample_time,
                display_lag=display_lag,
                columns=("t_px", "d_px", "total_visible_px", "frame_id", "step_index"),
            )
            shown_frames = values.pop("frame_id")
            shown_steps = values.pop("step_index")
            values["scene_shown"] = trial_scene_shown(
                sample_time,
                shown_frames,
                shown_steps,
                step_time,
                iti,
                starts,
                onset_frames,
            )
            parts.append(
                pd.DataFrame(
                    {
                        "dataset": key["dataset"],
                        "params_version": key["params_version"],
                        "trial": np.asarray(trial, dtype=np.int64),
                        "trial_step": np.asarray(trial_step, dtype=np.int64),
                        "step_time": np.asarray(sample_time, dtype=float),
                        **values,
                    }
                )
            )
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
