import os
import numpy as np
import cv2
import pandas as pd
import pathlib

from vr4mice.analysis.latency_testing import find_rising_edges

# NOTE(celia): all recordings should be 120 fps (frame rate per second).

class VideoTrimmer:
    def __init__(
        self,
        input_video_path,
        session_start_buffer=10,
        black_threshold=5,
        consecutive_frames=5,
    ):
        """Initialize video trimmer

        Args:
            input_video_path: Path to input video file.
            session_start_buffer: Buffer in seconds to search for session start.
            black_threshold: Pixel intensity threshold to detect black frames.
            consecutive_frames: Number of consecutive frames to confirm session start.
        """
        self.input_path = input_video_path
        self.session_start_buffer = session_start_buffer
        self.black_threshold = black_threshold
        self.consecutive_frames = consecutive_frames
        self.cap = cv2.VideoCapture(input_video_path)

        # Video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def _frame_to_time_str(self, frame_idx):
        """Convert frame index to time string (MM:SS.s format)"""
        seconds = frame_idx / self.fps
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:05.2f}"

    def detect_session_frames_by_roi(self, visual_roi_coords, sample_center_size=20):
        """
        Detect exact session frames by analyzing every frame in search regions

        Args:
            visual_roi_coords: (x, y, width, height) coordinates of visual input ROI
            sample_center_size: Size of center region to sample (e.g., 20x20 pixels)

        Returns:
            tuple: (session_start_frame, session_end_frame)
        """
        x, y, w, h = visual_roi_coords

        # Define center region coordinates within the ROI
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        # Calculate search ranges
        start_search_frame = int(self.session_start_buffer * self.fps)

        # Find session start: check every frame from 10th second onwards for consecutive session frames
        session_start = None
        consecutive_session_count = 0

        for frame_idx in range(start_search_frame, self.total_frames):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Extract center region of visual ROI
                center_region = frame[
                    center_y : center_y + sample_center_size,
                    center_x : center_x + sample_center_size,
                ]

                # Convert to grayscale and get mean intensity
                gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
                mean_intensity = np.mean(gray_center)

                if mean_intensity > self.black_threshold:
                    consecutive_session_count += 1
                    if consecutive_session_count >= self.consecutive_frames:
                        # Found sustained session activity, go back to find actual start
                        session_start = frame_idx - self.consecutive_frames + 1
                        break
                else:
                    consecutive_session_count = 0

        if session_start is None:
            raise ValueError("Could not detect session start.")

        # Find session end: check every frame from end backwards until we find session content
        session_end = None

        for frame_idx in range(self.total_frames - 1, 0, -1):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Extract center region of visual ROI
                center_region = frame[
                    center_y : center_y + sample_center_size,
                    center_x : center_x + sample_center_size,
                ]

                # Convert to grayscale and get mean intensity
                gray_center = cv2.cvtColor(center_region, cv2.COLOR_BGR2GRAY)
                mean_intensity = np.mean(gray_center)

                # If this frame is above threshold, it's session content - this is our end
                if mean_intensity > self.black_threshold:
                    session_end = frame_idx
                    break

        if session_end is None:
            raise ValueError(f"Could not detect session end.")

        # Ensure session_end is after session_start
        if session_end <= session_start:
            raise ValueError("Session end before session start.")

        return session_start, session_end

    def save_validation_frames(
        self,
        session_start: int,
        session_end: int,
        visual_roi_coords: tuple,
        sync_roi_coords: tuple,
        sample_center_size: int = 20,
    ):
        """Save session start frame for validation"""
        x, y, w, h = visual_roi_coords
        sync_x, sync_y, sync_w, sync_h = sync_roi_coords

        # Calculate center region coordinates (same as in detection)
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        base_path = pathlib.Path(self.input_path).parent
        base_name = pathlib.Path(self.input_path).stem

        frames_to_save = {
            "start_minus_1": session_start - 1,
            "start": session_start,
            "end": session_end,
            "end_plus_1": session_end + 1,
        }
        output_path_start_frame = None
        for label, frame_idx in frames_to_save.items():
            if 0 <= frame_idx < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = self.cap.read()
                if ret:
                    marked_frame = frame.copy()

                    # Draw Visual ROI rectangle in green
                    cv2.rectangle(marked_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Draw Sync ROI rectangle in blue
                    cv2.rectangle(
                        marked_frame,
                        (sync_x, sync_y),
                        (sync_x + sync_w, sync_y + sync_h),
                        (255, 0, 0),
                        2,
                    )

                    # Draw center region rectangle in red
                    cv2.rectangle(
                        marked_frame,
                        (center_x, center_y),
                        (center_x + sample_center_size, center_y + sample_center_size),
                        (0, 0, 255),
                        2,
                    )

                    # Add text labels
                    cv2.putText(
                        marked_frame,
                        "Visual ROI",
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )
                    cv2.putText(
                        marked_frame,
                        "Sync ROI",
                        (sync_x - 20, sync_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 0, 0),
                        2,
                    )
                    cv2.putText(
                        marked_frame,
                        "Center Region",
                        (center_x, center_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2,
                    )

                    output_path = (
                        f"{base_path}/{base_name}_{label}_frame{frame_idx}.jpg"
                    )
                    cv2.imwrite(output_path, marked_frame)

                    if label == "start":
                        output_path_start_frame = output_path

        return output_path_start_frame

    def trim_video_to_rois(
        self, session_start, session_end, visual_roi_coords, sync_roi_coords
    ):
        """
        Direct crop and trim in one command using ffmpeg

        Args:
            session_start: First frame to include
            session_end: Last frame to include
            visual_roi_coords: (x, y, width, height) coordinates of visual input ROI
            sync_roi_coords: (x, y, width, height) coordinates of sync signal ROI
        """
        import subprocess

        # Calculate time ranges
        start_time = session_start / self.fps
        duration = (session_end - session_start) / self.fps

        # Generate output paths
        base_name = os.path.splitext(self.input_path)[0]
        extension = os.path.splitext(self.input_path)[1]
        visual_output_path = f"{base_name}_visual_roi{extension}"
        sync_output_path = f"{base_name}_sync_roi{extension}"

        # Extract ROI coordinates
        visual_x, visual_y, visual_w, visual_h = visual_roi_coords
        sync_x, sync_y, sync_w, sync_h = sync_roi_coords

        try:
            # Visual ROI command
            visual_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                self.input_path,
                "-t",
                str(duration),
                "-filter:v",
                f"crop={visual_w}:{visual_h}:{visual_x}:{visual_y}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                visual_output_path,
            ]

            # Sync ROI command
            sync_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                self.input_path,
                "-t",
                str(duration),
                "-filter:v",
                f"crop={sync_w}:{sync_h}:{sync_x}:{sync_y}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                sync_output_path,
            ]

            # Run both commands in parallel
            process1 = subprocess.Popen(
                visual_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process2 = subprocess.Popen(
                sync_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Wait for both to complete
            stdout1, stderr1 = process1.communicate()
            stdout2, stderr2 = process2.communicate()

            if process1.returncode != 0:
                print(f"Visual ROI error: {stderr1.decode()}")
                return False

            if process2.returncode != 0:
                print(f"Sync ROI error: {stderr2.decode()}")
                return False

            return True, visual_output_path, sync_output_path

        except Exception as e:
            print(f"Error: {e}")
            return False

    def auto_trim_video(
        self, visual_roi_coords, sync_roi_coords, sample_center_size=20
    ):
        """
        Automatically detect and trim video to ROI regions
        """
        # Step 1: Detect session boundaries
        session_start, session_end = self.detect_session_frames_by_roi(
            visual_roi_coords, sample_center_size=sample_center_size
        )

        # Step 2: Save validation frames if requested
        validation_path = self.save_validation_frames(
            session_start,
            session_end,
            visual_roi_coords,
            sync_roi_coords,
            sample_center_size,
        )

        # Step 3: Trim video
        success, visual_output_path, sync_output_path = self.trim_video_to_rois(
            session_start, session_end, visual_roi_coords, sync_roi_coords
        )

        if not success:
            print("Trimming failed!")
            return None, None

        return (
            visual_output_path,
            sync_output_path,
            validation_path,
            session_start,
            session_end,
        )

    def __del__(self):
        """Clean up video capture"""
        if hasattr(self, "cap") and self.cap.isOpened():
            self.cap.release()


def extract_sync_signal_from_video(video_path):
    """
    Extract sync signal from video — returns arrays for frame IDs, timestamps, and binary signal.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_ids = []
    timestamps = []
    signals = []

    for frame_count in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break

        raw_val = frame[0, 0].sum()
        signal = 0 if raw_val < 400 else 1
        timestamp = frame_count / fps

        frame_ids.append(frame_count)
        timestamps.append(timestamp)
        signals.append(signal)

    cap.release()

    return (
        np.array(frame_ids, dtype=int),
        np.array(timestamps, dtype=float),
        np.array(signals, dtype=int),
        fps,
        total_frames,
    )


def sync_video_to_photodiode(video_sync_df, photodiode_df):
    """
    Synchronize video sync signal with photodiode signal.

    Args:
        video_sync_df: DataFrame containing video sync timestamps and signals.
        photodiode_signal: DataFrame containing photodiode timestamps and signals.

    Returns:
        DataFrame with synchronized timestamps and signals.
    """
    video_timestamps = video_sync_df["timestamps"].values
    video_signal = video_sync_df["signals"].values

    photodiode_timestamps = photodiode_df["time_stamp"].values
    photodiode_signal = photodiode_df["photodiode_read"].values

    video_binary = video_signal.astype(int)
    photodiode_binary = photodiode_signal.astype(int)

    # Find edges in both signals
    photodiode_rising_edges = find_rising_edges(
        photodiode_timestamps, photodiode_binary
    )
    if len(photodiode_rising_edges) == 0:
        raise ValueError("No rising edges found in photodiode signal.")

    video_rising_edges = find_rising_edges(video_timestamps, video_binary)

    if len(video_rising_edges) == 0:
        raise ValueError("No rising edges found in video signal.")

    # Use first photodiode rising edge as reference
    first_photodiode_edge = photodiode_rising_edges[0]

    # Find video edges before photodiode edge
    video_edges_before = video_rising_edges[video_rising_edges < first_photodiode_edge]

    if len(video_edges_before) == 0:
        raise ValueError("No video edges found before the first photodiode edge.")

    corresponding_video_edge = video_edges_before[-1]
    time_offset = corresponding_video_edge - first_photodiode_edge

    photodiode_times_array = np.array(photodiode_timestamps)
    video_times_shifted = photodiode_times_array + time_offset

    # Find valid time range mask
    valid_mask = (video_times_shifted >= video_timestamps[0]) & (
        video_times_shifted <= video_timestamps[-1]
    )

    num_timepoints = len(photodiode_timestamps)
    video_frame_indices = np.full(num_timepoints, np.nan)
    original_frame_indices = np.full(num_timepoints, np.nan)

    # Only process valid timepoints
    valid_indices = np.where(valid_mask)[0]
    if len(valid_indices) > 0:
        valid_video_times = video_times_shifted[valid_indices]

        # Use searchsorted for efficient closest index finding
        insert_indices = np.searchsorted(video_timestamps, valid_video_times)

        # Handle edge cases and find closest indices
        closest_indices = np.zeros_like(insert_indices)
        for i, insert_idx in enumerate(insert_indices):
            if insert_idx == 0:
                closest_indices[i] = 0
            elif insert_idx >= len(video_timestamps):
                closest_indices[i] = len(video_timestamps) - 1
            else:
                # Compare distances to left and right neighbors
                left_dist = abs(valid_video_times[i] - video_timestamps[insert_idx - 1])
                right_dist = abs(valid_video_times[i] - video_timestamps[insert_idx])
                closest_indices[i] = (
                    insert_idx - 1 if left_dist < right_dist else insert_idx
                )

        # Fill in the results for valid timepoints
        video_frame_indices[valid_indices] = closest_indices
        original_frame_indices[valid_indices] = video_sync_df.iloc[closest_indices][
            "frame_ids"
        ].values

    return np.arange(num_timepoints), video_frame_indices, original_frame_indices
