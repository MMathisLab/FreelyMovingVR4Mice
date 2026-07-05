import numpy as np
import pandas as pd
import scipy.signal
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

_PROC_NUMERIC_KEYS = (
    "frame_time",
    "time_stamp",
    "photodiode_read",
    "photodiode_time",
    "signal",
)


def load_proc_dict(raw) -> dict:
    """Return a dict from a PROC np.load result (handles 0-d object arrays)."""
    if isinstance(raw, np.ndarray) and raw.ndim == 0:
        raw = raw.item()
    if not isinstance(raw, dict):
        raise TypeError(f"PROC file must contain a dict, got {type(raw)}")
    return raw


def _coerce_float_array(value, name: str) -> np.ndarray:
    arr = np.asarray(value)
    if arr.dtype.kind in {"U", "S", "O"}:
        try:
            arr = arr.astype(float)
        except (ValueError, TypeError) as err:
            raise TypeError(f"{name} is not numeric (dtype={arr.dtype})") from err
    return np.asarray(arr, dtype=float)


def _coerce_float_scalar(value, name: str) -> float:
    return float(_coerce_float_array(value, name).reshape(-1)[0])


def normalize_proc_data(data: dict) -> dict:
    """
    Coerce PROC timing/signal fields to float arrays.

    Some older PROC files store timestamps as short string arrays; numpy
    arithmetic on those dtypes raises ufunc errors during latency checks.
    """
    data = dict(data)
    for key in _PROC_NUMERIC_KEYS:
        if key in data:
            data[key] = _coerce_float_array(data[key], key)

    if "start_time" in data:
        data["start_time"] = _coerce_float_scalar(data["start_time"], "start_time")
    elif "photodiode_time" in data and len(data["photodiode_time"]):
        data["start_time"] = float(np.min(data["photodiode_time"]))
    elif "frame_time" in data and len(data["frame_time"]):
        data["start_time"] = float(np.min(data["frame_time"]))
    else:
        data["start_time"] = 0.0

    if "signal_delay" in data and data["signal_delay"] is not None:
        data["signal_delay"] = _coerce_float_scalar(
            data["signal_delay"], "signal_delay"
        )

    return data


