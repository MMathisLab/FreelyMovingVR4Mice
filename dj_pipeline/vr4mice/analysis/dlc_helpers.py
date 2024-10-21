import bisect
import math
from typing import List, Tuple, Union

import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.signal


def _sync_dlc_with_game(game_data: pd.DataFrame, dlc_df: pd.DataFrame) -> pd.DataFrame:
    """Synchronizes DLC pose time data with game step time data.

    This function adjusts the DLC data (pose times) by subtracting the game's start time
    and aligns it with the game step times. It uses the closest matching times from the
    game data to adjust the DLC DataFrame, adding corresponding step and step time information.

    Args:
        game_data (pd.DataFrame): DataFrame containing game-related data, including 'step' and 'step_time'.
        dlc_df (pd.DataFrame): DataFrame containing DLC-related data, including 'pose_time'.

    Returns:
        pd.DataFrame: The synchronized DLC DataFrame, with added columns for 'step' and 'step_time' from game_data.

    Modifies:
        Adds columns "index/pose_time", "index/step", and "index/step_time" to `dlc_df`.
    """

    pose_time = np.array(dlc_df["pose_time"] - game_data["start_time"][0])
    step_time = np.array(game_data["step_time"])
    dlc_df[("index", "pose_time")] = pose_time

    closest_indices = find_closest_indices(pose_time, step_time)
    dlc_df = dlc_df.iloc[closest_indices].reset_index(drop=True)
    dlc_df[("index", "step")] = game_data["step"]
    dlc_df[("index", "step_time")] = game_data["step_time"]
    return dlc_df


def sync_keypoint_table(
    dataset_key: str, keypoint_cuttoff: float = 0.6, filter_window_length: int = 10
) -> pd.DataFrame:
    """Returns filtered keypoints from the DLCKptsDF table synchronized with game data.

    This function loads the DLCKptsDF keypoint table for dataset d,  replaces low confidence
    frames with a linearly interpolates between confident points and filters with a Savgol filter.

    Args:
        dataset_key (str):  the data set key formatted as "mouseName_date_attempt".
        keypoint_cuttoff (float): All keypoints below this confidence threshold will be removed
            and interpolated.
        filter_window_length (int): The window in frames for the filter window size.

    Returns:
        pd.Dataframe: filtered and synchronized keypoints with game indexes - step and step_time

    """
    from vr4mice.schema import base_analysis, dlc, vr4mice

    # Get time indexes from the game dataframe and the start time for session
    game_step_times = pd.DataFrame(
        (base_analysis.DataFrame() & dataset_key).fetch(
            "step_time", "step", "time_elapsed", "trial", as_dict=True
        )[0]
    )
    start_time = (vr4mice.State() & dataset_key).fetch("start_time")[0]
    game_step_times["start_time"] = start_time

    # Fetch the keypoint table and then sychronise with the game timesteps
    keypoint_df = dlc.DLCKptsDf().get_data(dataset_key)
    filt_dlc_df = filter_dlc(
        keypoint_df, cutoff=keypoint_cuttoff, window_length=filter_window_length
    )
    return _sync_dlc_with_game(game_data=game_step_times, dlc=filt_dlc_df)


def dlc_interpolate(
    trace: Union[List, npt.NDArray],
    likelihood: Union[List, npt.NDArray],
    cutoff: float = 0.6,
) -> npt.NDArray:
    """Interpolates the trace based on likelihood cutoff.

    Replaces values in the trace with NaN where the likelihood is below the cutoff and performs interpolation
    to fill in missing values.

    Args:
        trace (array-like): The trace data to be interpolated.
        likelihood (array-like): The likelihood values corresponding to the trace.
        cutoff (float, optional): The likelihood threshold below which values are considered unreliable. Default is 0.6.

    Returns:
        np.ndarray: The interpolated trace with low-confidence points replaced and interpolated.
    """
    trace = np.array(trace)
    low_confidence_points = np.where(np.array(likelihood) < cutoff)
    trace[low_confidence_points] = np.nan
    trace_nan_below_cutoff = trace
    df = pd.Series(trace_nan_below_cutoff)
    df = df.interpolate().ffill().bfill()
    interpolated_trace = np.array(df)
    return interpolated_trace


