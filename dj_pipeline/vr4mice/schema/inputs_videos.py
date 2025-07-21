"""
Latency testing tables should be imported before this.
"""

import cv2
import datajoint as dj
import pandas as pd

from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "input_videos"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class RawVideo(dj.Manual):
    definition = """
    video_id: int
    ---
    video_path: varchar(255)
    recording_time: datetime
    """


@schema
class ProcessedVideo(dj.Computed):
    definition = """
    -> RawVideo
    ---
    visual_video_path: varchar(255)
    sync_video_path: varchar(255)
    start_frame: float
    end_frame: float
    visual_roi: blob
    sync_roi: blob
    """

    def make(self, key):
        from vr4mice.analysis.input_videos import VideoTrimmer

        video_path = (RawVideo & key).fetch1("video_path")

        # Define ROIs
        # The visual ROI should correspond the bottom right screen of the OBS video
        visual_roi = (0, 540, 950, 540)
        # NOTE(celia) 2x2 pixel of the ROI for lighter files
        # The sync ROI is 30 x 30 pixels in the top left corner of bottom left
        # screen on the OBS video
        sync_roi = (1900, 540, 2, 2)

        # Process
        trimmer = VideoTrimmer(video_path)
        visual_video_path, sync_video_path, start, end = trimmer.auto_trim_video(
            visual_roi,
            sync_roi,
            black_threshold=5,
            sample_center_size=20,
            validate=False,  # True would save an image for manual validation
        )

        self.insert1(
            {
                **key,
                "visual_video_path": visual_video_path,
                "sync_video_path": sync_video_path,
                "start_frame": start,
                "end_frame": end,
                "visual_roi": visual_roi,
                "sync_roi": sync_roi,
            }
        )

    def get_visual_frame(self, key, frame_index: int):
        """Return the frame at `frame_index` from the visual video."""
        visual_path = (self & key).fetch1("visual_video_path")

        cap = cv2.VideoCapture(visual_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if frame_index < 0 or frame_index >= total_frames:
            cap.release()
            raise IndexError(
                f"frame_index {frame_index} out of bounds (0 to {total_frames-1})"
            )

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        success, frame = cap.read()
        cap.release()

        if not success:
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
        from vr4mice.analysis.input_videos import extract_sync_signal_from_video

        sync_path = (ProcessedVideo & key).fetch1("sync_video_path")
        frame_ids, timestamps, signals, fps, total = extract_sync_signal_from_video(
            sync_path
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

    def get_sync_df(key):
        data = (VideoSyncSignal & key).fetch1()
        import pandas as pd

        return pd.DataFrame(
            {
                "frame": data["frame_ids"],
                "timestamp": data["timestamps"],
                "signal": data["signals"],
            }
        )


@schema
class AlignedVideoFrame(dj.Computed):
    """
    Aligns photodiode signal to video frames using sync video signal.
    """

    definition = """
    -> VideoSyncSignal
    -> SignalsPhotodiodeAligned
    -> State
    ---
    step_time: longblob       # array of step times corresponding to game time
    video_frame: longblob      # array of video frame indices aligned to step times
    """

    def make(self, key):
        from vr4mice.schema.latency_tests import SignalsPhotodiodeAligned
        from vr4mice.analysis.input_videos import (
            sync_video_to_photodiode,
            sync_video_to_game_time,
        )
        from vr4mice.schema.vr4mice import State

        # 1. Align to photodiode signal
        video_signal = pd.DataFrame(
            (VideoSyncSignal() & key).fetch("timestamps", "signal", as_dict=True)[0]
        )
        photodiode_signal = pd.DataFrame(
            (SignalsPhotodiodeAligned() & key).fetch(
                "time_stamp", "photodiode_read", as_dict=True
            )[0]
        )
        _, _, original_frame_idx = sync_video_to_photodiode(
            video_signal, photodiode_signal
        )

        # 2. Resample based on State
        frames_and_dlc_aligned = pd.DataFrame(
            {
                "original_frame_idx": original_frame_idx,
                "send_time": (SignalsPhotodiodeAligned() & key).fetch1("send_time"),
            }
        )
        state_dict = (State() & key).fetch(
            "step", "step_time", "dlc_read_time", as_dict=True
        )[0]

        resampled_data = sync_video_to_game_time(frames_and_dlc_aligned, state_dict)

        # 3. Create keys
        self.insert1(
            {
                **key,
                "step": state_dict["step"],
                "step_time": resampled_data["step_time"],
                "video_frame": resampled_data["video_frame"],
            }
        )
