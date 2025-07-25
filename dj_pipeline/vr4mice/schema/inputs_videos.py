"""
Latency testing tables should be imported before this.
"""

import pathlib
import cv2
import datajoint as dj
import pandas as pd
import numpy as np
import scipy.interpolate
import pickle
import os

from vr4mice.schema.vr4mice import State, Dataset
from vr4mice.schema.latency_tests import SignalsPhotodiodeAligned
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "inputs_videos"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class RawVideo(dj.Imported):
    definition = """
    -> Dataset
    ---
    video_path: varchar(255)
    """

    # NOTE(celia): to update the default path when we put the videos onto the server
    def make(self, key, base_path: str = "/app/vr4mice/videos/full_videos/full"):
        dataset = key["dataset"]
        video_path = f"{base_path}/{dataset}.mkv"

        try:
            if not pathlib.Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            self.insert1({**key, "video_path": video_path})
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None


@schema
class ProcessedVideo(dj.Computed):
    definition = """
    -> RawVideo
    ---
    visual_video_path: varchar(255)
    sync_video_path: varchar(255)
    img_validation_path: varchar(255)
    start_frame: float
    end_frame: float
    visual_roi: blob
    sync_roi: blob
    """

    def make(self, key):
        from vr4mice.analysis.inputs_videos import VideoTrimmer

        video_path = (RawVideo & key).fetch1("video_path")

        # Define ROIs
        # The visual ROI should correspond the bottom right screen of the OBS video
        visual_roi = (0, 570, 930, 510)
        # NOTE(celia) 2x2 pixel of the ROI for lighter files
        # The sync ROI is 30 x 30 pixels in the top left corner of bottom left
        # screen on the OBS video
        sync_roi = (1895, 580, 2, 2)

        try:
            trimmer = VideoTrimmer(video_path, session_start_buffer=60)

            visual_video_path, sync_video_path, validation_path, start, end = (
                trimmer.auto_trim_video(visual_roi, sync_roi, sample_center_size=20)
            )

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
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_visual_frame(self, key, frame_index: int):
        """Return the frame at `frame_index` from the visual video."""
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
    """
    Extracts binary signal from sync ROI video (from ProcessedVideo).
    """

    definition = """
    -> ProcessedVideo
    ---
    video_fps: float
    total_frames: int
    frame_ids: longblob       # array of frame indices
    timestamps: longblob      # array of frame timestamps
    signals: longblob         # binary sync signal (0 or 1)
    """

    def make(self, key):
        from vr4mice.analysis.inputs_videos import extract_sync_signal_from_video

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
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    @classmethod
    def get_sync_df(cls, key):
        data = (cls & key).fetch1()
        import pandas as pd

        return pd.DataFrame(
            {
                "frame_ids": data["frame_ids"],
                "timestamps": data["timestamps"],
                "signals": data["signals"],
            }
        )


@schema
class AlignedVideoFrame(dj.Computed):
    """
    Aligns photodiode signal to video frames using sync video signal.
    """

    definition = """
    -> VideoSyncSignal
    -> State
    ---
    n_steps: int            # number of steps in the game
    step: longblob          # array of step indices corresponding to game time
    step_time: longblob       # array of step times corresponding to game time
    frame_ids: longblob      # array of video frame indices aligned to step times
    interpol_func: longblob     # interpolation function to align steps to video frames
    """

    def make(self, key):
        from vr4mice.analysis.inputs_videos import sync_video_to_photodiode

        # try:
        video_signal = VideoSyncSignal.get_sync_df(key)

        state_dict = (State() & key).fetch("step", "step_time", as_dict=True)[0]

        # NOTE(celia): if the photodiode signal was recorded for that session we align the video frames
        # to the photodiode signal to dlc time to game time (this is more precise)
        if len(SignalsPhotodiodeAligned() & key) > 0:
            # state_dict = (State() & key).fetch(
            #     "step", "step_time", as_dict=True
            # )[
            #     0
            # ]  # NOTE(celia): dict because step_time and dlc_read_time are not the same length

            photodiode_signal = pd.DataFrame(
                (SignalsPhotodiodeAligned() & key).fetch(
                    "time_stamp", "photodiode_read", "send_time", as_dict=True
                )[0]
            )
            _, _, original_frame_idx = sync_video_to_photodiode(
                video_signal, photodiode_signal[["time_stamp", "photodiode_read"]]
            )

            frames_and_dlc_aligned = pd.DataFrame(
                {
                    "frame_ids": original_frame_idx,
                    "send_time": photodiode_signal["send_time"],
                }
            )

            resampled_df = pd.merge_asof(
                pd.DataFrame(state_dict),
                frames_and_dlc_aligned,
                left_on="step_time",
                right_on="send_time",
                direction="backward",
            )
        # NOTE(celia): in some older sessions we don't have the photodiode signal
        # so we align the video frames to the game time directly (this is less precise
        # but still useful).
        else:
            resampled_df = pd.merge_asof(
                pd.DataFrame(state_dict),
                video_signal,
                left_on="step_time",
                right_on="timestamps",
                direction="forward",
            )

        timeinter_func = scipy.interpolate.interp1d(
            resampled_df["frame_ids"],
            resampled_df["step_time"],
            bounds_error=False,
            fill_value="extrapolate",
        )

        self.insert1(
            {
                **key,
                "n_steps": len(state_dict["step"]),
                "step": state_dict["step"],
                "step_time": np.array(list(resampled_df["step_time"].values)),
                "frame_ids": np.array(list(resampled_df["frame_ids"].values)),
                "interpol_func": pickle.dumps(timeinter_func),
            }
        )

        # except Exception as err:
        #     logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
        #     return None

    @classmethod
    def align_step_to_frames(cls, key, timepoints: list):
        """Aligns timepoints using interpolation, this should account for clock drift.

        Args:
            timepoints (list): List of timepoints to align.
        """
        interpol_func = pickle.loads((cls & key).fetch1("interpol_func"))

        for idx in timepoints:
            if not isinstance(idx, (int, float)):
                raise TypeError(f"Timepoint {idx} is not a number.")
            if idx < 0 or idx >= (cls & key).fetch1("n_steps"):
                raise ValueError(
                    f"Timepoint {idx} is out of bounds for the number of steps."
                )

        timepoints = np.array(timepoints, dtype=np.float64)
        return [
            int(tx) if not np.isnan(tx) else None for tx in interpol_func(timepoints)
        ]
