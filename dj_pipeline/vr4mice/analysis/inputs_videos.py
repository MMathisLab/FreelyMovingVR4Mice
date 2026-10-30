import os
import pathlib
import re
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from vr4mice.analysis.latency_testing import (
    filter_pulsed_signal,
    find_rising_edges,
)

# ---------------------------------------------------------------------------
# Old setup: OBS screen recording, aligned to game steps with the photodiode.
# The recording and the photodiode both see the sync square (pulse_geo).
# ---------------------------------------------------------------------------


def find_sync_square(
    video_path: str,
    search_region: Tuple[float, float, float, float] = (0.9, 0.4, 1.0, 0.65),
    n_samples: int = 40,
    dark: float = 60,
    bright: float = 200,
) -> Tuple[int, int, int, int]:
    """Locate the sync square: the pixels that switch between dark and bright.

    Frames are sampled across the recording; within ``search_region`` (fractions
    of the frame: x0, y0, x1, y1), pixels that are both below ``dark`` and above
    ``bright`` in some samples belong to the square. Works whatever the screen
    layout of the recording.

    Returns:
        (x, y, width, height) of the square, in pixels.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")
    try:
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        x0, y0 = int(search_region[0] * width), int(search_region[1] * height)
        x1, y1 = int(search_region[2] * width), int(search_region[3] * height)
        samples = []
        for index in np.linspace(0.1 * n_frames, 0.9 * n_frames, n_samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            success, frame = cap.read()
            if success:
                samples.append(frame[y0:y1, x0:x1, 1])
    finally:
        cap.release()
    if not samples:
        raise RuntimeError(f"Could not read frames from {video_path}")

    samples = np.stack(samples)
    toggling = (samples.min(axis=0) < dark) & (samples.max(axis=0) > bright)
    ys, xs = np.nonzero(toggling)
    if xs.size == 0:
        raise ValueError(
            f"No sync square found in {video_path} (search {search_region})"
        )
    return (
        int(x0 + xs.min()),
        int(y0 + ys.min()),
        int(xs.max() - xs.min() + 1),
        int(ys.max() - ys.min() + 1),
    )


def read_sync_trace(
    video_path: str,
    sync_roi: Tuple[int, int, int, int],
    inset: int = 3,
    start: int = 0,
    n_frames: Optional[int] = None,
    seek_offset: int = 0,
) -> np.ndarray:
    """Mean intensity inside the sync square for every frame of a video.

    The ROI is shrunk by ``inset`` pixels on each side to avoid its edges.
    ``start`` and ``n_frames`` read only a window of the video; ``seek_offset``
    (see ``measure_seek_offset``) corrects where seeking to ``start`` lands.

    Returns:
        uint8 array with one value per frame read.
    """
    x, y, w, h = (int(v) for v in sync_roi)
    x0, y0 = x + inset, y + inset
    x1, y1 = max(x + w - inset, x0 + 1), max(y + h - inset, y0 + 1)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")
    trace = []
    try:
        if start:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(start) - int(seek_offset))
        while n_frames is None or len(trace) < n_frames:
            success, frame = cap.read()
            if not success:
                break
            trace.append(frame[y0:y1, x0:x1, 1].mean())
    finally:
        cap.release()
    return np.round(np.asarray(trace)).astype(np.uint8)


def binarize_sync_trace(trace: np.ndarray) -> np.ndarray:
    """Square on (1) / off (0) per frame, thresholded midway between its two levels."""
    trace = np.asarray(trace, dtype=float)
    low, high = np.percentile(trace, [5, 95])
    return (trace > (low + high) / 2).astype(int)


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
    correction: Optional[np.ndarray] = None,
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
        correction: Optional per-time correction (seconds) added to the video
            times, e.g. smoothed residuals of the edge fit.
    """
    aligned = offset + drift * times
    if correction is not None:
        aligned = aligned + correction
    frames = np.interp(aligned, video_timestamps, frame_ids, left=np.nan, right=np.nan)
    return frames


