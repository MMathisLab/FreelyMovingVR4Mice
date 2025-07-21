#!/usr/bin/env python3
"""
Standalone script to synchronize video sync signal with photodiode signal
using first rising edge alignment and export mapping to CSV.
"""

import numpy as np
import pandas as pd


def find_rising_edges(time, signal, threshold=0.5):
    """Find rising edges in binary signal"""
    rising_edges = []
    for i in range(1, len(signal)):
        if signal[i - 1] < threshold and signal[i] >= threshold:
            rising_edges.append(time[i])
    return np.array(rising_edges)


def main():
    # Configuration - update these paths
    sync_signal_pickle_path = "/app/sync_signal.pkl"
    photodiode_pickle_path = "/app/photodiode.pkl"

    # Load video sync signal DataFrame
    video_sync_df = pd.read_pickle(sync_signal_pickle_path)
    video_timestamps = video_sync_df["timestamp"].values
    video_signal = video_sync_df["signal"].values

    # Load photodiode signal DataFrame
    photodiode_df = pd.read_pickle(photodiode_pickle_path)
    photodiode_timestamps = photodiode_df["time_stamp"].values
    photodiode_signal = photodiode_df["photodiode_read"].values

    # Convert signals to binary
    video_binary = video_signal.astype(int)
    photodiode_binary = photodiode_signal.astype(int)

    # Find signals starting from 10 seconds
    start_time = 10.0

    video_start_mask = video_timestamps >= start_time
    if np.any(video_start_mask):
        video_timestamps_sync = video_timestamps[video_start_mask]
        video_binary_sync = video_binary[video_start_mask]
    else:
        video_timestamps_sync = video_timestamps
        video_binary_sync = video_binary

    photodiode_start_mask = photodiode_timestamps >= start_time
    if np.any(photodiode_start_mask):
        photodiode_timestamps_sync = photodiode_timestamps[photodiode_start_mask]
        photodiode_binary_sync = photodiode_binary[photodiode_start_mask]
    else:
        photodiode_timestamps_sync = photodiode_timestamps
        photodiode_binary_sync = photodiode_binary

    # Find rising edges in both signals
    photodiode_rising_edges = find_rising_edges(
        photodiode_timestamps_sync, photodiode_binary_sync
    )
    video_rising_edges = find_rising_edges(video_timestamps_sync, video_binary_sync)

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

        photodiode_mapping_data.append(
            [
                timepoint_idx,
                video_frame_idx if video_frame_idx is not None else np.nan,
                original_frame_idx if original_frame_idx is not None else np.nan,
            ]
        )

    # Export to CSV
    if len(photodiode_mapping_data) > 0:
        mapping_array = np.array(photodiode_mapping_data)
        header = (
            "photodiode_timepoint_index,video_frame_index,original_video_frame_index"
        )
        mapping_df = pd.DataFrame(mapping_array, columns=header.split(","))
        mapping_df.to_csv("photodiode_timepoint_mapping.csv", index=False)


if __name__ == "__main__":
    main()
