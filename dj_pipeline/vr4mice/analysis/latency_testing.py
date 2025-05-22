import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt


def check_data(data):
    """
    Check that photodiode and generated signals are both in the dictionary

    """
    # first check that all data variables are present
    vars = [
        "frame_time",
        "frame_time",
        "timestamp",
        "photodiode_read",
        "photodiode_time",
        "signal",
    ]
    for var in vars:
        if var not in data:
            raise ValueError(f"{var} not found in PROC file")
            return False

    # check that there is a photodiode signal present
    photodiode_read = data["photodiode_read"] * detect_signal_polarity(
        data["photodiode_read"]
    )
    min_photodiode_read = np.min(photodiode_read)
    max_photodiode_read = np.max(photodiode_read)

    has_signal(data)

    return True


def has_signal(data, threshold_sigma=8.0):
    photodiode_time = data["photodiode_time"] - data["start_time"]
    signal = data["photodiode_read"] * detect_signal_polarity(data["photodiode_read"])

    try:
        delay = (
            data["frame_time"][np.where(data["signal"] > 0.5)[0][0]]
            - data["start_time"]
        )
    except:
        return False

    # check if peak signal is above noise threshold
    min_start = np.mean(
        signal[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    )
    std = np.std(
        signal[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    )
    peak_to_peak = np.max(signal) - np.min(signal)

    # Signal likely present if peak-to-peak is significantly larger than noise
    return peak_to_peak > (min_start + threshold_sigma * std)


def detect_signal_polarity(photodiode_read):
    # Calculate the mean value prior to signal coming in to scale the signal and scale the trace
    read = photodiode_read
    read = read - np.mean(read[0:100])

    if np.abs(np.min(read)) > np.abs(np.max(read)):
        return -1
        print("flipping signal")
    else:
        print("not flipping signal")
        return 1


def filter_pulsed_signal(signal, sample_rate, cutoff_freq=50, filter_order=5):
    """
    Filters high-frequency noise from a pulsed signal and plots the results.

    Parameters:
    - signal: The input signal with noise
    - sample_rate: Sampling rate in Hz

    - cutoff_freq: Cutoff frequency for the low-pass filter in Hz (default 50Hz)
    - filter_order: Order of the Butterworth filter (default 5)

    Returns:
    - filtered_signal: The filtered output signal
    """
    # Calculate Nyquist frequency
    nyquist = 0.5 * sample_rate

    # Design Butterworth low-pass filter
    b, a = butter(filter_order, cutoff_freq / nyquist, btype="low", analog=False)

    # Apply zero-phase filtering (filtfilt to avoid phase shift)
    filtered_signal = filtfilt(b, a, signal)

    return filtered_signal


def find_rising_edges(time, signal, threshold=0.5):
    "calculates the rising edges of photodiode and signal."
    rising_edges = []
    for i in range(1, len(signal)):
        if signal[i - 1] < threshold and signal[i] >= threshold:
            rising_edges.append(time[i])
    return rising_edges


def detect_signal_polarity(photodiode_read):
    # Calculate the mean value prior to signal coming in to scale the signal and scale the trace
    read = photodiode_read
    read = read - np.mean(read[0:100])

    if np.abs(np.min(read)) > np.abs(np.max(read)):
        print("flipping signal")
        return -1
    else:
        print("not flipping signal")
        return 1


def get_latency(rising_edges_singal, rising_edges_photodiode):
    latencies = []

    # Convert to numpy arrays if they aren't already
    rising_edges_singal = np.array(rising_edges_singal)
    rising_edges_photodiode = np.array(rising_edges_photodiode)

    for i in range(len(rising_edges_singal) - 1):
        start = rising_edges_singal[i]
        end = rising_edges_singal[i + 1]

        # Find photodiode edges between current and next signal edge
        mask = (rising_edges_photodiode > start) & (rising_edges_photodiode < end)
        temp_photodiode = rising_edges_photodiode[mask]

        if len(temp_photodiode) > 0:
            closest = temp_photodiode[np.argmin(np.abs(temp_photodiode - start))]
            latencies.append(
                {
                    "frame_time": start,
                    "time_diff": closest - start,
                    "photodiode_time": closest,
                }
            )

    return pd.DataFrame(latencies)


def get_signals(data, threshold=0.2):
    """
    Processes photodiode and generated signal data from a PROC file and returns a merged DataFrame
    containing aligned signal and photodiode values.

    Args:
        data (dict):

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

    photodiode_read = data["photodiode_read"]
    photodiode_time = data["photodiode_time"] - data["start_time"]

    # estimate the delay by find the first point where sent signal is 1
    delay = (
        data["generated_frame_time"][np.where(data["generated_signal"] > 0.5)[0][0]]
        - data["start_time"]
    )
    print("delay: ", delay)

    # remove first point as this corresponds to the thread starting
    if len(photodiode_time) != len(photodiode_read):
        photodiode_read = photodiode_read[1:]
    photodiode_read = photodiode_read[photodiode_time > 1]
    photodiode_time = photodiode_time[photodiode_time > 1]

    flip_photodiode_signal = detect_signal_polarity(photodiode_read)
    filtered_photodiode_read = (
        filter_pulsed_signal(
            photodiode_read, int(1 // np.mean(np.diff(photodiode_time))), cutoff_freq=50
        )
        * flip_photodiode_signal
    )
    # Calculate the mean value prior to signal coming in to scale the signal and scale the trace
    min_start = np.mean(
        filtered_photodiode_read[
            (photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)
        ]
    )
    filtered_photodiode_scaled = (filtered_photodiode_read - min_start) / (
        np.max(filtered_photodiode_read) - min_start
    )

    min_start = np.mean(
        photodiode_read[(photodiode_time > delay - 3) & (photodiode_time < delay - 0.5)]
    )
    photodiode_read = (photodiode_read - min_start) / (
        np.max(photodiode_read) - min_start
    )
    photodiode_signal_scaled = photodiode_read

    # binarise the signal
    photodiode_read = photodiode_read > threshold

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
            "photodiode_raw_scaled": photodiode_signal_scaled,
            "filtered_photodiode_scaled": filtered_photodiode_scaled,
            "threshold": threshold,
        }
    )
    df = pd.merge_asof(left=photodiode, right=signal, on="time_stamp")

    df["signal_read"] = df.signal_read.ffill()
    df["photodiode_read"] = df.photodiode_read

    return df
