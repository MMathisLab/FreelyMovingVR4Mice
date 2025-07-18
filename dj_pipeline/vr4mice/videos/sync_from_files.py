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

        # Get timestamps using the original data arrays
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
            axes[2].set_title("Frame-to-Timepoint Mapping")
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
    sync_signal_pickle_path = "/app/sync_signal.pkl"  # Path to video sync signal DataFrame
    photodiode_pickle_path = "/app/photodiode.pkl"  # Path to photodiode signal DataFrame
    
    # Sampling rates (for reference, but we'll use the timestamps from DataFrames)
    video_fps = 120.0  # Video frame rate in Hz
    photodiode_sampling_rate = 1000.0  # Photodiode sampling rate in Hz
    
    print("=== Loading Signals ===")
    
    # Load video sync signal DataFrame
    print(f"Loading video sync signal from: {sync_signal_pickle_path}")
    try:
        video_sync_df = pd.read_pickle(sync_signal_pickle_path)
        print(f"✓ Video sync DataFrame loaded: {len(video_sync_df)} rows")
        print(f"  Columns: {list(video_sync_df.columns)}")
        print(f"  Duration: {video_sync_df['timestamp'].max():.2f} seconds")
        
        # Extract signal and timestamps
        video_timestamps = video_sync_df['timestamp'].values
        video_signal = video_sync_df['signal'].values
        
        print(f"  Signal range: {np.min(video_signal)} to {np.max(video_signal)}")
        
    except FileNotFoundError:
        print(f"✗ Error: Video sync signal file not found: {sync_signal_pickle_path}")
        return
    except Exception as e:
        print(f"✗ Error loading video sync signal: {e}")
        return
    
    # Load photodiode signal DataFrame
    print(f"Loading photodiode signal from: {photodiode_pickle_path}")
    try:
        photodiode_df = pd.read_pickle(photodiode_pickle_path)
        print(f"✓ Photodiode DataFrame loaded: {len(photodiode_df)} rows")
        print(f"  Columns: {list(photodiode_df.columns)}")
        print(f"  Duration: {photodiode_df['time_stamp'].max():.2f} seconds")
        
        # Extract signal and timestamps
        photodiode_timestamps = photodiode_df['time_stamp'].values
        photodiode_signal = photodiode_df['photodiode_read'].values
        
        print(f"  Signal range: {np.min(photodiode_signal.astype(int))} to {np.max(photodiode_signal.astype(int))}")
        
    except FileNotFoundError:
        print(f"✗ Error: Photodiode signal file not found: {photodiode_pickle_path}")
        return
    except Exception as e:
        print(f"✗ Error loading photodiode signal: {e}")
        return

    print("\n=== Processing Signals ===")
    
    # Since we have timestamps, we don't need to create them from scratch
    print(f"Video signal duration: {video_timestamps[-1]:.2f} seconds")
    print(f"Photodiode signal duration: {photodiode_timestamps[-1]:.2f} seconds")
    
    # Convert video signal to binary if needed (it should already be binary)
    video_binary = video_signal.astype(int)
    print(f"Video binary signal: {np.sum(video_binary)} high samples ({np.mean(video_binary)*100:.1f}%)")
    
    # Convert photodiode signal to binary if needed (it should already be binary)
    photodiode_binary = photodiode_signal.astype(int)
    print(f"Photodiode binary signal: {np.sum(photodiode_binary)} high samples ({np.mean(photodiode_binary)*100:.1f}%)")
    
    print("\n=== Starting Synchronization from 10 Seconds ===")
    
    # Find signals starting from 10 seconds
    start_time = 10.0  # seconds
    
    # Get video signal starting from 10 seconds
    video_start_mask = video_timestamps >= start_time
    if np.any(video_start_mask):
        video_timestamps_sync = video_timestamps[video_start_mask]
        video_binary_sync = video_binary[video_start_mask]
        print(f"Video synchronization starting from {video_timestamps_sync[0]:.3f}s")
        print(f"Video sync signal: {len(video_timestamps_sync)} samples")
    else:
        print("Warning: Video signal is shorter than 10 seconds, using original signal")
        video_timestamps_sync = video_timestamps
        video_binary_sync = video_binary
    
    # Get photodiode signal starting from 10 seconds
    photodiode_start_mask = photodiode_timestamps >= start_time
    if np.any(photodiode_start_mask):
        photodiode_timestamps_sync = photodiode_timestamps[photodiode_start_mask]
        photodiode_binary_sync = photodiode_binary[photodiode_start_mask]
        print(f"Photodiode synchronization starting from {photodiode_timestamps_sync[0]:.3f}s")
        print(f"Photodiode sync signal: {len(photodiode_timestamps_sync)} samples")
    else:
        print("Warning: Photodiode signal is shorter than 10 seconds, using original signal")
        photodiode_timestamps_sync = photodiode_timestamps
        photodiode_binary_sync = photodiode_binary

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

    # Use first photodiode rising edge as reference and find the video edge just before it
    first_photodiode_edge = photodiode_rising_edges[0]
    
    # Find the video rising edge that occurs just before the first photodiode edge
    # Look for video edges that are before the photodiode edge
    video_edges_before = video_rising_edges[video_rising_edges < first_photodiode_edge]
    
    if len(video_edges_before) == 0:
        print("✗ Error: No video rising edges found before the first photodiode edge")
        print(f"  First photodiode edge: {first_photodiode_edge:.3f}s")
        print(f"  Video edges: {video_rising_edges[:5] if len(video_rising_edges) > 0 else 'None'}")
        return
    
    # Use the last video edge before the photodiode edge (closest preceding edge)
    corresponding_video_edge = video_edges_before[-1]
    
    # Calculate time offset based on aligning these edges
    time_offset = corresponding_video_edge - first_photodiode_edge
    
    print(f"Photodiode-referenced synchronization:")
    print(f"  First photodiode edge: {first_photodiode_edge:.3f}s")
    print(f"  Corresponding video edge (just before): {corresponding_video_edge:.3f}s")
    print(f"  Time offset: {time_offset:.3f}s")

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

        # Find closest video frame using DataFrame
        video_frame_idx = None
        original_frame_idx = None

        if video_time >= video_timestamps[0] and video_time <= video_timestamps[-1]:
            # Find closest timestamp in video DataFrame
            time_diffs = np.abs(video_timestamps - video_time)
            closest_idx = np.argmin(time_diffs)
            
            # Get the original frame index from the DataFrame
            original_frame_idx = video_sync_df.iloc[closest_idx]['frame']
            video_frame_idx = closest_idx

            frame_to_timepoint_mapping[closest_idx] = timepoint_idx
            timepoint_to_frame_mapping[timepoint_idx] = closest_idx

        # Add to mapping data (photodiode timepoint, video frame, original frame)
        photodiode_mapping_data.append(
            [
                timepoint_idx,  # photodiode timepoint index
                video_frame_idx if video_frame_idx is not None else np.nan,  # video frame
                original_frame_idx if original_frame_idx is not None else np.nan,  # original video frame
            ]
        )

    print(f"Created mapping for {len(photodiode_timestamps)} photodiode timepoints")
    print(f"Valid frame mappings: {len(frame_to_timepoint_mapping)}")

    # Export photodiode-based mapping to CSV
    if len(photodiode_mapping_data) > 0:
        mapping_array = np.array(photodiode_mapping_data)
        header = "photodiode_timepoint_index,video_frame_index,original_video_frame_index"

        # Handle NaN values for CSV output
        mapping_df = pd.DataFrame(mapping_array, columns=header.split(","))
        mapping_df.to_csv("photodiode_timepoint_mapping.csv", index=False)
        print(
            f"✓ Photodiode-based mapping exported to: photodiode_timepoint_mapping.csv"
        )

        # Also create the original frame-based mapping for backward compatibility
        frame_mapping_data = []
        for frame_idx, timepoint_idx in frame_to_timepoint_mapping.items():
            # Get the original frame index from the video DataFrame
            original_frame_idx = video_sync_df.iloc[frame_idx]['frame']
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
        "original_video_timestamps": video_timestamps,  # Original timestamps for mapping
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
            video_frame_idx = timepoint_to_frame_mapping.get(timepoint_idx, None)
            if video_frame_idx is not None:
                original_frame_idx = video_sync_df.iloc[video_frame_idx]['frame']
                frame_time = video_sync_df.iloc[video_frame_idx]['timestamp']
                print(
                    f"  Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s) -> Original frame {original_frame_idx} ({frame_time:.3f}s)"
                )
            else:
                print(
                    f"  Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s) -> No corresponding frame"
                )

    # Example queries for original video frames
    example_frames = [100, 500, 1000, 2000, 5000]
    print("Original video frame -> Photodiode timepoint:")
    for original_frame_idx in example_frames:
        # Find the DataFrame row with this original frame index
        frame_rows = video_sync_df[video_sync_df['frame'] == original_frame_idx]
        if len(frame_rows) > 0:
            video_frame_idx = frame_rows.index[0]
            timepoint_idx = frame_to_timepoint_mapping.get(video_frame_idx, None)
            if timepoint_idx is not None:
                frame_time = frame_rows.iloc[0]['timestamp']
                print(
                    f"  Original frame {original_frame_idx} ({frame_time:.3f}s) -> Timepoint {timepoint_idx} ({photodiode_timestamps[timepoint_idx]:.3f}s)"
                )
            else:
                print(
                    f"  Original frame {original_frame_idx} -> No corresponding timepoint"
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
    print(f"# - video_frame_index: Frame index in video DataFrame")
    print(f"# - original_video_frame_index: Frame index in original video (120fps)")
    print(f"# - NaN values indicate no corresponding frame for that timepoint")
    print(f"# Total photodiode timepoints: {len(photodiode_timestamps)}")
    print(
        f"# Synchronized timepoints: {len(timepoint_to_frame_mapping)} ({len(timepoint_to_frame_mapping)/len(photodiode_timestamps)*100:.1f}%)"
    )


if __name__ == "__main__":
    main()
