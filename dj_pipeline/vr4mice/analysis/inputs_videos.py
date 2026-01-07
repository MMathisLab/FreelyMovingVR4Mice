import os
import pathlib
from typing import Dict, Iterable, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from vr4mice.analysis.latency_testing import (detect_signal_polarity,
                                              filter_pulsed_signal,
                                              find_rising_edges)

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

        base_path = pathlib.Path(self.input_path).parents[1]
        base_name = pathlib.Path(self.input_path).stem

        (base_path / "validation_frames").mkdir(parents=True, exist_ok=True)

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

                    output_path = f"{base_path}/validation_frames/{base_name}_{label}_frame{frame_idx}.jpg"
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
        base_path = pathlib.Path(self.input_path).parents[1]
        base_name = pathlib.Path(self.input_path).stem
        extension = os.path.splitext(self.input_path)[1]

        visual_output_path = (
            f"{base_path}/processed_recordings/{base_name}_visual_roi{extension}"
        )
        sync_output_path = (
            f"{base_path}/processed_recordings/{base_name}_sync_roi{extension}"
        )

        (base_path / "processed_recordings").mkdir(parents=True, exist_ok=True)

        # Extract ROI coordinates
        visual_x, visual_y, visual_w, visual_h = visual_roi_coords
        sync_x, sync_y, sync_w, sync_h = sync_roi_coords

        # try:
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
            raise RuntimeError(f"Error processing visual ROI: {stderr1.decode()}")

        if process2.returncode != 0:
            raise RuntimeError(f"Error processing sync ROI: {stderr2.decode()}")

        return True, visual_output_path, sync_output_path

        # except Exception as e:
        #     print(f"Error during video trimming: {e}")
        #     return False, visual_output_path, sync_output_path

    def auto_trim_video(
        self, visual_roi_coords, sync_roi_coords, sample_center_size=20, trimmed=True
    ):
        """
        Detect and trim video to ROI regions
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
        if trimmed:
            success, visual_output_path, sync_output_path = self.trim_video_to_rois(
                session_start, session_end, visual_roi_coords, sync_roi_coords
            )
        else:
            success = None

        if not success:
            ("Trimming failed!")
            return None, None, None, None, None

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


def sync_video_to_photodiode(video_sync_df, photodiode_df, frame_offset: int = 0):
    """
    Synchronize video sync signal with photodiode signal.

    Args:
        video_sync_df: DataFrame containing video sync timestamps and signals.
        photodiode_signal: DataFrame containing photodiode timestamps and signals.
        frame_offset: Integer frame offset to add to mapped frames (default 0).

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

    # Apply frame offset to both mapped and original frame indices
    if frame_offset != 0:
        video_frame_indices = video_frame_indices + frame_offset
        original_frame_indices = original_frame_indices + frame_offset

    return np.arange(num_timepoints), video_frame_indices, original_frame_indices


# ---------------------------------------------------------------------------
# Photodiode-aware alignment for pulse_geo, with fallback.
# ---------------------------------------------------------------------------


def _binarize(
    signal: Iterable[float], threshold: float = 0.2, invert: bool = False
) -> np.ndarray:
    arr = np.asarray(signal, dtype=float)
    binary = (arr > threshold).astype(int)
    if invert:
        binary = 1 - binary
    return binary


def _dedup_edges(edges: np.ndarray, min_separation: float = 0.01) -> np.ndarray:
    if edges.size == 0:
        return edges
    keep = [edges[0]]
    for t in edges[1:]:
        if t - keep[-1] >= min_separation:
            keep.append(t)
    return np.asarray(keep)


def _detect_edges(
    timestamps: np.ndarray, binary_signal: np.ndarray, min_separation: float = 0.01
) -> np.ndarray:
    edges = find_rising_edges(np.asarray(timestamps), np.asarray(binary_signal))
    return _dedup_edges(edges, min_separation=min_separation)


def _pair_edges(
    video_edges: np.ndarray, pd_edges: np.ndarray, max_gap: float = 0.3
) -> Tuple[np.ndarray, np.ndarray]:
    """Greedy nearest-neighbor pairing of photodiode edges to video edges within max_gap."""
    if video_edges.size == 0 or pd_edges.size == 0:
        return np.array([]), np.array([])

    pairs_v = []
    pairs_p = []
    vid = np.asarray(video_edges)
    pd = np.asarray(pd_edges)
    for t_pd in pd:
        idx = np.searchsorted(vid, t_pd)
        candidates = []
        if idx < len(vid):
            candidates.append(vid[idx])
        if idx > 0:
            candidates.append(vid[idx - 1])
        if not candidates:
            continue
        best = min(candidates, key=lambda t: abs(t - t_pd))
        if abs(best - t_pd) <= max_gap:
            pairs_p.append(t_pd)
            pairs_v.append(best)
    return np.asarray(pairs_v), np.asarray(pairs_p)