def _preprocess_photodiode(
    pd_read: np.ndarray,
    pd_ts: np.ndarray,
    pd_threshold: float = 0.5,
    invert: bool = False,
    level_percentiles: Tuple[float, float] = (5.0, 95.0),
) -> np.ndarray:
    """Binarize the photodiode: optional low-pass filter, then a level threshold.

    The sync square makes the photodiode switch between two levels. The signal is
    scaled between its low and high levels (``level_percentiles``) and
    thresholded at ``pd_threshold`` (0.5 = midpoint), which does not depend on
    the first samples (often a start-up transient).

    Args:
        pd_read: Raw photodiode signal values.
        pd_ts: Photodiode timestamps (seconds).
        pd_threshold: Threshold on the scaled signal (0 = low level, 1 = high level).
        invert: If True, the square is "on" when the photodiode is low.
        level_percentiles: Percentiles taken as the low and high levels.

    Returns:
        Binarized photodiode signal (1 = square on).
    """
    pd_read = np.asarray(pd_read, dtype=float)
    # Low-pass filter when sampled fast enough (>= ~1 kHz recordings)
    sampling_rate = int(1 // np.mean(np.diff(pd_ts))) if len(pd_ts) > 1 else 50
    if sampling_rate > 70:
        pd_read = filter_pulsed_signal(
            signal=pd_read, sample_rate=sampling_rate, cutoff_freq=50
        )

    low, high = np.percentile(pd_read, level_percentiles)
    if high <= low:
        return np.zeros(len(pd_read), dtype=int)
    scaled = (pd_read - low) / (high - low)
    binary = (scaled > pd_threshold).astype(int)
    return 1 - binary if invert else binary


def _estimate_edge_offset(
    video_edges: np.ndarray,
    pd_edges: np.ndarray,
    max_offset: float = 60.0,
    bin_size: float = 0.005,
    window: float = 0.05,
    n_video_edges: int = 50,
) -> float:
    """Coarse offset (video time - photodiode time) between two edge trains.

    The sync signal (pulse_geo) has irregular inter-pulse intervals, so only
    the true offset lines up many video/photodiode edge pairs at once: it is
    the peak of the pairwise edge time differences. Only the first video edges
    are used, so drift or dropped frames have not yet spread the peak, and the
    histogram is summed over ``window`` to tolerate the remaining spread.

    Args:
        video_edges: Rising edge times of the video sync signal (s).
        pd_edges: Rising edge times of the photodiode (s).
        max_offset: Largest offset searched (s).
        bin_size: Histogram bin size (s).
        window: Width over which histogram counts are summed (s).
        n_video_edges: Number of leading video edges used.

    Returns:
        Offset in seconds such that video_time ~= pd_time + offset.
    """
    v = np.asarray(video_edges, dtype=float)[:n_video_edges]
    p = np.asarray(pd_edges, dtype=float)
    diffs = (v[None, :] - p[:, None]).ravel()
    diffs = diffs[np.abs(diffs) <= max_offset]
    if diffs.size == 0:
        raise ValueError("No video/photodiode edges within max_offset")
    bins = np.arange(-max_offset, max_offset + bin_size, bin_size)
    hist, bin_edges = np.histogram(diffs, bins=bins)
    width = max(int(round(window / bin_size)), 1)
    summed = np.convolve(hist, np.ones(width), mode="same")
    peak = int(np.argmax(summed))
    return float(bin_edges[peak] + bin_size / 2)


def _robust_offset_drift(
    v_pairs: np.ndarray,
    p_pairs: np.ndarray,
    allow_drift: bool,
    sigma: float = 3.0,
    floor: float = 0.01,
) -> Tuple[float, float, Dict[str, float], np.ndarray]:
    """Fit offset/drift after rejecting residual outliers (wrongly paired edges).

    Residuals are centred on their median and scored against a MAD-based scale
    with a ``floor`` (s), as in ``np_sync.align_barcodes``.

    Returns:
        offset, drift, QA and the boolean mask of kept pairs.
    """
    keep = np.ones(len(v_pairs), dtype=bool)
    for _ in range(5):
        offset, drift, qa = _fit_offset_drift(
            v_pairs[keep], p_pairs[keep], allow_drift=allow_drift
        )
        residuals = v_pairs - (offset + drift * p_pairs)
        center = np.median(residuals[keep])
        scale = 1.4826 * np.median(np.abs(residuals[keep] - center))
        updated = np.abs(residuals - center) <= max(sigma * scale, floor)
        if updated.sum() < 2 or np.array_equal(updated, keep):
            break
        keep = updated
    offset, drift, qa = _fit_offset_drift(
        v_pairs[keep], p_pairs[keep], allow_drift=allow_drift
    )
    return offset, drift, qa, keep


def _fit_photodiode_edges(
    video_edges: np.ndarray,
    pd_edges: np.ndarray,
    max_gap: float,
    max_offset: float,
    allow_drift: bool,
    initial_span: float = 20.0,
    anchor: str = "pattern",
) -> Tuple[float, float, Dict[str, float], np.ndarray, np.ndarray]:
    """Fit video_time = offset + drift * pd_time from two sync edge trains.

    The coarse offset comes from ``anchor``: "pattern" matches the irregular
    pulse_geo intervals (``_estimate_edge_offset``); "first_edge" matches the
    first edge of each train, for regular pulses whose intervals are all alike
    (the recording must start before the pulse train).

    Starting from the coarse offset at the beginning of the video, edges are
    paired in a time window that doubles at each step, refitting (with outlier
    rejection) in between, so the fit only ever extrapolates over a short span
    and chance pairings far from the current fit are not used.

    Returns the offset, drift, QA and the paired (photodiode, video) edge times.
    """
    if len(video_edges) == 0 or len(pd_edges) == 0:
        raise ValueError("No sync edges in video or photodiode signal")
    if anchor == "pattern":
        offset = _estimate_edge_offset(video_edges, pd_edges, max_offset=max_offset)
    elif anchor == "first_edge":
        offset = float(video_edges[0] - pd_edges[0])
    else:
        raise ValueError(f"Unknown anchor {anchor!r}")
    drift = 1.0

    def _pair_and_fit(pd_subset, offset, drift, gap):
        mapped = offset + drift * pd_subset
        v_pairs, mapped_pairs = _pair_edges(video_edges, mapped, max_gap=gap)
        if len(v_pairs) < 2:
            raise ValueError("No edge pairs within tolerance")
        p_pairs = (mapped_pairs - offset) / drift
        offset, drift, qa, keep = _robust_offset_drift(
            v_pairs, p_pairs, allow_drift=allow_drift
        )
        return offset, drift, qa, p_pairs[keep], v_pairs[keep]

    # Grow the window from the first video edge until it covers the session
    t_start = float(video_edges[0]) - offset  # photodiode time of the video start
    span = initial_span
    while True:
        window = (pd_edges >= t_start) & (pd_edges <= t_start + span)
        if window.sum() >= 2:
            offset, drift, qa, p_pairs, v_pairs = _pair_and_fit(
                pd_edges[window], offset, drift, max_gap
            )
        if t_start + span >= pd_edges[-1]:
            break
        span *= 2
    # Final pass over all edges with a tight tolerance around the fit
    offset, drift, qa, p_pairs, v_pairs = _pair_and_fit(
        pd_edges, offset, drift, max_gap / 3
    )
    return offset, drift, qa, p_pairs, v_pairs


def align_steps_to_frames_by_photodiode(
    video_df: pd.DataFrame,
    photodiode_df: pd.DataFrame,
    step_times: np.ndarray,
    max_gap: float = 0.1,
    max_offset: float = 60.0,
    min_edge_separation: float = 0.1,
    pd_threshold: float = 0.5,
    pd_invert: Optional[bool] = None,
    allow_drift: bool = True,
    frame_offset: int = 0,
    qa_rms_thresh: float = 0.02,
    min_pairs: int = 10,
    min_pair_fraction: float = 0.8,
    residual_window: int = 41,
    regular_pulses: bool = False,
    min_quiet: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Align step times to video frames using the photodiode signal.

    The photodiode and the video sync ROI see the same sync square. Their rising
    edges are matched to fit ``video_time = offset + drift * game_time``. As in
    the barcode sync (``np_sync.align_barcodes``), the paired edges are also
    followed locally: a running median of the fit residuals over
    ``residual_window`` edges is added, so local timing errors of the video
    (e.g. dropped frames, when its timestamps are frame / fps) are corrected
    without passing through each edge's jitter.

    Args:
        video_df: DataFrame with video 'timestamps' (s; e.g. frame / fps of the
            raw recording, any origin), 'frame_ids', and 'signals' (sync square
            on/off per frame).
        photodiode_df: DataFrame with photodiode 'time_stamp' and
            'photodiode_read'. 'time_stamp' must be on the same clock as
            ``step_times`` (game time: unix time - State.start_time).
        step_times: Array of game step times to align.
        max_gap: Maximum time gap to pair edges after the coarse offset (s).
        max_offset: Largest video/photodiode offset searched (s).
        min_edge_separation: Minimum separation between edges to consider them
            distinct (s); sync pulses are >= ~0.2 s apart.
        pd_threshold: Threshold on the scaled photodiode (0.5 = midpoint).
        pd_invert: Photodiode polarity; None tries both and keeps the better fit.
        allow_drift: Whether to allow drift in the alignment fit.
        frame_offset: Integer frame offset to add after alignment (default 0).
        qa_rms_thresh: Maximum RMS error for QA pass.
        min_pairs: Minimum number of paired edges for QA pass.
        min_pair_fraction: Minimum fraction of the edges expected in the
            video/photodiode overlap that are paired, for QA pass. Catches
            noise edges and unfollowed jumps in the video timing.
        residual_window: Number of paired edges in the running median of the
            fit residuals (~0.5 s apart for pulse_geo).
        regular_pulses: True for a regular sync signal ("pulse"): the trains
            are anchored on their first edges instead of their interval
            pattern, so the recording must start before the pulses.
        min_quiet: With regular pulses, minimum time (s) without sync edges
            before the first edge, in both the video and the photodiode, so the
            first edges are the start of the pulse train and not a later pulse
            (which would shift every frame by whole pulse periods).
    """
    video_ts = np.asarray(video_df["timestamps"], dtype=float)
    video_frames = np.asarray(video_df["frame_ids"], dtype=float)
    video_signals = np.asarray(video_df["signals"], dtype=float)
    video_bin = _binarize(video_signals, threshold=0.5)
    video_edges = _detect_edges(video_ts, video_bin, min_separation=min_edge_separation)

    # Photodiode times stay on the game clock (no re-zeroing), like step_times
    pd_ts = np.asarray(photodiode_df["time_stamp"], dtype=float)
    pd_read = np.asarray(photodiode_df["photodiode_read"], dtype=float)

    best = None
    errors = []
    for invert in (False, True) if pd_invert is None else (pd_invert,):
        pd_bin = _preprocess_photodiode(
            pd_read, pd_ts, pd_threshold=pd_threshold, invert=invert
        )
        pd_edges = _detect_edges(pd_ts, pd_bin, min_separation=min_edge_separation)
        if regular_pulses and len(video_edges) and len(pd_edges):
            quiet_video = video_edges[0] - video_ts[0]
            quiet_pd = pd_edges[0] - pd_ts[0]
            if min(quiet_video, quiet_pd) < min_quiet:
                errors.append(
                    f"invert={invert}: regular pulses but no quiet period before "
                    f"the first edge (video {quiet_video:.2f}s, photodiode "
                    f"{quiet_pd:.2f}s): the pulse train start is not recorded"
                )
                continue
            # The square is off before the train: with the wrong polarity the
            # photodiode reads "on" there (a 50% duty cycle train is otherwise
            # the same, shifted by half a period).
            if pd_bin[pd_ts < pd_edges[0]].mean() > 0.1:
                errors.append(
                    f"invert={invert}: photodiode on before the first pulse "
                    "(wrong polarity)"
                )
                continue
            # Regular trains all look alike: only the pulse count tells a
            # recording of another session (or a cut recording) apart.
            n_video, n_pd = len(video_edges), len(pd_edges)
            if abs(n_video - n_pd) > max(0.05 * n_pd, 5):
                errors.append(
                    f"invert={invert}: {n_video} sync pulses in the video but "
                    f"{n_pd} in the photodiode (wrong session's video, or "
                    "recording cut?)"
                )
                continue
        try:
            offset, drift, qa, p_pairs, v_pairs = _fit_photodiode_edges(
                video_edges,
                pd_edges,
                max_gap,
                max_offset,
                allow_drift,
                anchor="first_edge" if regular_pulses else "pattern",
            )
        except ValueError as err:
            errors.append(f"invert={invert}: {err}")
            continue
        # QA: enough pairs, low residuals, and most expected edges paired
        mapped = offset + drift * pd_edges
        n_pd_in_video = int(((mapped >= video_ts[0]) & (mapped <= video_ts[-1])).sum())
        n_expected = max(min(n_pd_in_video, len(video_edges)), 1)
        qa["pair_fraction"] = qa["pair_count"] / n_expected
        if (
            qa["pair_count"] < min_pairs
            or qa["rms"] > qa_rms_thresh
            or qa["pair_fraction"] < min_pair_fraction
        ):
            errors.append(
                f"invert={invert}: QA failed (pairs={qa['pair_count']:.0f}, "
                f"pair_fraction={qa['pair_fraction']:.2f}, rms={qa['rms']:.4f}s)"
            )
            continue
        if best is None or qa["rms"] < best[2]["rms"]:
            best = (offset, drift, qa, invert, p_pairs, v_pairs)

    if best is None:
        raise ValueError("Photodiode alignment QA failed: " + "; ".join(errors))

    offset, drift, qa, invert, p_pairs, v_pairs = best
    residuals = v_pairs - (offset + drift * p_pairs)
    smoothed = (
        pd.Series(residuals)
        .rolling(residual_window, center=True, min_periods=1)
        .median()
        .to_numpy()
    )
    correction = np.interp(np.asarray(step_times, dtype=float), p_pairs, smoothed)
    frames = _map_times_to_frames(
        step_times, video_ts, video_frames, offset, drift, correction=correction
    )
    # Apply optional fixed frame offset to account for known latency
    if frame_offset != 0:
        frames = frames + frame_offset
    qa["offset"] = offset
    qa["drift"] = drift
    qa["pd_invert"] = float(invert)
    return frames, qa


# ---------------------------------------------------------------------------
# 3-camera setup: input video filmed by camera 2 with per-frame timestamps on
# the game's host clock, so game steps map to frames by timestamp lookup.
# ---------------------------------------------------------------------------


_DATASET_PATTERN = r"[A-Za-z0-9]+_\d{4}-\d{2}-\d{2}_\d+"


def find_input_video_files(
    filenames: Iterable[str], prefixes: Iterable[str], camera: int = 2
) -> Dict[str, Tuple[str, str]]:
    """Pair input videos with their timestamp files, per dataset.

    Expected names, with ``prefix`` one of ``prefixes`` (e.g. ``vr4mice``):
    ``{prefix}_{dataset}_VIDEO{camera}.avi`` and
    ``TS_{prefix}_{dataset}_CAMERA{camera}.npy``. Datasets missing either file
    are left out. When several prefixes match, the first one in ``prefixes``
    wins.

    Args:
        filenames: File names (not paths) found in the input video folder.
        prefixes: Accepted file prefixes, in order of preference.
        camera: Camera number of the input video.

    Returns:
        Mapping dataset -> (video filename, timestamp filename).
    """
    names = set(filenames)
    pairs = {}
    for prefix in prefixes:
        video_re = re.compile(
            rf"^{re.escape(prefix)}_({_DATASET_PATTERN})_VIDEO{camera}\.avi$"
        )
        for name in sorted(names):
            match = video_re.match(name)
            if not match or match.group(1) in pairs:
                continue
            dataset = match.group(1)
            timestamp_name = f"TS_{prefix}_{dataset}_CAMERA{camera}.npy"
            if timestamp_name in names:
                pairs[dataset] = (name, timestamp_name)
    return pairs


def align_steps_to_frames_by_timestamps(
    step_times: np.ndarray, frame_times: np.ndarray, frame_offset: int = 0
) -> np.ndarray:
    """Map step times to video frames using per-frame timestamps on the same clock.

    Each step is matched to the first frame at or after it, then shifted by
    ``frame_offset`` frames to account for display/capture latency. Steps outside the
    video, before its first frame or after its last one, get -1 rather than a
    clipped frame.

    Args:
        step_times: Step times, on the same clock as ``frame_times`` (seconds).
        frame_times: Timestamp of each video frame (seconds), non-decreasing.
        frame_offset: Number of frames added after matching.

    Returns:
        Integer frame index per step, -1 for steps outside the video.
    """
    step_times = np.asarray(step_times, dtype=float)
    frame_times = np.asarray(frame_times, dtype=float)
    if frame_times.ndim != 1 or frame_times.size == 0:
        raise ValueError("frame_times must be a non-empty 1D array")
    if np.any(np.diff(frame_times) < 0):
        raise ValueError("frame_times must be sorted (non-decreasing)")

    frames = np.searchsorted(frame_times, step_times, side="left") + int(frame_offset)
    outside = (
        ~np.isfinite(step_times)
        | (step_times < frame_times[0])
        | (step_times > frame_times[-1])
        | (frames < 0)
        | (frames >= frame_times.size)
    )
    frames[outside] = -1
    return frames.astype(np.int64)


def step_alignment_qa(
    step_times: np.ndarray, frame_times: np.ndarray, frame_ids: np.ndarray
) -> Dict[str, float]:
    """Quality summary of a timestamp-based alignment.

    Args:
        step_times: Step times on the frame clock (seconds).
        frame_times: Timestamp of each video frame (seconds).
        frame_ids: Output of ``align_steps_to_frames_by_timestamps``.

    Returns:
        Dict with ``n_steps``, ``n_steps_outside_video``, ``coverage`` (fraction
        of steps with a frame) and ``median_abs_gap`` (median |frame time - step
        time| in seconds over steps with a frame, NaN if none).
    """
    step_times = np.asarray(step_times, dtype=float)
    frame_times = np.asarray(frame_times, dtype=float)
    frame_ids = np.asarray(frame_ids)
    inside = frame_ids >= 0
    n_steps = int(frame_ids.size)
    gaps = np.abs(frame_times[frame_ids[inside]] - step_times[inside])
    return {
        "n_steps": n_steps,
        "n_steps_outside_video": int(n_steps - inside.sum()),
        "coverage": float(inside.mean()) if n_steps else 0.0,
        "median_abs_gap": float(np.median(gaps)) if gaps.size else float("nan"),
    }


def list_input_video_files(
    input_video_dir: str, prefixes: Iterable[str], camera: int = 2
) -> Dict[str, Tuple[str, str]]:
    """Return {dataset: (video_path, timestamp_path)} for input videos in a folder.

    Only datasets with both the camera video and its timestamp file are listed
    (see ``find_input_video_files``). Returns an empty dict if the folder is missing.
    """
    directory = pathlib.Path(input_video_dir)
    if not directory.is_dir():
        return {}
    pairs = find_input_video_files(
        [path.name for path in directory.iterdir() if path.is_file()],
        prefixes,
        camera=camera,
    )
    return {
        dataset: (str(directory / video), str(directory / timestamps))
        for dataset, (video, timestamps) in pairs.items()
    }


def measure_seek_offset(
    video_path: str,
    probes: Tuple[int, ...] = (3000, 15000, 30000),
    window: int = 30,
    sequence: int = 20,
    thumbnail: Tuple[int, int] = (160, 120),
) -> int:
    """Frames by which OpenCV seeking misses the requested frame (landed - requested).

    Seeking is not frame-accurate in some files (e.g. H.264 in AVI lands a fixed
    number of frames early). Frames around each probe are decoded sequentially
    (the true frame order); after seeking to the probe, ``sequence`` frames are
    read and located in the sequential frames. A sequence, unlike one frame, is
    unique even when consecutive frames repeat (a camera filming slower
    screens). Probes where it still cannot be located are skipped.

    Raises:
        ValueError: If no probe can be matched, or probes give different offsets.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    probes = sorted(
        {int(np.clip(p, window, n_frames - window - sequence - 1)) for p in probes}
    )
    wanted = {i for p in probes for i in range(p - window, p + window + sequence)}

    def small(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, thumbnail).astype(np.int16)

    sequential = {}
    try:
        for index in range(max(wanted) + 1):
            if not cap.grab():
                break
            if index in wanted:
                success, frame = cap.retrieve()
                if success:
                    sequential[index] = small(frame)
    finally:
        cap.release()

    offsets = []
    for probe in probes:
        cap = cv2.VideoCapture(video_path)
        sought = []
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, probe)
            for _ in range(sequence):
                success, frame = cap.read()
                if not success:
                    break
                sought.append(small(frame))
        finally:
            cap.release()
        if len(sought) < sequence:
            continue
        sought = np.stack(sought)
        candidates = [
            c
            for c in range(probe - window, probe + window + 1)
            if all(c + k in sequential for k in range(sequence))
        ]
        diffs = np.array(
            [
                np.abs(
                    np.stack([sequential[c + k] for k in range(sequence)]) - sought
                ).mean()
                for c in candidates
            ]
        )
        order = np.argsort(diffs)
        if diffs[order[0]] > 0.5 or diffs[order[1]] - diffs[order[0]] < 0.02:
            continue  # sequence not unique around this probe (static screens)
        offsets.append(candidates[order[0]] - probe)

    if not offsets:
        raise ValueError(
            f"Could not measure seek accuracy in {video_path} (frames too alike)"
        )
    if len(set(offsets)) > 1:
        raise ValueError(
            f"Seeking in {video_path} lands at varying offsets {offsets}: frames "
            "cannot be read reliably (re-encode the video?)"
        )
    return offsets[0]


def read_video_frame(video_path: str, frame_index: int, seek_offset: int = 0):
    """Return frame `frame_index` of a video (BGR, as read by OpenCV).

    ``seek_offset`` (see ``measure_seek_offset``) corrects where seeking lands.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video path does not exist: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if not (0 <= frame_index < total_frames):
        cap.release()
        raise IndexError(
            f"frame_index {frame_index} out of bounds (0 to {total_frames - 1})"
        )

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index - seek_offset)
    success, frame = cap.read()
    cap.release()

    if not success or frame is None:
        raise RuntimeError(f"Could not read frame {frame_index} from {video_path}")

    return frame


def crop_frame(frame: np.ndarray, roi: Tuple[int, int, int, int]) -> np.ndarray:
    """Return the (x, y, width, height) region of a frame (rows = y, cols = x)."""
    x, y, w, h = (int(v) for v in roi)
    return frame[y : y + h, x : x + w]


# ---------------------------------------------------------------------------
# Checks that a video belongs to its session, used before and during alignment.
# ---------------------------------------------------------------------------

_OBS_NAME_RE = re.compile(rf"^({_DATASET_PATTERN})\.(mkv|mp4)$")
_CAMERA_VIDEO_RE = re.compile(rf"^(.+?)_({_DATASET_PATTERN})_VIDEO(\d+)\.avi$")
_CAMERA_TS_RE = re.compile(rf"^TS_(.+?)_({_DATASET_PATTERN})_CAMERA(\d+)\.npy$")


def audit_video_files(
    obs_names: Iterable[str],
    camera_names: Iterable[str],
    known_datasets: Iterable[str],
    prefixes: Iterable[str],
    camera: int = 2,
) -> List[Tuple[str, str, str]]:
    """Problems with the files in the two input video folders.

    Args:
        obs_names: File names in the OBS recordings folder.
        camera_names: File names in the 3-camera input video folder.
        known_datasets: Datasets ingested in the pipeline (vr4mice.Dataset).
        prefixes: Accepted camera file prefixes (IMG_SRC).
        camera: Camera number of the input video.

    Returns:
        (folder, file name, issue) tuples, folder being "obs" or "camera".
    """
    known = set(known_datasets)
    prefixes = set(prefixes)
    issues = []
    not_ingested = "no session {} in vr4mice.Dataset (behavior not ingested?)"

    obs_datasets = {}
    for name in sorted(obs_names):
        match = _OBS_NAME_RE.match(name)
        if not match:
            issues.append(
                ("obs", name, "unexpected name (expected <dataset>.mkv/.mp4)")
            )
            continue
        obs_datasets[match.group(1)] = name
        if match.group(1) not in known:
            issues.append(("obs", name, not_ingested.format(match.group(1))))

    videos, stamps = {}, {}
    for name in sorted(camera_names):
        video, stamp = _CAMERA_VIDEO_RE.match(name), _CAMERA_TS_RE.match(name)
        match = video or stamp
        if not match:
            issues.append(
                (
                    "camera",
                    name,
                    f"unexpected name (expected <prefix>_<dataset>_VIDEO{camera}.avi "
                    f"or TS_<prefix>_<dataset>_CAMERA{camera}.npy)",
                )
            )
            continue
        prefix, dataset, number = match.group(1), match.group(2), int(match.group(3))
        if number != camera:
            issues.append(
                (
                    "camera",
                    name,
                    f"camera {number} file: only camera {camera} belongs here",
                )
            )
            continue
        if prefix not in prefixes:
            issues.append(("camera", name, f"unknown prefix {prefix!r} (IMG_SRC)"))
            continue
        (videos if video else stamps)[dataset] = name

    for dataset in sorted(set(videos) | set(stamps)):
        if dataset not in stamps:
            issues.append(
                (
                    "camera",
                    videos[dataset],
                    f"no TS_..._CAMERA{camera}.npy timestamps for it",
                )
            )
        elif dataset not in videos:
            issues.append(
                ("camera", stamps[dataset], f"no ..._VIDEO{camera}.avi for it")
            )
        elif dataset not in known:
            for name in (videos[dataset], stamps[dataset]):
                issues.append(("camera", name, not_ingested.format(dataset)))
        if dataset in obs_datasets and dataset in videos and dataset in stamps:
            issues.append(
                (
                    "obs",
                    obs_datasets[dataset],
                    "session also has camera files, which are used instead",
                )
            )
    return issues


def check_camera_timestamps(
    timestamps: np.ndarray,
    dataset: str,
    frame_interval_range: Tuple[float, float] = (0.002, 0.05),
    max_gap: float = 2.0,
) -> List[str]:
    """Problems with a camera's frame timestamps (unix seconds) for a session.

    Checks that they are unix times on the session's date (one day of slack for
    time zones), and that frames come at a plausible, gap-free rate.
    """
    timestamps = np.asarray(timestamps, dtype=float)
    problems = []
    if timestamps.ndim != 1 or timestamps.size < 2:
        return ["fewer than 2 timestamps"]
    if not np.all(np.isfinite(timestamps)):
        problems.append("non-finite timestamps")
        return problems
    if timestamps[0] < 1e9:
        problems.append(
            f"timestamps start at {timestamps[0]:.1f}: not unix times (another clock?)"
        )
        return problems

    expected = re.fullmatch(_DATASET_PATTERN, dataset)
    session_day = date.fromisoformat(dataset.split("_")[1]) if expected else None
    first_day = datetime.fromtimestamp(timestamps[0], timezone.utc).date()
    if session_day is not None and abs((first_day - session_day).days) > 1:
        problems.append(
            f"timestamps are from {first_day}, the session is from {session_day}: "
            "another session's timestamps?"
        )
    intervals = np.diff(timestamps)
    if np.any(intervals < 0):
        problems.append("timestamps are not sorted")
    median = float(np.median(intervals))
    if not frame_interval_range[0] <= median <= frame_interval_range[1]:
        problems.append(
            f"median frame interval {median * 1000:.1f} ms outside "
            f"{frame_interval_range[0] * 1000:.0f}-{frame_interval_range[1] * 1000:.0f} ms"
        )
    if intervals.max() > max_gap:
        problems.append(
            f"{intervals.max():.1f} s without frames at frame {int(np.argmax(intervals))}"
        )
    return problems


def match_edge_times(
    video_edge_times: np.ndarray, pd_edge_times: np.ndarray, tolerance: float = 0.05
) -> Tuple[float, float]:
    """Fraction of video edges with a photodiode edge within ``tolerance`` (s).

    Returns:
        (matched fraction, median |gap| in seconds), (0, nan) without edges.
    """
    v = np.asarray(video_edge_times, dtype=float)
    p = np.sort(np.asarray(pd_edge_times, dtype=float))
    if v.size == 0 or p.size == 0:
        return 0.0, float("nan")
    k = (
        np.clip(np.searchsorted(p, v), 1, len(p) - 1)
        if len(p) > 1
        else np.zeros(len(v), dtype=int)
    )
    gaps = np.minimum(np.abs(v - p[k]), np.abs(v - p[np.maximum(k - 1, 0)]))
    return float(np.mean(gaps <= tolerance)), float(np.median(gaps))


def verify_sync_against_photodiode(
    video_path: str,
    sync_roi: Tuple[int, int, int, int],
    frame_times: np.ndarray,
    pd_time: np.ndarray,
    pd_read: np.ndarray,
    n_windows: int = 3,
    window: int = 2000,
    tolerance: float = 0.05,
    seek_offset: int = 0,
) -> Dict[str, float]:
    """Check a camera video and its timestamps against the photodiode.

    The sync square is read in ``n_windows`` windows of ``window`` frames spread
    over the video; its rising edges, placed at the camera timestamps, must
    coincide with photodiode rising edges (same clock). A video paired with the
    wrong timestamps, or with another session, does not match.

    Returns:
        Dict with ``match_fraction``, ``median_gap`` (s) and ``n_edges``.
    """
    frame_times = np.asarray(frame_times, dtype=float)
    pd_time = np.asarray(pd_time, dtype=float)
    n = len(frame_times)
    edge_times = []
    for start in np.linspace(0.1 * n, 0.9 * n - window, n_windows).astype(int):
        start = int(np.clip(start, 0, max(n - window, 0)))
        trace = read_sync_trace(
            video_path, sync_roi, start=start, n_frames=window, seek_offset=seek_offset
        )
        if trace.size < 2 or np.ptp(trace) < 50:
            continue  # square not switching in this window
        on = binarize_sync_trace(trace)
        rises = np.flatnonzero((on[:-1] == 0) & (on[1:] == 1)) + 1
        edge_times.extend(frame_times[start + rises[start + rises < n]])
    edge_times = np.asarray(edge_times)

    best = {
        "match_fraction": 0.0,
        "median_gap": float("nan"),
        "n_edges": len(edge_times),
    }
    for invert in (False, True):
        pd_bin = _preprocess_photodiode(pd_read, pd_time, invert=invert)
        pd_edges = _detect_edges(pd_time, pd_bin, min_separation=0.1)
        fraction, gap = match_edge_times(edge_times, pd_edges, tolerance=tolerance)
        if fraction > best["match_fraction"]:
            best.update(match_fraction=fraction, median_gap=gap)
    return best