def check_data(data: dict):
    """
    Check that photodiode and generated signals are both in the dictionary

    Args:
        data (dict): Dictionary containing the photodiode and generated signal data.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    try:
        data = normalize_proc_data(data)
        for var in _PROC_NUMERIC_KEYS:
            if var not in data:
                raise ValueError(f"{var} not found in PROC file")
    except (ValueError, TypeError) as e:
        logger.warning("Session population failed: %s", e)
        return False

    return has_signal(data)


def has_signal(data, mean_threshold: float = 8.0):
    """Check if the photodiode signal is present in the data.

    Args:
        data (dict): Dictionary containing the photodiode and generated signal data.
        mean_threshold (float): Threshold for detecting the signal presence, default is 8.0.
    """
    photodiode_time = data["photodiode_time"] - data["start_time"]
    signal = data["photodiode_read"] * detect_signal_polarity(data["photodiode_read"])

    try:
        delay = (
            data["frame_time"][np.where(data["signal"] > 0.5)[0][0]]
            - data["start_time"]
        )
    except (IndexError, TypeError, ValueError) as e:
        logger.warning("Error finding delay, %s.", e)
        return False

    mean_start = np.mean(
        signal[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    )

    # NOTE(celia): DOESN'T WORK as it's about the range of values rather than the scale
    # check if peak-to-peak distance is above mean noise:
    # std = np.std(
    #     signal[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    # )
    # peak_to_peak = np.max(signal) - np.min(signal)
    # is_signal_present = peak_to_peak > (mean_start + threshold_sigma * std)

    is_signal_present = mean_start > mean_threshold

    if not is_signal_present:
        logger.debug(
            "No significant signal detected, make sure the photodiode was recording."
        )
    return is_signal_present


def detect_signal_polarity(photodiode_read):
    """Calculate the mean value prior to signal coming in."""
    read = photodiode_read
    read = read - np.mean(read[0:100])

    if np.abs(np.min(read)) > np.abs(np.max(read)):
        return -1
    else:
        return 1


def filter_pulsed_signal(signal, sample_rate, cutoff_freq=50, filter_order=5):
    """Filters high-frequency noise from a pulsed signal.

    Args:
        signal: The input signal with noise
        sample_rate: Sampling rate in Hz
        cutoff_freq: Cutoff frequency for the low-pass filter in Hz (default 50Hz)
        filter_order: Order of the Butterworth filter (default 5)

    Returns:
        filtered_signal: The filtered output signal
    """
    # Calculate Nyquist frequency
    nyquist = 0.5 * sample_rate

    # Design Butterworth low-pass filter
    b, a = scipy.signal.butter(
        N=filter_order, Wn=cutoff_freq / nyquist, btype="low", analog=False
    )

    # Apply zero-phase filtering (filtfilt to avoid phase shift)
    # NOTE(celia): as filtfilt applies the filter twice,
    # the filter_order is doubled so we could use a lower order filter than 5.
    filtered_signal = scipy.signal.filtfilt(b, a, signal)

    return filtered_signal


def find_rising_edges(time, signal, threshold=0.5):
    """Calculate the rising edge of the photodiode and signal.

    Args:
        time (np.ndarray): Time array corresponding to the signal.
        signal (np.ndarray): Signal array to find rising edges in.
        threshold (float): Threshold value to determine rising edges. Default is 0.5.

    Note:
        When signal crosses from < threshold to >= threshold.
    """
    signal = np.asarray(signal)
    time = np.asarray(time)

    prev = signal[:-1] < threshold
    curr = signal[1:] >= threshold
    rising_indices = np.where(prev & curr)[0] + 1  # shift by 1 for correct time index

    return time[rising_indices]


def detect_signal_polarity(photodiode_read):
    """Calculate the mean value prior to signal coming in to scale the signal and scale the trace."""
    read = photodiode_read
    read = read - np.mean(read[0:100])

    if np.abs(np.min(read)) > np.abs(np.max(read)):
        # flipping signal
        return -1
    else:
        return 1


def get_latency(rising_edges_singal, rising_edges_photodiode):
    rising_edges_singal = np.array(rising_edges_singal)
    rising_edges_photodiode = np.array(rising_edges_photodiode)
    if len(rising_edges_singal) < 2:
        return pd.DataFrame(columns=["frame_time", "time_diff", "photodiode_time"])

    signal_starts = rising_edges_singal[:-1]
    signal_ends = rising_edges_singal[1:]

    # Use searchsorted to find indices where photodiode times fall into intervals
    photodiode_idx_start = np.searchsorted(
        rising_edges_photodiode, signal_starts, side="right"
    )
    photodiode_idx_end = np.searchsorted(
        rising_edges_photodiode, signal_ends, side="left"
    )

    frame_time = []
    time_diff = []
    photodiode_time = []

    for i in range(len(signal_starts)):
        # Get photodiode events within interval [start, end]
        pd_in_window = rising_edges_photodiode[
            photodiode_idx_start[i] : photodiode_idx_end[i]
        ]

        if len(pd_in_window) > 0:
            dists = np.abs(pd_in_window - signal_starts[i])
            closest_idx = np.argmin(dists)
            closest_val = pd_in_window[closest_idx]

            frame_time.append(signal_starts[i])
            photodiode_time.append(closest_val)
            time_diff.append(closest_val - signal_starts[i])

    return pd.DataFrame(
        {
            "frame_time": frame_time,
            "time_diff": time_diff,
            "photodiode_time": photodiode_time,
        }
    )


def get_signals(data, threshold=0.2):
    """
    Processes photodiode and generated signal data from a PROC file and returns a merged DataFrame
    containing aligned signal and photodiode values.

    Args:
        data (dict): Dictionary containing the following
            - 'photodiode_read': Photodiode signal values.
            - 'photodiode_time': Time stamps of the photodiode signal.
            - 'start_time': Start time of the recording.
            - 'generated_frame_time': Time stamps of the generated frame.
            - 'generated_send_time': Time stamps of the generated signal send times.
            - 'generated_signal': Generated signal values.
        threshold (float, optional): Threshold for the signal. Default is 0.2.

    Returns:
        pd.DataFrame: A DataFrame containing synchronized and processed signal and photodiode data, with the following columns:
            - 'time_stamp': Time stamps
            - 'send_time': Adjusted signal send times.
            - 'frame_to_socket_time': Absolute difference between the frame and signal send times.
            - 'signal_read': Generated signal values, shifted to frame times
            - 'photodiode_read': Thresholded photodiode values.
            - 'photodiode_raw_scaled': Scaled raw photodiode readings.

    Notes:
        - The function adjusts the photodiode signal to remove an initial thread-starting point, scales it based on
          pre-signal mean and max values, and applies a threshold based on the standard deviation of the pre-signal values.
        - The function merges the processed photodiode data with the signal data based on time alignment.
    """

    data = normalize_proc_data(data)
    photodiode_read = data["photodiode_read"]
    photodiode_time = data["photodiode_time"] - data["start_time"]

    # estimate the delay by find the first point where sent signal is 1
    delay = (
        data["generated_frame_time"][np.where(data["generated_signal"] > 0.5)[0][0]]
        - data["start_time"]
    )
    logger.info("Delay: %s", delay)

    # remove first point as this corresponds to the thread starting
    if len(photodiode_time) != len(photodiode_read):
        photodiode_read = photodiode_read[1:]
    photodiode_read = photodiode_read[photodiode_time > 1]
    photodiode_time = photodiode_time[photodiode_time > 1]

    flip_photodiode_signal = detect_signal_polarity(photodiode_read)

    # NOTE(celia): in newer recordings, photodiode signal is sampled at 1000Hz,
    # so we can use a lower sample rate to filter the signal, in older recordings
    # the photodiode signal is sampled at 50Hz, so we do not apply the filter.
    sampling_rate = int(1 // np.mean(np.diff(photodiode_time)))
    if sampling_rate > 70:
        filtered_photodiode_read = (
            filter_pulsed_signal(
                signal=photodiode_read, sample_rate=sampling_rate, cutoff_freq=50
            )
            * flip_photodiode_signal
        )
    else:
        logger.info(
            f"Photodiode signal sampled at {sampling_rate}, skipping filtering step."
        )
        filtered_photodiode_read = photodiode_read * flip_photodiode_signal

    # Calculate the mean value prior to signal coming in to scale the signal and scale the trace
    filtered_mean_start = np.mean(
        filtered_photodiode_read[
            (photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)
        ]
    )
    filtered_photodiode_scaled = (filtered_photodiode_read - filtered_mean_start) / (
        np.max(filtered_photodiode_read) - filtered_mean_start
    )

    raw_mean_start = np.mean(
        photodiode_read[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    )

    raw_photodiode_signal_scaled = (photodiode_read - raw_mean_start) / (
        np.max(photodiode_read) - raw_mean_start
    )

    # Binarise the signal
    photodiode_read = filtered_photodiode_scaled > threshold

    signal_time = data["generated_frame_time"]
    send_time = data["generated_send_time"]
    signal_read = data["generated_signal"]
    signal_time = signal_time - data["start_time"]
    send_time = send_time - data["start_time"]

    signal = pd.DataFrame(
        {
            "time_stamp": signal_time,
            "send_time": send_time,
            "frame_to_socket_time": abs(signal_time - send_time),
            "signal_read": signal_read,
        }
    )
    photodiode = pd.DataFrame(
        {
            "time_stamp": photodiode_time,
            "photodiode_read": photodiode_read,
            "photodiode_raw_scaled": raw_photodiode_signal_scaled,
            "filtered_photodiode_scaled": filtered_photodiode_scaled,
            "threshold": threshold,
        }
    )
    df = pd.merge_asof(left=photodiode, right=signal, on="time_stamp")

    df["signal_read"] = df.signal_read.ffill()

    return df