def _fit_offset_drift(
    video_edges: np.ndarray, pd_edges: np.ndarray, allow_drift: bool = True
) -> Tuple[float, float, Dict[str, float]]:
    """Fit t_video ≈ offset + drift * t_pd using paired edges."""
    if len(video_edges) == 0 or len(pd_edges) == 0:
        raise ValueError("No edge pairs available")

    if allow_drift and len(video_edges) >= 3:
        slope, intercept = np.polyfit(pd_edges, video_edges, deg=1)
    else:
        slope = 1.0
        intercept = float(np.mean(video_edges - pd_edges))

    preds = intercept + slope * pd_edges
    residuals = preds - video_edges
    rms = float(np.sqrt(np.mean(residuals**2))) if residuals.size else np.inf
    return intercept, slope, {"pair_count": float(len(video_edges)), "rms": rms}


def _map_times_to_frames(
    times: np.ndarray,
    video_timestamps: np.ndarray,
    frame_ids: np.ndarray,
    offset: float,
    drift: float,
) -> np.ndarray:
    """
    Map times to video frame IDs using fitted offset and drift.

    Converts each game/photodiode time t into the video times t': t' = offset + drift * t,
    accounting for a potential delay (offset) and clock drift (drift) between the video and
    photodiode signals. Then uses linear interpolation to find the corresponding video
    frame IDs.

    Args:
        times: Array of photodiode/game timesteps.
        video_timestamps: Array of video frame timestamps.
        frame_ids: Array of video frame IDs.
        offset: Fitted offset in seconds.
            Corresponds to a potential delay between photodiode and video such as latency
            or signal delay as defined in `mouse_task.dlc_utils.processor_with_signal.ProcessorWithSignal`.
        drift: Fitted drift factor.
            Accounts for clock drift between photodiode and video. Should be close to 1.
    """
    aligned = offset + drift * times
    frames = np.interp(aligned, video_timestamps, frame_ids, left=np.nan, right=np.nan)
    return frames


