#!/usr/bin/env python3
"""
Standalone script to synchronize video sync signal (numpy file) with photodiode signal (pickle file)
using first rising edge alignment.

Usage:
    python sync_from_files.py

Make sure to update the file paths and parameters in the script before running.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d


def find_rising_edges(time, signal, threshold=0.5):
    """Find rising edges in binary signal"""
    rising_edges = []
    for i in range(1, len(signal)):
        if signal[i - 1] < threshold and signal[i] >= threshold:
            rising_edges.append(time[i])
    return np.array(rising_edges)


def validate_edge_synchronization(
    photodiode_edges, video_edges, time_offset, tolerance=0.1
):
    """Validate synchronization quality by comparing edge timing patterns"""
    # Apply time offset to photodiode edges
    aligned_photodiode_edges = photodiode_edges + time_offset

    # Compare edge intervals for quality assessment
    if len(photodiode_edges) > 1 and len(video_edges) > 1:
        photo_intervals = np.diff(photodiode_edges)
        video_intervals = np.diff(video_edges)

        # Compare mean intervals
        photo_mean_interval = np.mean(photo_intervals)
        video_mean_interval = np.mean(video_intervals)

        if photo_mean_interval > 0 and video_mean_interval > 0:
            interval_ratio = min(photo_mean_interval, video_mean_interval) / max(
                photo_mean_interval, video_mean_interval
            )
            print(f"  Photodiode mean interval: {photo_mean_interval:.3f}s")
            print(f"  Video mean interval: {video_mean_interval:.3f}s")
            print(f"  Interval ratio: {interval_ratio:.3f}")
            return interval_ratio

    # Fallback: count matching edges within tolerance
    matches = 0
    max_edges_to_check = min(len(video_edges), len(aligned_photodiode_edges), 20)

    for i in range(max_edges_to_check):
        video_edge = video_edges[i]
        distances = np.abs(aligned_photodiode_edges - video_edge)
        if len(distances) > 0 and np.min(distances) < tolerance:
            matches += 1

    return matches / max_edges_to_check if max_edges_to_check > 0 else 0.0


def plot_synchronization_results(sync_results):
    """Plot synchronization results"""
    fig, axes = plt.subplots(4, 1, figsize=(15, 12))

    # Use cut signals for visualization (what was actually used for synchronization)
    photodiode_timestamps = sync_results["photodiode_timestamps"]
    video_timestamps = sync_results["video_timestamps"]
    photodiode_binary = sync_results["photodiode_binary"]
    video_binary = sync_results["video_binary"]
    time_offset = sync_results["time_offset"]

    # Also get original full timestamps for mapping statistics
    original_video_timestamps = sync_results.get(
        "original_video_timestamps", video_timestamps
    )
    original_photodiode_timestamps = sync_results.get(
        "original_photodiode_timestamps", photodiode_timestamps
    )

    # Show first 30 seconds for clarity
    time_limit = 30

    # Plot 1: Cut binary signals with first rising edges
    photo_mask = photodiode_timestamps <= time_limit
    video_mask = video_timestamps <= time_limit

    axes[0].plot(
        photodiode_timestamps[photo_mask],
        photodiode_binary[photo_mask],
        "g-",
        alpha=0.7,
        label="Photodiode binary (from 10s)",
    )
    axes[0].plot(
        video_timestamps[video_mask],
        video_binary[video_mask],
        "b-",
        alpha=0.7,
        label="Video binary (from 10s)",
    )

    # Mark first rising edges
    axes[0].axvline(
        x=sync_results["first_photodiode_edge"],
        color="green",
        linestyle="--",
        linewidth=2,
        label=f"First PD edge ({sync_results['first_photodiode_edge']:.3f}s)",
    )
    axes[0].axvline(
        x=sync_results["first_video_edge"],
        color="blue",
        linestyle="--",
        linewidth=2,
        label=f"First video edge ({sync_results['first_video_edge']:.3f}s)",
    )

    axes[0].set_title("Binary Signals Starting from 10s (sync region)")
    axes[0].set_ylabel("Binary Signal")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(0, time_limit)

    # Plot 2: Aligned signals
    aligned_photodiode_times = photodiode_timestamps + time_offset
    aligned_photo_mask = aligned_photodiode_times <= time_limit

    axes[1].plot(
        video_timestamps[video_mask],
        video_binary[video_mask],
        "b-",
        alpha=0.7,
        label="Video binary (from 10s)",
    )
    axes[1].plot(
        aligned_photodiode_times[aligned_photo_mask],
        photodiode_binary[aligned_photo_mask] + 0.1,
        "g-",
        alpha=0.7,
        label="Photodiode binary (aligned)",
    )

    axes[1].set_title(
        f'Aligned Binary Signals (offset: {time_offset:.3f}s, quality: {sync_results["sync_quality"]:.3f})'
    )
    axes[1].set_ylabel("Binary Signal")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlim(0, time_limit)

    # Plot 3: Mapping visualization using original timestamps
    frame_indices = list(sync_results["frame_to_timepoint_mapping"].keys())
    timepoint_indices = list(sync_results["frame_to_timepoint_mapping"].values())

    if len(frame_indices) > 0:
        # Show every 10th point for clarity
        step = max(1, len(frame_indices) // 1000)
        sample_frames = frame_indices[::step]
        sample_timepoints = timepoint_indices[::step]

        sample_video_times = [
            original_video_timestamps[f]
            for f in sample_frames
            if f < len(original_video_timestamps)
        ]
        sample_photo_times = [
            original_photodiode_timestamps[t]
            for t in sample_timepoints
            if t < len(original_photodiode_timestamps)
        ]

        if len(sample_video_times) == len(sample_photo_times):
            axes[2].plot(
                sample_video_times, sample_photo_times, "ro", alpha=0.5, markersize=2
            )
            axes[2].plot(
                [0, time_limit], [0, time_limit], "k--", alpha=0.5, label="Perfect sync"
            )
            axes[2].set_xlabel("Video Time (s)")
            axes[2].set_ylabel("Photodiode Time (s)")
            axes[2].set_title("Frame-to-Timepoint Mapping (original timestamps)")
            axes[2].legend()
            axes[2].grid(True, alpha=0.3)
            axes[2].set_xlim(0, time_limit)
            axes[2].set_ylim(0, time_limit)

    # Plot 4: Summary statistics
    summary_text = f"""Synchronization Summary:

Results:
- Time offset: {time_offset:.3f}s
- Sync quality: {sync_results['sync_quality']:.3f}
- Photodiode edges: {sync_results['photodiode_edges']}
- Video edges: {sync_results['video_edges']}

Mapping:
- Total video frames: {len(original_video_timestamps)}
- Total photodiode timepoints: {len(original_photodiode_timestamps)}
- Mapped frames: {len(sync_results['frame_to_timepoint_mapping'])}
- Mapped timepoints: {len(sync_results['timepoint_to_frame_mapping'])}
- Coverage: {len(sync_results['frame_to_timepoint_mapping'])/len(original_video_timestamps)*100:.1f}% of video frames

Time Ranges (original):
- Video: {original_video_timestamps[0]:.2f}s to {original_video_timestamps[-1]:.2f}s
- Photodiode: {original_photodiode_timestamps[0]:.2f}s to {original_photodiode_timestamps[-1]:.2f}s

Time Ranges (sync region from 10s):
- Video: {video_timestamps[0]:.2f}s to {video_timestamps[-1]:.2f}s
- Photodiode: {photodiode_timestamps[0]:.2f}s to {photodiode_timestamps[-1]:.2f}s

Quality: {'✓ Excellent' if sync_results['sync_quality'] > 0.9 else '✓ Good' if sync_results['sync_quality'] > 0.7 else '~ Moderate' if sync_results['sync_quality'] > 0.5 else '⚠️ Poor'}
"""

    axes[3].text(
        0.05,
        0.95,
        summary_text,
        transform=axes[3].transAxes,
        verticalalignment="top",
        fontfamily="monospace",
        fontsize=9,
    )
    axes[3].set_xlim(0, 1)
    axes[3].set_ylim(0, 1)
    axes[3].axis("off")

    plt.tight_layout()
    plt.savefig("synchronization_results.png", dpi=150, bbox_inches="tight")
    plt.show()

    print("Synchronization plot saved as 'synchronization_results.png'")


def main():
    # ===== CONFIGURATION - UPDATE THESE PATHS =====
    sync_signal_npy_path = (
        "/app/sync_signal.npy"  # Path to your video sync signal (numpy file)
    )
    photodiode_pickle_path = (
        "/app/photodiode_read.pkl"  # Path to your photodiode signal (pickle file)
    )

    # Sampling rates
    video_fps = 120.0  # Video frame rate in Hz
    photodiode_sampling_rate = 1000.0  # Photodiode sampling rate in Hz (corrected)

    print("=== Loading Signals ===")

    # Load video sync signal from numpy file
    print(f"Loading video sync signal from: {sync_signal_npy_path}")
    try:
        video_sync_signal = np.load(sync_signal_npy_path)
        print(f"✓ Video sync signal loaded: {len(video_sync_signal)} samples")
        print(
            f"  Signal range: {np.min(video_sync_signal):.3f} to {np.max(video_sync_signal):.3f}"
        )
    except FileNotFoundError:
        print(f"✗ Error: Video sync signal file not found: {sync_signal_npy_path}")
        return
    except Exception as e:
        print(f"✗ Error loading video sync signal: {e}")
        return

    # Load photodiode signal from pickle file
    print(f"Loading photodiode signal from: {photodiode_pickle_path}")
    try:
        photodiode_data = pd.read_pickle(photodiode_pickle_path)

        # Handle different data formats
        if isinstance(photodiode_data, pd.DataFrame):
            # If it's a DataFrame, extract the signal column
            if "photodiode_read" in photodiode_data.columns:
                photodiode_signal = photodiode_data["photodiode_read"].values
                print(f"  Using 'photodiode_read' column")
            else:
                # Use first numeric column
                numeric_cols = photodiode_data.select_dtypes(
                    include=[np.number]
                ).columns
                if len(numeric_cols) > 0:
                    photodiode_signal = photodiode_data[numeric_cols[0]].values
                    print(f"  Using column '{numeric_cols[0]}' as photodiode signal")
                else:
                    raise ValueError("No numeric columns found in photodiode DataFrame")
        else:
            # If it's a numpy array or other format
            photodiode_signal = np.array(photodiode_data)
            print(f"  Loaded as numpy array")

        print(f"✓ Photodiode signal loaded: {len(photodiode_signal)} samples")
        print(
            f"  Signal range: {np.min(photodiode_signal):.3f} to {np.max(photodiode_signal):.3f}"
        )

    except FileNotFoundError:
        print(f"✗ Error: Photodiode signal file not found: {photodiode_pickle_path}")
        return
    except Exception as e:
        print(f"✗ Error loading photodiode signal: {e}")
        return

    print("\n=== Processing Signals ===")

    # Create timestamps for original signals
    video_timestamps_original = np.arange(len(video_sync_signal)) / video_fps
    photodiode_timestamps = np.arange(len(photodiode_signal)) / photodiode_sampling_rate

    print(f"Original video duration: {video_timestamps_original[-1]:.2f} seconds")
    print(f"Photodiode duration: {photodiode_timestamps[-1]:.2f} seconds")

    # Resample video signal to match photodiode sampling rate
    print(
        f"Resampling video signal from {video_fps} Hz to {photodiode_sampling_rate} Hz..."
    )

    # Create new time array for resampled video at photodiode sampling rate
    video_duration = len(video_sync_signal) / video_fps
    video_timestamps_resampled = np.arange(
        0, video_duration, 1 / photodiode_sampling_rate
    )

    # Interpolate video signal to match photodiode sampling rate
    from scipy.interpolate import interp1d

    video_interpolator = interp1d(
        video_timestamps_original,
        video_sync_signal,
        kind="linear",
        bounds_error=False,
        fill_value="extrapolate",
    )
    video_sync_resampled = video_interpolator(video_timestamps_resampled)

    print(f"Resampled video signal: {len(video_sync_resampled)} samples")
    print(f"Resampled video duration: {video_timestamps_resampled[-1]:.2f} seconds")

    # Binarize resampled video sync signal
    video_signal_min = np.min(video_sync_resampled)
    video_signal_max = np.max(video_sync_resampled)
    video_threshold = video_signal_min + (video_signal_max - video_signal_min) * 0.5
    video_binary = (video_sync_resampled > video_threshold).astype(int)
    print(f"Video signal binarized with threshold: {video_threshold:.3f}")
    print(
        f"  Binary signal: {np.sum(video_binary)} high samples ({np.mean(video_binary)*100:.1f}%)"
    )

    # Binarize photodiode signal if not already binary
    if not np.all(np.isin(photodiode_signal, [0, 1])):
        photodiode_threshold = np.mean(photodiode_signal) + 0.5 * np.std(
            photodiode_signal
        )
        photodiode_binary = (photodiode_signal > photodiode_threshold).astype(int)
        print(f"Photodiode signal binarized with threshold: {photodiode_threshold:.3f}")
    else:
        photodiode_binary = photodiode_signal.astype(int)
        print("Photodiode signal already binary")

    print(
        f"  Binary signal: {np.sum(photodiode_binary)} high samples ({np.mean(photodiode_binary)*100:.1f}%)"
    )

    # Now both signals are at the same sampling rate
    print(f"Both signals now at {photodiode_sampling_rate} Hz sampling rate")

    print("\n=== Starting Synchronization from 10 Seconds ===")

    # Start synchronization from 10 seconds to account for photodiode recording delay
    # but keep original frame indices for mapping
    start_time = 10.0  # seconds

    # Find indices for starting synchronization
    video_start_idx = int(start_time * photodiode_sampling_rate)
    photodiode_start_idx = int(start_time * photodiode_sampling_rate)

    # Get signals starting from 10 seconds for synchronization
    if video_start_idx < len(video_timestamps_resampled):
        video_timestamps_sync = video_timestamps_resampled[video_start_idx:]
        video_binary_sync = video_binary[video_start_idx:]
        print(
            f"Video synchronization starting from index {video_start_idx} ({video_timestamps_sync[0]:.3f}s)"
        )
    else:
        print("Warning: Video signal is shorter than 10 seconds, using original signal")
        video_timestamps_sync = video_timestamps_resampled
        video_binary_sync = video_binary
        video_start_idx = 0

    # Get photodiode signal starting from 10 seconds
    if photodiode_start_idx < len(photodiode_timestamps):
        photodiode_timestamps_sync = photodiode_timestamps[photodiode_start_idx:]
        photodiode_binary_sync = photodiode_binary[photodiode_start_idx:]
        print(
            f"Photodiode synchronization starting from index {photodiode_start_idx} ({photodiode_timestamps_sync[0]:.3f}s)"
        )
    else:
        print(
            "Warning: Photodiode signal is shorter than 10 seconds, using original signal"
        )
        photodiode_timestamps_sync = photodiode_timestamps
        photodiode_binary_sync = photodiode_binary
        photodiode_start_idx = 0

    print("\n=== Synchronizing Signals ===")

    # Find rising edges in both signals starting from 10 seconds
    photodiode_rising_edges = find_rising_edges(
        photodiode_timestamps_sync, photodiode_binary_sync
    )
    video_rising_edges = find_rising_edges(video_timestamps_sync, video_binary_sync)

    print(f"Detected {len(photodiode_rising_edges)} photodiode rising edges")
    print(f"Detected {len(video_rising_edges)} video rising edges")

    if len(photodiode_rising_edges) == 0 or len(video_rising_edges) == 0:
        print("✗ Error: No rising edges found in one or both signals")
        return

    # Use first photodiode rising edge as reference
    first_photodiode_edge = photodiode_rising_edges[0]
    print(
        f"Using first photodiode rising edge as reference: {first_photodiode_edge:.3f}s"
    )

    # Find the video rising edge that occurs closest to the photodiode reference time
    # This handles the case where video signal starts before photodiode signal
    video_edge_diffs = np.abs(np.array(video_rising_edges) - first_photodiode_edge)
    closest_video_edge_idx = np.argmin(video_edge_diffs)
    corresponding_video_edge = video_rising_edges[closest_video_edge_idx]

    # Calculate time offset based on photodiode reference
    time_offset = corresponding_video_edge - first_photodiode_edge

    print(f"Photodiode-referenced synchronization:")
    print(f"  Reference photodiode edge: {first_photodiode_edge:.3f}s")
    print(f"  Corresponding video edge: {corresponding_video_edge:.3f}s")
    print(f"  Time offset: {time_offset:.3f}s")
    print(
        f"  Video edge index used: {closest_video_edge_idx} (out of {len(video_rising_edges)} video edges)"
    )

    # Validate synchronization quality
    sync_quality = validate_edge_synchronization(
        photodiode_rising_edges, video_rising_edges, time_offset
    )
    print(f"  Sync quality: {sync_quality:.3f}")

    # Create frame-to-timepoint mapping
    frame_to_timepoint_mapping = {}
    timepoint_to_frame_mapping = {}

    print("\n=== Creating Mapping ===")

    # Create photodiode-based mapping starting from first timepoint
    # For each photodiode timepoint, find corresponding video frame
    photodiode_mapping_data = []

    for timepoint_idx, photodiode_time in enumerate(photodiode_timestamps):
        # Apply offset to get corresponding video time
        video_time = photodiode_time + time_offset

        # Find closest resampled video frame
        resampled_frame_idx = None
        original_frame_idx = None

        if (
            video_time >= video_timestamps_resampled[0]
            and video_time <= video_timestamps_resampled[-1]
        ):
            # Find closest index in resampled video timestamps
            closest_resampled_idx = np.argmin(
                np.abs(video_timestamps_resampled - video_time)
            )
            resampled_frame_idx = closest_resampled_idx

            # Convert resampled frame index to original video frame index
            # Since resampled is at 1000Hz and original is at 120Hz
            original_frame_idx = int(
                closest_resampled_idx * video_fps / photodiode_sampling_rate
            )

            # Make sure original frame index is within bounds
            if original_frame_idx >= len(video_timestamps_original):
                original_frame_idx = len(video_timestamps_original) - 1

            frame_to_timepoint_mapping[closest_resampled_idx] = timepoint_idx
            timepoint_to_frame_mapping[timepoint_idx] = closest_resampled_idx

        # Add to mapping data (photodiode timepoint, resampled frame, original frame)
        photodiode_mapping_data.append(
            [
                timepoint_idx,  # photodiode timepoint index
                resampled_frame_idx
                if resampled_frame_idx is not None
                else np.nan,  # resampled video frame
                original_frame_idx
                if original_frame_idx is not None
                else np.nan,  # original video frame
            ]
        )

    print(f"Created mapping for {len(photodiode_timestamps)} photodiode timepoints")
    print(f"Valid frame mappings: {len(frame_to_timepoint_mapping)}")

    # Export photodiode-based mapping to CSV
    if len(photodiode_mapping_data) > 0:
        mapping_array = np.array(photodiode_mapping_data)
        header = "photodiode_timepoint_index,resampled_video_frame_index,original_video_frame_index"

        # Handle NaN values for CSV output
        mapping_df = pd.DataFrame(mapping_array, columns=header.split(","))
        mapping_df.to_csv("photodiode_timepoint_mapping.csv", index=False)
        print(
            f"✓ Photodiode-based mapping exported to: photodiode_timepoint_mapping.csv"
        )

        # Also create the original frame-based mapping for backward compatibility
        frame_mapping_data = []
        for frame_idx, timepoint_idx in frame_to_timepoint_mapping.items():
            # Convert resampled frame to original frame
            original_frame_idx = int(frame_idx * video_fps / photodiode_sampling_rate)
            if original_frame_idx >= len(video_timestamps_original):
                original_frame_idx = len(video_timestamps_original) - 1
            frame_mapping_data.append([original_frame_idx, timepoint_idx])

        if len(frame_mapping_data) > 0:
            frame_mapping_array = np.array(frame_mapping_data)
            frame_header = "original_video_frame_index,photodiode_timepoint_index"
            np.savetxt(
                "frame_timepoint_mapping.csv",
                frame_mapping_array,
                delimiter=",",
                header=frame_header,
                fmt="%d",
                comments="",
            )
            print(f"✓ Frame-based mapping exported to: frame_timepoint_mapping.csv")

    # Prepare results for plotting
    sync_results = {
        "frame_to_timepoint_mapping": frame_to_timepoint_mapping,
        "timepoint_to_frame_mapping": timepoint_to_frame_mapping,
        "time_offset": time_offset,
        "sync_quality": sync_quality,
        "photodiode_edges": len(photodiode_rising_edges),
        "video_edges": len(video_rising_edges),
        "first_photodiode_edge": first_photodiode_edge,
        "first_video_edge": corresponding_video_edge,
        "photodiode_timestamps": photodiode_timestamps_sync,  # Use sync signals for plotting
        "video_timestamps": video_timestamps_sync,
        "photodiode_binary": photodiode_binary_sync,
        "video_binary": video_binary_sync,
        "original_video_timestamps": video_timestamps_resampled,  # Original timestamps for mapping
        "original_photodiode_timestamps": photodiode_timestamps,
    }

    # Plot results
    plot_synchronization_results(sync_results)

    print("\n=== Example Queries ===")

    # Example queries for photodiode timepoints
    example_timepoints = [100, 500, 1000, 2000, 5000]
    print("Photodiode timepoint -> Video frame:")
    for timepoint_idx in example_timepoints:
        if timepoint_idx < len(photodiode_timestamps):
            resampled_frame_idx = timepoint_to_frame_mapping.get(timepoint_idx, None)
            if resampled_frame_idx is not None:
                original_frame_idx = int(
                    resampled_frame_idx * video_fps / photodiode_sampling_rate
                )
                if original_frame_idx >= len(video_timestamps_original):
                    original_frame_idx = len(video_timestamps_original) - 1
                print(
                    f"  Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s) -> Original frame {original_frame_idx} ({original_frame_idx/video_fps:.3f}s)"
                )
            else:
                print(
                    f"  Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s) -> No corresponding frame"
                )

    # Example queries for original video frames
    example_frames = [100, 500, 1000, 2000, 5000]
    print("Original video frame -> Photodiode timepoint:")
    for original_frame_idx in example_frames:
        if original_frame_idx < len(video_timestamps_original):
            # Convert to resampled frame index
            resampled_frame_idx = int(
                original_frame_idx * photodiode_sampling_rate / video_fps
            )
            if resampled_frame_idx < len(video_timestamps_resampled):
                timepoint_idx = frame_to_timepoint_mapping.get(
                    resampled_frame_idx, None
                )
                if timepoint_idx is not None:
                    print(
                        f"  Original frame {original_frame_idx} ({original_frame_idx/video_fps:.3f}s) -> Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s)"
                    )
                else:
                    print(
                        f"  Original frame {original_frame_idx} ({original_frame_idx/video_fps:.3f}s) -> No corresponding timepoint"
                    )

    print("\n=== Summary ===")
    print(f"✓ Successfully synchronized {len(frame_to_timepoint_mapping)} frames")
    print(f"✓ Sync quality: {sync_quality:.3f}")
    print(f"✓ Files created:")
    print(f"  - photodiode_timepoint_mapping.csv (primary mapping)")
    print(f"  - frame_timepoint_mapping.csv (backward compatibility)")
    print(f"  - synchronization_results.png")

    # Show usage example
    print(f"\n=== Usage Example ===")
    print(f"# Primary CSV (photodiode_timepoint_mapping.csv) structure:")
    print(f"# - photodiode_timepoint_index: Index in photodiode signal")
    print(f"# - resampled_video_frame_index: Frame index in resampled video (1000Hz)")
    print(f"# - original_video_frame_index: Frame index in original video (120fps)")
    print(f"# - NaN values indicate no corresponding frame for that timepoint")
    print(f"# Total photodiode timepoints: {len(photodiode_timestamps)}")
    print(
        f"# Synchronized timepoints: {len(timepoint_to_frame_mapping)} ({len(timepoint_to_frame_mapping)/len(photodiode_timestamps)*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
