import os
import numpy as np
import cv2
import pandas as pd

BLACK_THRESHOLD = 5  # Default threshold for detecting black pixels
CONSECUTIVE_FRAMES = 5
SESSION_START_BUFFER = 60  # Search buffer in sec for session start detection

# NOTE(celia): all recordings should be 120 fps (frame rate per second).


class VideoTrimmer:
    def __init__(self, input_video_path):
        """Initialize video trimmer

        Args:
            input_video_path: Path to input video file
        """
        self.input_path = input_video_path
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

    def detect_session_frames_by_roi(
        self,
        visual_roi_coords,
        black_threshold=BLACK_THRESHOLD,
        sample_center_size=20,
        consecutive_frames=CONSECUTIVE_FRAMES,
    ):
        """
        Detect exact session frames by analyzing every frame in search regions

        Args:
            visual_roi_coords: (x, y, width, height) coordinates of visual input ROI
            black_threshold: Pixel intensity threshold - below this is considered "black" (welcome screen)
            sample_center_size: Size of center region to sample (e.g., 20x20 pixels)
            consecutive_frames: Number of consecutive "session" frames needed to confirm session start

        Returns:
            tuple: (session_start_frame, session_end_frame)
        """
        x, y, w, h = visual_roi_coords

        # Define center region coordinates within the ROI
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        # Calculate search ranges
        start_search_frame = int(SESSION_START_BUFFER * self.fps)

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

                if mean_intensity > black_threshold:
                    consecutive_session_count += 1
                    if consecutive_session_count >= consecutive_frames:
                        # Found sustained session activity, go back to find actual start
                        session_start = frame_idx - consecutive_frames + 1
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
                if mean_intensity > black_threshold:
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
        session_start,
        session_end,
        visual_roi_coords,
        sync_roi_coords,
        sample_center_size=20,
    ):
        """Save session start frame for validation"""
        x, y, w, h = visual_roi_coords
        sync_x, sync_y, sync_w, sync_h = sync_roi_coords

        # Calculate center region coordinates (same as in detection)
        center_x = x + w // 2 - sample_center_size // 2
        center_y = y + h // 2 - sample_center_size // 2

        # Only save the session start frame
        frame_idx = session_start
        if 0 <= frame_idx < self.total_frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Save full frame with ROI and center region marked
                full_frame_marked = frame.copy()

                # Draw Visual ROI rectangle in green
                cv2.rectangle(full_frame_marked, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Draw Sync ROI rectangle in blue
                cv2.rectangle(
                    full_frame_marked,
                    (sync_x, sync_y),
                    (sync_x + sync_w, sync_y + sync_h),
                    (255, 0, 0),
                    2,
                )

                # Draw center region rectangle in red
                cv2.rectangle(
                    full_frame_marked,
                    (center_x, center_y),
                    (center_x + sample_center_size, center_y + sample_center_size),
                    (0, 0, 255),
                    2,
                )

                # Add text labels
                cv2.putText(
                    full_frame_marked,
                    "Visual ROI",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    full_frame_marked,
                    "Sync ROI",
                    (sync_x, sync_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 0, 0),
                    2,
                )
                cv2.putText(
                    full_frame_marked,
                    "Center Region",
                    (center_x, center_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )

                cv2.imwrite(
                    f"validation_session_start_frame{frame_idx}.jpg",
                    full_frame_marked,
                )

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
        self,
        visual_roi_coords,
        sync_roi_coords,
        black_threshold=BLACK_THRESHOLD,
        sample_center_size=20,
        validate=True,
    ):
        """
        Automatically detect and trim video to ROI regions
        """
        # Step 1: Detect session boundaries
        session_start, session_end = self.detect_session_frames_by_roi(
            visual_roi_coords,
            black_threshold=black_threshold,
            sample_center_size=sample_center_size,
        )

        # Step 2: Save validation frames if requested
        if validate:
            self.save_validation_frames(
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

        return visual_output_path, sync_output_path, session_start, session_end

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


def find_rising_edges(time, signal, threshold=0.5):
    """Find rising edges in binary signal"""
    rising_edges = []
    for i in range(1, len(signal)):
        if signal[i - 1] < threshold and signal[i] >= threshold:
            rising_edges.append(time[i])
    return np.array(rising_edges)


def sync_video_to_photodiode(video_sync_df, photodiode_df):
    """
    Synchronize video sync signal with photodiode signal.

    Args:
        video_sync_df: DataFrame containing video sync timestamps and signals.
        photodiode_signal: DataFrame containing photodiode timestamps and signals.

    Returns:
        DataFrame with synchronized timestamps and signals.
    """
    video_timestamps = video_sync_df["timestamp"].values
    video_signal = video_sync_df["signal"].values

    photodiode_timestamps = photodiode_df["time_stamp"].values
    photodiode_signal = photodiode_df["photodiode_read"].values

    # Convert signals to binary
    video_binary = video_signal.astype(int)
    photodiode_binary = photodiode_signal.astype(int)

    # Find rising edges in both signals
    photodiode_rising_edges = find_rising_edges(
        photodiode_timestamps, photodiode_binary
    )
    video_rising_edges = find_rising_edges(video_timestamps, video_binary)

    if len(photodiode_rising_edges) == 0 or len(video_rising_edges) == 0:
        return

    # Use first photodiode rising edge as reference
    first_photodiode_edge = photodiode_rising_edges[0]
    video_edges_before = video_rising_edges[video_rising_edges < first_photodiode_edge]

    if len(video_edges_before) == 0:
        return

    corresponding_video_edge = video_edges_before[-1]
    time_offset = corresponding_video_edge - first_photodiode_edge

    # Create photodiode-based mapping
    photodiode_mapping_data = []

    for timepoint_idx, photodiode_time in enumerate(photodiode_timestamps):
        video_time = photodiode_time + time_offset
        video_frame_idx = None
        original_frame_idx = None

        if video_time >= video_timestamps[0] and video_time <= video_timestamps[-1]:
            time_diffs = np.abs(video_timestamps - video_time)
            closest_idx = np.argmin(time_diffs)
            original_frame_idx = video_sync_df.iloc[closest_idx]["frame"]
            video_frame_idx = closest_idx

        video_frame_idx = video_frame_idx if video_frame_idx is not None else np.nan
        original_frame_idx = (
            original_frame_idx if original_frame_idx is not None else np.nan
        )

    return timepoint_idx, video_frame_idx, original_frame_idx


def sync_video_to_game_time(sync_df, time_dict):
    """
    Map video frames to step_time intervals based on corresponding dlc_read_time.

    Parameters:
    -----------
    sync_df : pandas.DataFrame
        Synchronized data with columns: video_frame_index, send_time
    time_dict : dict
        Dictionary with keys 'dlc_read_time' and 'step_time' containing arrays of corresponding times

    Returns:
    --------
    pandas.DataFrame
        DataFrame with columns: step_time, dlc_read_time, send_time, video_frame
    """

    # Extract arrays from synchronized data
    sync_send_times = sync_df["send_time"].values
    video_frames = sync_df["original_frame_idx"].values

    # Extract time arrays from dictionary
    dict_dlc_times = np.array(time_dict["dlc_read_time"])
    dict_step_times = np.array(time_dict["step_time"])

    # Calculate step rate for tolerance
    step_rate = (
        1.0 / np.mean(np.diff(dict_step_times)) if len(dict_step_times) > 1 else 10.0
    )

    # Create mapping for ALL step_times
    step_times_list = []
    send_times_list = []
    dlc_read_times_list = []
    video_frames_list = []

    for i, step_time in enumerate(dict_step_times):
        step_times_list.append(step_time)

        # Get corresponding dlc_read_time for this step_time
        if len(dict_dlc_times) > 1:
            dlc_index = i * (len(dict_dlc_times) - 1) / (len(dict_step_times) - 1)
            dlc_index_floor = int(np.floor(dlc_index))
            dlc_index_ceil = min(dlc_index_floor + 1, len(dict_dlc_times) - 1)

            if dlc_index_floor == dlc_index_ceil:
                corresponding_dlc_time = dict_dlc_times[dlc_index_floor]
            else:
                weight = dlc_index - dlc_index_floor
                corresponding_dlc_time = (
                    dict_dlc_times[dlc_index_floor] * (1 - weight)
                    + dict_dlc_times[dlc_index_ceil] * weight
                )
        else:
            corresponding_dlc_time = dict_dlc_times[0]

        dlc_read_times_list.append(corresponding_dlc_time)

        # Find video frames with send_time close to this step_time
        time_tolerance = 1.0 / step_rate
        time_diffs = np.abs(sync_send_times - step_time)
        close_frames_mask = time_diffs <= time_tolerance

        if np.any(close_frames_mask):
            close_frame_indices = video_frames[close_frames_mask]
            close_send_times = sync_send_times[close_frames_mask]

            # Take the closest frame
            closest_idx = np.argmin(time_diffs[close_frames_mask])
            best_frame = close_frame_indices[closest_idx]
            best_send_time = close_send_times[closest_idx]

            video_frames_list.append(best_frame)
            send_times_list.append(best_send_time)
        else:
            video_frames_list.append(np.nan)
            send_times_list.append(np.nan)

    # Create resampled dataset
    resampled_data = pd.DataFrame(
        {
            "step_time": step_times_list,  # NOTE(celia): this is the game time
            "dlc_read_time": dlc_read_times_list,
            "send_time": send_times_list,  # NOTE(celia): should be the same as dlc_read_time
            "video_frame": video_frames_list,
        }
    )

    return resampled_data.sort_values("step_time").reset_index(drop=True)