def _preprocess_photodiode(
    pd_read: np.ndarray,
    pd_ts: np.ndarray,
    pd_threshold: float = 0.2,
    baseline_time: Optional[float] = None,
    baseline_window: Tuple[float, float] = (3.0, 0.5),
) -> np.ndarray:
    """Preprocess photodiode signal: detect polarity, optional filter, baseline scale, binarize.

    Args:
        pd_read: Raw photodiode signal values.
        pd_ts: Photodiode timestamps (seconds).
        pd_threshold: Threshold for binarizing after preprocessing (default 0.2).
        baseline_time: Optional reference time to compute pre-signal baseline,
            using window (baseline_time - window[0], baseline_time - window[1]).
        baseline_window: Tuple describing window sizes before baseline_time.

    Returns:
        Binarized photodiode signal as boolean array.
    """
    # Detect signal polarity (flip if negative-going)
    polarity = detect_signal_polarity(pd_read)

    # Estimate sampling rate and apply filtering if high enough (>= ~1 kHz recordings)
    sampling_rate = int(1 // np.mean(np.diff(pd_ts))) if len(pd_ts) > 1 else 50
    if sampling_rate > 70:
        filtered_pd = (
            filter_pulsed_signal(
                signal=pd_read, sample_rate=sampling_rate, cutoff_freq=50
            )
            * polarity
        )
    else:
        filtered_pd = pd_read * polarity

    # Compute baseline mean using a pre-signal window when available; otherwise first 100 samples
    if baseline_time is not None and len(filtered_pd) > 0:
        start = baseline_time - baseline_window[0]
        end = baseline_time - baseline_window[1]
        mask = (pd_ts > start) & (pd_ts < end)
        if np.any(mask):
            baseline_mean = float(np.mean(filtered_pd[mask]))
        else:
            baseline_mean = float(np.mean(filtered_pd[: min(100, len(filtered_pd))]))
    else:
        baseline_mean = float(np.mean(filtered_pd[: min(100, len(filtered_pd))]))

    baseline_max = float(np.max(filtered_pd)) if len(filtered_pd) else 1.0
    if baseline_max > baseline_mean:
        scaled_pd = (filtered_pd - baseline_mean) / (baseline_max - baseline_mean)
    else:
        scaled_pd = filtered_pd

    # Binarize after scaling
    return (scaled_pd > pd_threshold).astype(int)


def _align_by_photodiode(
    video_df: pd.DataFrame,
    photodiode_df: pd.DataFrame,
    step_times: np.ndarray,
    max_gap: float = 0.3,
    min_edge_separation: float = 0.01,
    pd_threshold: float = 0.2,
    pd_invert: bool = False,
    allow_drift: bool = True,
    frame_offset: int = 0,
    qa_rms_thresh: float = 0.02,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Align step times to video frames using photodiode signal.

    Args:
        video_df: DataFrame with video 'timestamps', 'frame_ids', and 'signals'.
        photodiode_df: DataFrame with photodiode 'time_stamp' and 'photodiode_read'.
        step_times: Array of game step times to align.
        max_gap: Maximum time gap to consider edges as paired.
        min_edge_separation: Minimum separation between edges to consider them distinct.
        pd_threshold: Threshold for binarizing photodiode signal after preprocessing.
        pd_invert: Whether to invert the photodiode binary signal.
        allow_drift: Whether to allow drift in the alignment fit.
        frame_offset: Integer frame offset to add after alignment (default 0).
        qa_rms_thresh: Maximum RMS error for QA pass.
    """
    # Extract and preprocess video data
    video_ts = np.asarray(video_df["timestamps"], dtype=float)
    video_frames = np.asarray(video_df["frame_ids"], dtype=float)
    video_signals = np.asarray(video_df["signals"], dtype=float)
    video_bin = _binarize(video_signals, threshold=0.5)

    # Extract and preprocess photodiode data
    pd_ts = np.asarray(photodiode_df["time_stamp"], dtype=float)
    pd_read = np.asarray(photodiode_df["photodiode_read"], dtype=float)

    # Normalize photodiode time to start at 0
    pd_ts = pd_ts - pd_ts[0]

    # Determine a baseline reference time from video: first rising edge after trimming
    video_edges_for_baseline = _detect_edges(
        video_ts, video_bin, min_separation=min_edge_separation
    )
    baseline_time = (
        float(video_edges_for_baseline[0]) if len(video_edges_for_baseline) else None
    )

    # Preprocess photodiode signal using same strategy as latency testing
    pd_bin = _preprocess_photodiode(
        pd_read, pd_ts, pd_threshold=pd_threshold, baseline_time=baseline_time
    )
    if pd_invert:
        pd_bin = 1 - pd_bin

    video_edges = _detect_edges(video_ts, video_bin, min_separation=min_edge_separation)
    pd_edges = _detect_edges(pd_ts, pd_bin, min_separation=min_edge_separation)

    v_pairs, p_pairs = _pair_edges(video_edges, pd_edges, max_gap=max_gap)
    if len(v_pairs) < 1:
        raise ValueError("No edge pairs within tolerance")

    offset, drift, qa = _fit_offset_drift(v_pairs, p_pairs, allow_drift=allow_drift)
    frames = _map_times_to_frames(step_times, video_ts, video_frames, offset, drift)
    # Apply optional fixed frame offset to account for known latency
    if frame_offset != 0:
        frames = frames + frame_offset
    qa["offset"] = offset
    qa["drift"] = drift

    # QA thresholds: require at least 2 pairs and low residuals
    if qa["pair_count"] < 2 or qa["rms"] > qa_rms_thresh:
        raise ValueError("Photodiode alignment QA failed")

    return frames, qa


def _align_by_merge(
    step_times: np.ndarray,
    video_df: pd.DataFrame,
    frame_offset: int = -7,
    signal_delay: float = 0,
) -> np.ndarray:
    """
    Align step times to video frames using merge_asof.

    Each step time is matched to the closest forward video timestamp using absolute time.
    Applies a fixed frame offset to account for known latency. Optionally shifts step times
    to account for signal_delay (if step times are relative to game start, not TTL start).

    Args:
        step_times: Array of game step times to align.
        video_df: DataFrame with video 'timestamps' and 'frame_ids'.
        frame_offset: Fixed frame offset to apply after alignment to take the latency into account.
            Note that 7 was determined empirically for our setup at 120 fps.
        signal_delay: Initial delay (seconds) before TTL signal started. If step_times are
            game times (starting when video/TTL started), use 0 (default). If step_times
            started before the signal, subtract this delay to align to the signal timeline.

    Returns:
        Array of frame IDs aligned onto the game steps (with offset applied).
    """
    # Shift step times to account for signal delay
    aligned_step_times = step_times - signal_delay

    resampled = pd.merge_asof(
        pd.DataFrame({"step_time": aligned_step_times}),
        video_df.sort_values("timestamps"),
        left_on="step_time",
        right_on="timestamps",
        direction="forward",
    )
    frames = resampled["frame_ids"].to_numpy(dtype=float) + frame_offset
    return frames


def align_steps_to_frames(
    video_sync_df: pd.DataFrame,
    photodiode_df: Optional[pd.DataFrame],
    step_times: np.ndarray,
    signal_type: str,
    use_photodiode: bool = True,
    **kwargs,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Align game step times to video frame IDs.

    For pulse_geo: try photodiode-based alignment, else fallback.
    For pulse/sin/flip/others: always use merge_asof fallback.
    Returns (frame_ids, qa_dict).
    """
    step_times = np.asarray(step_times, dtype=float)
    qa: Dict[str, float] = {"path": "fallback"}

    if use_photodiode and photodiode_df is not None and signal_type == "pulse_geo":
        try:
            frames, qa_pd = _align_by_photodiode(
                video_sync_df,
                photodiode_df,
                step_times,
                **kwargs,
            )
            qa.update(qa_pd)
            qa["path"] = "photodiode"
            return frames, qa
        except Exception as err:
            qa["error"] = str(err)

    # Extract signal_delay from kwargs if provided (default 0)
    signal_delay = kwargs.pop("signal_delay", 0.0)
    frames = _align_by_merge(step_times, video_sync_df, signal_delay=signal_delay)
    qa["path"] = "fallback"
    return frames, qa