def dlc_savgol_filter(
    trajectory: Union[list, npt.NDArray],
    window_length_jitter: int = 9,
    polyorder: int = 3,
) -> npt.NDArray:
    """Applies a Savitzky-Golay filter to smooth the trajectory data.

    The function uses a Savitzky-Golay filter to smooth the input trajectory,
    replacing NaN values with zero before filtering.

    Args:
        trajectory (array-like): The trajectory data to be smoothed.
        window_length_jitter (int, optional): The window length for the filter.
            Must be a positive odd integer. Default is 9.
        polyorder (int, optional): The order of the polynomial to fit within the
        window. Default is 3.

    Returns:
        np.ndarray: The smoothed trajectory.
    """
    filtered_trajectory = np.nan_to_num(
        scipy.signal.savgol_filter(
            trajectory, window_length=window_length_jitter, polyorder=polyorder
        )
    )
    return filtered_trajectory


def filter_dlc(
    dlc_dict: pd.DataFrame,
    cutoff: float = 0.4,
    window_length: int = 9,
    polyorder: int = 3,
) -> pd.DataFrame:
    """Filter keypoints data based on likelihood, interpolate missing values, and apply a Savitzky-Golay filter.

    Args:
        dlc_dict (pd.DataFrame): Dataframe containing the keypoints data.
        cutoff (float): Likelihood threshold below which values are considered missing and set to NaN.
        window_length (int): Length of the filter window (i.e., the number of coefficients). Must be an odd number.
        polyorder (int): Order of the polynomial used to fit the samples. Must be less than window_length.

    Returns:
        pd.DataFrame: The filtered DataFrame.
    """

    body_parts = dlc_dict.columns.get_level_values(0).unique()[:-2]
    for b in body_parts:
        # Copy the relevant columns to avoid chained assignment
        key_point_x = dlc_dict[b, "x"].copy()
        key_point_y = dlc_dict[b, "y"].copy()
        likelihood = dlc_dict[b, "likelihood"]

        # Mask low likelihood points as NaN and interpolate missing values
        trace_x = dlc_interpolate(key_point_x, likelyhood=likelihood, cutoff=cutoff)
        trace_y = dlc_interpolate(key_point_y, likelyhood=likelihood, cutoff=cutoff)

        # Apply Savitzky-Golay filter
        trace_x = dlc_savgol_filter(trace_x, window_length, polyorder)
        trace_y = dlc_savgol_filter(trace_y, window_length, polyorder)

        # Update original DataFrame using loc
        dlc_dict.loc[:, (b, "x")] = trace_x
        dlc_dict.loc[:, (b, "y")] = trace_y

    return dlc_dict


def _compute_single_heading_angle(
    filtered_dlc_row: pd.Series,
) -> Tuple[float, float, float, float, npt.NDArray, npt.NDArray]:
    """Computes the heading and head angles from DLC tracking data.

    The function calculates the animal's heading angle (body orientation) and head angle
    (relative head orientation to the body) based on filtered DLC data. It also returns
    the body and head axes.

    Args:
        filtered_dlc_row (pd.Series): A row of DLC data with multi-level indices, where the 'coords' level contains x, y, and confidence.

    Returns:
        tuple: A tuple containing:
            - center_x (float): The x-coordinate of the weighted average center of the head.
            - center_y (float): The y-coordinate of the weighted average center of the head.
            - heading (float): The heading angle (orientation of the body) in degrees.
            - head_angle (float): The head angle relative to the body in degrees.
            - body_axis (np.ndarray): The unit vector representing the body axis.
            - head_axis (np.ndarray): The unit vector representing the head axis.
    """
    pose = np.array(filtered_dlc_row.unstack(level="coords"))
    xy = pose[:, :2]
    conf = pose[:, 2]
    head_xy = xy[[0, 1, 2, 3, 4, 5, 6, 26], :]
    head_conf = conf[[0, 1, 2, 3, 4, 5, 6, 26]]
    center = np.average(head_xy, axis=0, weights=head_conf)

    body_axis = xy[7] - xy[13]  # tail_base -> neck
    body_axis /= np.sqrt(np.sum(body_axis**2))

    head_axis = xy[0] - xy[7]  # neck -> nose
    head_axis /= np.sqrt(np.sum(head_axis**2))

    cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
    sign = math.copysign(1, cross)  # Positive when looking left

    try:
        head_angle = math.acos(body_axis @ head_axis) * sign
    except ValueError:
        head_angle = 0
    heading = math.atan2(body_axis[1], body_axis[0])
    heading = math.degrees(heading)
    head_angle = math.degrees(head_angle)

    return center[0], center[1], heading, head_angle, body_axis, head_axis


