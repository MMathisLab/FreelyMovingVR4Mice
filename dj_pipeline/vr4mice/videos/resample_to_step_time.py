#!/usr/bin/env python3
"""
Script to map synchronized video frames to step_time intervals.

This script takes:
1. A synchronized DataFrame with video_frame_index and send_time columns
2. A dictionary with 'dlc_read_time' and 'step_time' keys containing corresponding time arrays

Both time arrays correspond to the same session and start at the same time.

Usage:
    python resample_to_step_time.py

Make sure to update the file paths in the configuration section.
"""

import numpy as np
import pandas as pd
import os


def map_video_frames_to_step_time(sync_df, time_dict):
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
        - One row per step_time (including NaN video_frame when no corresponding frame exists)
    """

    print(f"=== Mapping Video Frames to Step Time ===")
    print(f"Synchronized video data: {len(sync_df)} samples")

    # Ensure we have the required columns in sync_df
    required_sync_cols = ["video_frame_index", "send_time"]

    for col in required_sync_cols:
        if col not in sync_df.columns:
            raise ValueError(f"Missing required column '{col}' in sync DataFrame")

    # Extract arrays from synchronized data
    sync_send_times = sync_df["send_time"].values
    video_frames = sync_df["video_frame_index"].values

    # Extract time arrays from dictionary
    if "dlc_read_time" not in time_dict or "step_time" not in time_dict:
        available_keys = list(time_dict.keys())
        raise ValueError(
            f"Dictionary must contain 'dlc_read_time' and 'step_time' keys. Available keys: {available_keys}"
        )

    dict_dlc_times = np.array(time_dict["dlc_read_time"])
    dict_step_times = np.array(time_dict["step_time"])

    print(f"Dictionary DLC read times: {len(dict_dlc_times)} samples")
    print(f"Dictionary step times: {len(dict_step_times)} samples")

    print(
        f"Sync send time range: {sync_send_times[0]:.3f}s to {sync_send_times[-1]:.3f}s"
    )
    print(
        f"Dict DLC read time range: {dict_dlc_times[0]:.3f}s to {dict_dlc_times[-1]:.3f}s"
    )
    print(
        f"Dict step time range: {dict_step_times[0]:.3f}s to {dict_step_times[-1]:.3f}s"
    )

    # Calculate sampling rates
    sync_send_rate = 1.0 / np.mean(np.diff(sync_send_times))
    dict_dlc_rate = (
        1.0 / np.mean(np.diff(dict_dlc_times)) if len(dict_dlc_times) > 1 else 0
    )
    step_rate = (
        1.0 / np.mean(np.diff(dict_step_times)) if len(dict_step_times) > 1 else 0
    )

    print(f"Sync send time sampling rate: {sync_send_rate:.1f} Hz")
    print(f"Dict DLC read time sampling rate: {dict_dlc_rate:.1f} Hz")
    print(f"Step time sampling rate: {step_rate:.1f} Hz")

    # Find overlapping time range
    min_time = max(sync_send_times[0], dict_dlc_times[0])
    max_time = min(sync_send_times[-1], dict_dlc_times[-1])

    print(f"Overlapping time range: {min_time:.3f}s to {max_time:.3f}s")

    # For each step time, find video frames that fall within that time interval
    print(f"Mapping video frames to step time intervals")

    # The dlc_read_time and step_time arrays have different sampling rates
    # but they correspond to the same session timeline
    # The send_time in sync_df is also in relative time like step_time
    # So we should map step_time directly to send_time

    # Create a mapping for ALL step_times, including those without corresponding video frames
    step_times_list = []
    send_times_list = []
    dlc_read_times_list = []
    video_frames_list = []

    for i, step_time in enumerate(dict_step_times):
        # Always add this step_time to our output
        step_times_list.append(step_time)

        # Get the corresponding dlc_read_time for this step_time
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

        # Find video frames that have send_time close to this step_time
        # Use a tolerance based on the step time sampling rate
        time_tolerance = (
            1.0 / step_rate if step_rate > 0 else 0.1
        )  # Use step sampling period as tolerance

        # Find all video frames within this time window
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
            # No corresponding video frame found
            video_frames_list.append(np.nan)
            send_times_list.append(np.nan)

    print(f"Processed {len(step_times_list)} step times")
    valid_frames = sum(1 for frame in video_frames_list if not np.isnan(frame))
    print(f"Found {valid_frames} step times with corresponding video frames")

    # Create the main resampled dataset with ALL step times
    resampled_data = pd.DataFrame(
        {
            "step_time": step_times_list,
            "dlc_read_time": dlc_read_times_list,
            "send_time": send_times_list,
            "video_frame": video_frames_list,
        }
    )

    # Sort by step_time
    resampled_data = resampled_data.sort_values("step_time").reset_index(drop=True)

    print(f"Resampled dataset (all step times): {len(resampled_data)} samples")
    valid_frames = resampled_data["video_frame"].notna().sum()
    print(f"Step times with valid video frames: {valid_frames} samples")

    # Calculate statistics
    if valid_frames > 0:
        original_range = [video_frames.min(), video_frames.max()]
        valid_video_frames = resampled_data["video_frame"].dropna()
        resampled_range = [valid_video_frames.min(), valid_video_frames.max()]

        print(f"Original frame range: {original_range[0]} to {original_range[1]}")
        print(f"Resampled frame range: {resampled_range[0]} to {resampled_range[1]}")

    return resampled_data


def main():
    # ===== CONFIGURATION - UPDATE THESE PATHS =====
    sync_file_path = "/app/now_photodiode.pkl"  # Synchronized video data with video_frame_index and send_time
    time_dict_file_path = "/app/vr4mice/videos/full_videos_2/CeliaTest_2025-07-18_1.pickle"  # Dictionary with 'dlc_read_time' and 'step_time' keys

    output_resampled_path = "/app/video_frames_resampled_to_step_time.csv"

    print("=== Loading Data ===")

    # Load synchronized video data
    print(f"Loading synchronized data from: {sync_file_path}")
    try:
        if sync_file_path.endswith(".pkl"):
            sync_df = pd.read_pickle(sync_file_path)
        else:
            sync_df = pd.read_csv(sync_file_path)
        print(f"✓ Synchronized data loaded: {len(sync_df)} rows")
        print(f"  Columns: {list(sync_df.columns)}")

        # Check if we need to rename columns
        if (
            "video_frame_index" not in sync_df.columns
            or "send_time" not in sync_df.columns
        ):
            # Try to find similar column names
            possible_frame_cols = [
                col for col in sync_df.columns if "frame" in col.lower()
            ]
            possible_time_cols = [
                col
                for col in sync_df.columns
                if "send" in col.lower() and "time" in col.lower()
            ]
            if not possible_time_cols:
                possible_time_cols = [
                    col for col in sync_df.columns if "time" in col.lower()
                ]

            if possible_frame_cols and possible_time_cols:
                print(
                    f"  Auto-detecting columns: frame='{possible_frame_cols[0]}', time='{possible_time_cols[0]}'"
                )
                sync_df = sync_df.rename(
                    columns={
                        possible_frame_cols[0]: "video_frame_index",
                        possible_time_cols[0]: "send_time",
                    }
                )
            else:
                print(f"  Available columns: {list(sync_df.columns)}")
                raise ValueError(
                    "Could not find video_frame_index and send_time columns"
                )

    except FileNotFoundError:
        print(f"✗ Error: Synchronized data file not found: {sync_file_path}")
        return
    except Exception as e:
        print(f"✗ Error loading synchronized data: {e}")
        return

    # Load time dictionary
    print(f"Loading time dictionary from: {time_dict_file_path}")
    try:
        if time_dict_file_path.endswith(".pkl") or time_dict_file_path.endswith(
            ".pickle"
        ):
            time_dict = pd.read_pickle(time_dict_file_path)
        elif time_dict_file_path.endswith(".json"):
            import json

            with open(time_dict_file_path, "r") as f:
                time_dict = json.load(f)
        else:
            raise ValueError("Time dictionary file must be .pkl or .json format")

        print(f"✓ Time dictionary loaded")
        print(f"  Keys: {list(time_dict.keys())}")

        # Show sample data
        if "dlc_read_time" in time_dict and "step_time" in time_dict:
            dlc_times = time_dict["dlc_read_time"]
            step_times = time_dict["step_time"]
            print(f"  DLC read times: {len(dlc_times)} samples")
            print(f"  Step times: {len(step_times)} samples")
            print(f"  DLC read time range: {dlc_times[0]:.3f}s to {dlc_times[-1]:.3f}s")
            print(f"  Step time range: {step_times[0]:.3f}s to {step_times[-1]:.3f}s")
        else:
            available_keys = list(time_dict.keys())
            print(
                f"  Error: Expected 'dlc_read_time' and 'step_time' keys, found: {available_keys}"
            )
            return

    except FileNotFoundError:
        print(f"✗ Error: Time dictionary file not found: {time_dict_file_path}")
        return
    except Exception as e:
        print(f"✗ Error loading time dictionary: {e}")
        return

    # Perform mapping
    try:
        resampled_data = map_video_frames_to_step_time(sync_df, time_dict)

        # Save results
        print(f"\n=== Saving Results ===")

        # Save resampled data (all step times with corresponding frames or NaN)
        resampled_data.to_csv(output_resampled_path, index=False)
        print(f"✓ Resampled data saved to: {output_resampled_path}")
        print(f"  Shape: {resampled_data.shape}")
        print(f"  Columns: {list(resampled_data.columns)}")

        # Show sample data
        print(f"\n=== Sample Resampled Data ===")
        print(resampled_data.head(10))

        # Show summary statistics
        valid_frames = resampled_data["video_frame"].notna().sum()
        total_step_times = len(resampled_data)
        coverage_percent = (valid_frames / total_step_times) * 100

        print(f"\n=== Summary ===")
        print(f"✓ Successfully processed {len(sync_df)} video frames")
        print(f"✓ Total step times: {total_step_times}")
        print(f"✓ Step times with video frames: {valid_frames}")
        print(f"✓ Coverage: {coverage_percent:.1f}%")
        print(f"✓ Output file: {output_resampled_path}")

    except Exception as e:
        print(f"✗ Error during mapping: {e}")
        return


if __name__ == "__main__":
    main()
