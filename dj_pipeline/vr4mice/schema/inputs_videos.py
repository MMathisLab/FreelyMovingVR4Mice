"""Video input schema for sync/crop/align operations on session recordings."""

import os
import pathlib
from typing import Tuple

import cv2
import datajoint as dj
import numpy as np
import pandas as pd
import scipy.interpolate

from vr4mice.schema import vr4mice
from vr4mice.schema.vr4mice import State
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "inputs_videos"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class RawVideo(dj.Imported):
    """Stores the raw OBS recording path for a dataset."""

    definition = """
    -> vr4mice.Dataset             # source dataset key
    ---
    video_path: varchar(255)       # absolute path to the raw OBS recording
    """

    # NOTE(celia): to update the default path when we put the videos onto the server
    def make(self, key, base_path: str = "/vr4mice_screen_recordings"):
        """Insert raw OBS recording path for a dataset."""
        from vr4mice.actions.populate_rig import get_files_paths

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        logger.info(f"{key['dataset']}")
        paths = get_files_paths(key["dataset"])
        video_filepath = f"{paths['screen_recording_output']['dst']}/{paths['screen_recording_output']['filename']}"

        try:
            if not pathlib.Path(video_filepath).exists():
                raise FileNotFoundError(f"Video file not found: {video_filepath}")

            self.insert1({**key, "video_path": video_filepath})
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class ProcessedVideo(dj.Computed):
    """Stores cropped/truncated OBS videos and ROI metadata."""

    definition = """
    -> RawVideo                    # source raw video
    ---
    visual_video_path: varchar(255)  # cropped visual ROI video path
    sync_video_path: varchar(255)    # cropped sync ROI video path
    img_validation_path: varchar(255) # path to validation frame JPEGs
    start_frame: int                # session start frame index (raw video)
    end_frame: int                  # session end frame index (raw video)
    visual_roi: blob                # (x,y,w,h) for visual ROI in raw video coords
    sync_roi: blob                  # (x,y,w,h) for sync ROI in raw video coords
    """

    def make(
        self,
        key,
        visual_roi: Tuple[int] = (0, 570, 925, 510),
        sync_roi: Tuple[int] = (1895, 580, 2, 2),
    ):
        """
        Args:
            visual_roi: (x, y, wx, wy) with x and y the positions of the start of the roi
                and wx and wy the widths of the roi. The visual ROI should correspond the
                bottom right screen of the OBS video
            sync_roi: (x, y, wx, wy) with x and y the positions of the start of the roi
                and wx and wy the widths of the roi. The sync ROI is 2 x 2 pixels in the
                top left corner of bottom left screen on the OBS video
        """
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            from vr4mice.analysis.inputs_videos import VideoTrimmer

            video_path = (RawVideo & key).fetch1("video_path")
            trimmer = VideoTrimmer(video_path, session_start_buffer=10)

            (
                visual_video_path,
                sync_video_path,
                validation_path,
                start,
                end,
            ) = trimmer.auto_trim_video(visual_roi, sync_roi, sample_center_size=20)

            self.insert1(
                {
                    **key,
                    "visual_video_path": visual_video_path,
                    "sync_video_path": sync_video_path,
                    "img_validation_path": validation_path,
                    "start_frame": start,
                    "end_frame": end,
                    "visual_roi": visual_roi,
                    "sync_roi": sync_roi,
                }
            )
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_visual_frame(self, key, frame_index: int):
        """Return the frame at `frame_index` from the visual video.

        Note: This method raises exceptions (FileNotFoundError, IOError, IndexError, RuntimeError).
        If calling from pipeline code, wrap in try-except and log errors appropriately.
        """
        visual_path = (self & key).fetch1("visual_video_path")

        if not os.path.exists(visual_path):
            raise FileNotFoundError(f"Video path does not exist: {visual_path}")

        cap = cv2.VideoCapture(visual_path)
        if not cap.isOpened():
            raise IOError(f"Failed to open video file: {visual_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if not (0 <= frame_index < total_frames):
            cap.release()
            raise IndexError(
                f"frame_index {frame_index} out of bounds (0 to {total_frames - 1})"
            )

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = cap.read()
        cap.release()

        if not success or frame is None:
            raise RuntimeError(f"Could not read frame {frame_index} from {visual_path}")

        return frame


@schema
class VideoSyncSignal(dj.Computed):
    """Extracts the binary sync trace from the sync ROI video."""

    definition = """
    -> ProcessedVideo             # cropped sync ROI video
    ---
    video_fps: float              # FPS of the sync video
    total_frames: int             # frame count of the sync video
    frame_ids: longblob           # frame indices (0-based)
    timestamps: longblob          # frame timestamps in seconds
    signals: longblob             # binary sync signal per frame (0/1)
    """

    def make(self, key):
        """Extract and store the sync signal trace from the sync ROI video."""
        from vr4mice.analysis.inputs_videos import extract_sync_signal_from_video

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            sync_path = (ProcessedVideo & key).fetch1("sync_video_path")
            frame_ids, timestamps, signals, fps, total = extract_sync_signal_from_video(
                sync_path
            )

            if np.unique(signals).size < 2:
                raise ValueError(
                    f"Sync signal in {sync_path} is not binary, check the sync ROI."
                )

            self.insert1(
                {
                    **key,
                    "video_fps": fps,
                    "total_frames": total,
                    "frame_ids": frame_ids,
                    "timestamps": timestamps,
                    "signals": signals,
                }
            )
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    @classmethod
    def get_sync_df(cls, key):
        data = (cls & key).fetch1()
        return pd.DataFrame(
            {
                "frame_ids": data["frame_ids"],
                "timestamps": data["timestamps"],
                "signals": data["signals"],
            }
        )


@schema
class AlignedVideoFrame(dj.Computed):
    """Aligns game steps to video frames using photodiode when available; stores QA."""

    definition = """
    -> VideoSyncSignal              # sync ROI signal per frame
    -> State                        # game state (step, step_time, photodiode optional)
    ---
    n_steps: int                    # number of steps in the session
    step: longblob                  # step indices
    step_time: longblob             # step timestamps (seconds)
    frame_ids: longblob             # aligned video frame indices for each step
    align_path: varchar(32)         # 'photodiode' or 'fallback'
    pair_count: float               # number of matched edges (if photodiode path)
    rms: float                      # RMS residual of edge fit (seconds)
    offset: float                   # fitted time offset (seconds)
    drift: float                    # fitted drift factor
    align_error: varchar(255)       # error text if photodiode alignment failed
    """

    def make(self, key):
        """Align game steps to video frames and store alignment QA."""
        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            video_signal = VideoSyncSignal.get_sync_df(key)
            state_dict = (State() & key).fetch1()
            step_times = np.array(state_dict["step_time"], dtype=float)

            photodiode_df = None
            if "photodiode_time" in state_dict and "photodiode_read" in state_dict:
                photodiode_df = pd.DataFrame(
                    {
                        "time_stamp": np.array(
                            state_dict["photodiode_time"], dtype=float
                        ),
                        "photodiode_read": np.array(
                            state_dict["photodiode_read"], dtype=float
                        ),
                    }
                )

            from vr4mice.schema.vr4mice import SignalsPhotodiode

            # Check that SignalsPhotodiode has the attribute signal_type
            # else default to pulse
            signal_type = (SignalsPhotodiode & key).fetch1("signal_type")
            if signal_type is None:
                signal_type = "pulse"

            from vr4mice.analysis.inputs_videos import align_steps_to_frames

            frames, qa = align_steps_to_frames(
                video_sync_df=video_signal,
                photodiode_df=photodiode_df,
                step_times=step_times,
                signal_type=signal_type,
                use_photodiode=True,
            )

            self.insert1(
                {
                    **key,
                    "n_steps": len(state_dict["step"]) - 1,
                    "step": state_dict["step"],
                    "step_time": step_times,
                    "frame_ids": frames,
                    "align_path": qa.get("path", "fallback"),
                    "pair_count": qa.get("pair_count", np.nan),
                    "rms": qa.get("rms", np.nan),
                    "offset": qa.get("offset", np.nan),
                    "drift": qa.get("drift", np.nan),
                    "align_error": qa.get("error", ""),
                }
            )
        except Exception as err:
            dataset = key.get("dataset") if isinstance(key, dict) else None
            if dataset:
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    @classmethod
    def align_step_to_frames(cls, key, timepoints: list):
        """
        Given a list of timepoints (in seconds), return the corresponding video frame indices.

        If any timepoint is out of bounds (less than the minimum step_time or greater than
        the maximum step_time), a ValueError is raised.

        Args:
            key: dict, key to identify the AlignedVideoFrame entry
            timepoints: list of float, timepoints in seconds to align to video frames

        Returns:
            list of int or None: corresponding video frame indices for each timepoint
        """
        rec = (cls & key).fetch1()
        frame_ids = rec["frame_ids"]
        step_times = rec["step_time"]

        # Validate timepoints are within the valid time range
        min_time = np.min(step_times)
        max_time = np.max(step_times)

        for tp in timepoints:
            if not isinstance(tp, (int, float)):
                raise TypeError(f"Timepoint {tp} is not a number.")
            if tp < min_time or tp > max_time:
                raise ValueError(
                    f"Timepoint {tp} is out of bounds. Valid range: [{min_time:.3f}, {max_time:.3f}] seconds."
                )

        timepoints = np.array(timepoints, dtype=np.float64)

        # Interpolate: step_time (seconds) → frame_ids
        interp = scipy.interpolate.interp1d(
            step_times,
            frame_ids,
            bounds_error=False,
            fill_value="extrapolate",
        )
        return [int(tx) if not np.isnan(tx) else None for tx in interp(timepoints)]