def compute_head_angles(filtered_dlc: pd.DataFrame) -> pd.DataFrame:
    """Computes heading direction and head angles for all frames in DLC data.

    Iterates through each row of filtered DLC data to calculate the heading direction,
    head angle, and the body and head axes for each frame. Stores the results in a DataFrame.

    Args:
        filtered_dlc (pd.DataFrame): DataFrame containing filtered DLC data for multiple frames.

    Returns:
        pd.DataFrame: A DataFrame with the following columns:
            - "head_center_x" (float): The x-coordinate of the weighted average center of the head for each frame.
            - "head_center_y" (float): The y-coordinate of the weighted average center of the head for each frame.
            - "heading_dir" (float): The heading angle (orientation of the body) in degrees for each frame.
            - "head_angle" (float): The head angle relative to the body in degrees for each frame.
    """

    def _compute_angles(row):
        x, y, heading_angle, head_angle, _, _ = _compute_single_heading_angle(row[:-2])
        return pd.Series([x, y, heading_angle, head_angle])

    results = filtered_dlc.apply(_compute_angles, axis=1)

    df = pd.DataFrame(
        results, columns=["head_center_x", "head_center_y", "heading_dir", "head_angle"]
    )

    return df


def find_closest_indices(pose_time: List[int], step_time: List[int]) -> List[int]:
    """Finds the index of the closest point in `pose_time` for each entry in `step_time`.

    This function uses binary search to efficiently find the closest indices in `pose_time`
    corresponding to each timestamp in `step_time`.

    Args:
        pose_time (List[int]): Sorted list of timestamps representing pose times.
        step_time (List[int]): List of timestamps for which to find the closest points.

    Returns:
        List[int]: A list of indices in `pose_time` corresponding to each entry in `step_time`.
    """
    closest_indices = []

    for step in step_time:
        idx = bisect.bisect_left(pose_time, step)

        if idx == 0:
            closest_indices.append(0)
        elif idx == len(pose_time):
            closest_indices.append(len(pose_time) - 1)
        else:
            before = pose_time[idx - 1]
            after = pose_time[idx]
            closest_indices.append(idx if step - before > after - step else idx - 1)

    return closest_indices


# TODO(celia): not used in the codebase but could be used later.
def compute_circular_angular_velocity(
    angles: Union[list, npt.NDArray], time_intervals: Union[list, npt.NDArray]
) -> npt.NDArray:
    """Computes the circular angular velocity of an angle changing over time.

    Args:
        angles (array-like): Array of angles in radians.
        time_intervals (array-like): Array of time intervals corresponding to the angles.

    Returns:
        numpy array: Array of circular angular velocities.
    """

    # Convert inputs to numpy arrays
    angles = np.asarray(angles, dtype=np.float64)
    time_intervals = np.asarray(time_intervals, dtype=np.float64)
    angles = np.deg2rad(angles)

    # Ensure angles are wrapped between -pi and pi for circular continuity
    # Compute the sine and cosine of the angles
    angles_wrapped = np.unwrap(angles)
    sin_angles = np.sin(angles_wrapped)
    cos_angles = np.cos(angles_wrapped)

    # Compute the derivatives of sine and cosine with respect to time
    d_sin = np.diff(sin_angles) / np.diff(time_intervals)
    d_cos = np.diff(cos_angles) / np.diff(time_intervals)

    # Calculate the angular velocity using the formula
    angular_velocity = cos_angles[:-1] * d_sin - sin_angles[:-1] * d_cos

    return np.insert(angular_velocity, 0, 0)
