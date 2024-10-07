import bisect
from math import acos, atan2, copysign, degrees, pi, sqrt

from IPython.display import clear_output, display

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.signal import find_peaks, hilbert, savgol_filter


def get_dlc_steps_in_VR_game(step_time, dlc_times):
    """
    Computes for each dlc_time the closest element index in step time.
    :param step_time: step times in the game, should be sorted in ascending order
    :param dlc_times: DLC timestamps, should be sorted in ascending order
    :return: numpy array containing the index of the closest step for each dlc timestamp.
    """
    dlc_steps = np.zeros(len(dlc_times), dtype=int)
    step_time_index = 0
    for i in range(dlc_steps.size):
        current_distance = np.abs(step_time[step_time_index] - dlc_times[i])
        found_step = False
        while not found_step:
            if step_time_index == len(step_time) - 1:
                dlc_steps[i] = step_time_index
                found_step = True
            else:
                next_distance = np.abs(step_time[step_time_index + 1] - dlc_times[i])
                if next_distance >= current_distance:
                    dlc_steps[i] = step_time_index
                    found_step = True
                else:
                    current_distance = next_distance
                    step_time_index += 1

    return dlc_steps


# TODO: proper loader for all types all files
# NOTE: since the database is in use, we are not supposed to use this "raw" loader anymore!
def _load_dlc_proc_files(
    camera_name="Imagingsource",
    mouse_name="30559",
    date="2024-02-14",
    attempt="1",
    path="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/",
):
    dlc_dict = pd.read_hdf(
        path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_DLC.hdf5"
    )
    # TS = np.load(path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_TS.npy")
    # proc_dict = pd.DataFrame(np.load(path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_PROC", allow_pickle =True))
    print(camera_name + "_" + mouse_name + "_" + date + "_" + attempt)

    return dlc_dict


def load_dlc(mouse_name, date, attempt, path, db_mode=True):

    if db_mode:
        from vr4mice.schema import vr4mice, dlc

        # NOTE: a little bit dirty way since we are searching via kpts filepath and not PK
        # TODO: pass by PK
        key = f"keypoints_filepath='{path}'"
        data = (vr4mice.DLC() & key).fetch1()
        pk_def = vr4mice.DLC().primary_key
        pk = (vr4mice.DLC() & key).fetch(*pk_def, as_dict=True)[0]
        dlc_dict = dlc.DLCKptsDf().get_data(pk)
    else:
        dlc_dict = _load_dlc_proc_file(
            mouse_name=mouse_name, date=date, attempt=attempt, path=path
        )
    return dlc_dict


def load_dlc_key(key):
    from vr4mice.schema import dlc

    return dlc.DLCKptsDf().get_data(key)


def _sync_dlc_w_game(game_data, dlc):
    pose_time = np.array(dlc["pose_time"] - game_data["start_time"][0])
    step_time = np.array(game_data["step_time"])
    dlc[("index", "pose_time")] = pose_time
    closest_indices = find_closest_indices(pose_time, step_time)
    # print(closest_indices)
    # print(len(closest_indices) == len(step_time))
    dlc = dlc.iloc[closest_indices].reset_index(drop=True)
    dlc[("index", "step")] = game_data["step"]
    dlc[("index", "step_time")] = game_data["step_time"]
    return dlc


def sync_dlc_w_game(dlc_dict, game_data):

    """Add the filtered head angle and head direction and compute derivatives."""

    filt_dlc = filter_dlc(dlc_dict.copy())
    dlc_s = _sync_dlc_w_game(game_data, filt_dlc.copy())
    dlc_var = compute_dlc_variables(dlc_s.iloc[:, :-3].copy())

    df_out = pd.concat([game_data, dlc_var], axis=1)

    df_out["head_angle_velocity"] = compute_circular_angular_velocity(
        df_out.head_angle, time_intervals=df_out.time_elapsed
    )  # df_out.head_angle.diff()
    df_out["heading_dir_velocity"] = compute_circular_angular_velocity(
        df_out.heading_dir, time_intervals=df_out.time_elapsed
    )  # df_out.heading_dir.diff()

    df_out["head_angle_acceleration"] = np.gradient(
        df_out.head_angle_velocity, df_out.time_elapsed
    )  # df_out.head_angle.diff()
    df_out["heading_dir_acceleration"] = np.gradient(
        df_out.heading_dir_velocity, df_out.time_elapsed
    )  # df_out.heading_dir.diff()

    return df_out

  
def sync_keypoint_table(d, keypoint_cuttoff=0.6, filter_window_length=10):
    """ Returns filtered keypoints from the DLCKptsDF table synchronized with game data.
    
        This function loads the DLCKptsDF keypoint table for  dataset d it then removes low confidence frames and sets them to nan. it then
        linearly interpolates between them and then filters with a Savgol filter.
        
        Args:
            d (str):  the data set key formatted as "mouseName_date_attempt".
            keypoint_cuttoff (float): All keypoints below this confidence threshold will be removed and interpolated.
            filter_window_length (int): The window in frames for the filter window size.
            
        Returns:
            pd.Dataframe: filtered and synchronized keypoints with game indexes - step and step_time
    
    """
    # get time indexs from the game dataframe and the start time for session
    from vr4mice.schema import base_analysis, dlc, vr4mice

    game_step_times = pd.DataFrame(
        (base_analysis.DataFrame() & d).fetch(
            "step_time", "step", "time_elapsed", "trial", as_dict=True
        )[0]
    )
    start_time = (vr4mice.State() & d).fetch("start_time")[0]
    game_step_times["start_time"] = start_time

    # Fetch the keypoint table and then sychronise with the game timesteps
    keypoint_df = (dlc.DLCKptsDf() & d).get_all_data()[0]
    filt_dlc_df = filter_dlc(
        keypoint_df, cutoff=keypoint_cuttoff, window_length=filter_window_length
    )
    return _sync_dlc_w_game(game_data=game_step_times, dlc=filt_dlc_df)


def dlc_interpolate(trace, likelyhood, cutoff=0.6):
    trace = np.array(trace)
    low_conf = np.where(np.array(likelyhood) < cutoff)
    trace[low_conf] = np.nan
    traj_nan_below_cutoff = trace
    df = pd.Series(traj_nan_below_cutoff)
    df = df.interpolate().ffill().bfill()
    traj = np.array(df)
    return traj


def dlc_savgol_filter(traj, WL_jitter=9, polyorder=3):
    filt = np.nan_to_num(
        savgol_filter(traj, window_length=WL_jitter, polyorder=polyorder)
    )
    return filt


def filter_dlc(dlc_dict, cutoff=0.4, window_length=9, polyorder=3):
    """
    Filter keypoints data based on likelihood, interpolate missing values, and apply a Savitzky-Golay filter.

    Args:
    - dlc_dict (pd.DataFrame): Dataframe containing the keypoints data.
    - cutoff (float): Likelihood threshold below which values are considered missing and set to NaN.
    - window_length (int): Length of the filter window (i.e., the number of coefficients). Must be an odd number.
    - polyorder (int): Order of the polynomial used to fit the samples. Must be less than window_length.

    Returns:
    - pd.DataFrame: The filtered DataFrame.
    """

    body_parts = dlc_dict.columns.get_level_values(0).unique()[:-2]
    for b in body_parts:
        # Copy the relevant columns to avoid chained assignment
        key_point_x = dlc_dict[b, "x"].copy()
        key_point_y = dlc_dict[b, "y"].copy()
        likelihood = dlc_dict[b, "likelihood"]

        # Mask low likelihood points as NaN
        trace_x = dlc_interpolate(key_point_x, likelyhood=likelihood, cutoff=cutoff)
        trace_y = dlc_interpolate(key_point_y, likelyhood=likelihood, cutoff=cutoff)

        # Interpolate missing values

        # Apply Savitzky-Golay filter
        # if len(key_point_x.dropna()) > window_length:  # Ensure there are enough points for filtering
        trace_x = dlc_savgol_filter(trace_x, window_length, polyorder)
        trace_y = dlc_savgol_filter(trace_y, window_length, polyorder)

        # Update original DataFrame using loc
        dlc_dict.loc[:, (b, "x")] = trace_x
        dlc_dict.loc[:, (b, "y")] = trace_y

    return dlc_dict


def compute_dlc_heading_angles(filt_dlc_row):
    pose = np.array(filt_dlc_row.unstack(level="coords"))
    xy = pose[:, :2]
    conf = pose[:, 2]
    head_xy = xy[[0, 1, 2, 3, 4, 5, 6, 26], :]
    head_conf = conf[[0, 1, 2, 3, 4, 5, 6, 26]]
    center = np.average(head_xy, axis=0, weights=head_conf)
    body_axis = xy[7] - xy[13]  # tail_base -> neck

    body_axis /= sqrt(np.sum(body_axis ** 2))
    head_axis = xy[0] - xy[7]  # neck -> nose
    head_length = xy[0] - xy[7]
    head_axis /= sqrt(np.sum(head_axis ** 2))

    cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
    sign = copysign(1, cross)  # Positive when looking left
    try:
        head_angle = acos(body_axis @ head_axis) * sign
    except ValueError:
        head_angle = 0
    heading = atan2(body_axis[1], body_axis[0])
    heading = degrees(heading)
    head_angle = degrees(head_angle)
    # vals = *center, heading % (360), head_angle
    return (center[0], center[1], heading, head_angle, body_axis, head_axis)


def getall_dlc_heading_angles(filt_dlc):
    heading = []
    head_angles = []
    body_axis_list = []
    head_axis_list = []
    center_x = []
    center_y = []

    for i in range(filt_dlc.shape[0]):
        (
            x,
            y,
            heading_angle,
            head_angle,
            body_axis,
            head_axis,
        ) = compute_dlc_heading_angles(filt_dlc.iloc[i][:-2])
        heading.append(heading_angle)
        head_angles.append(head_angle)
        body_axis_list.append(body_axis)
        head_axis_list.append(head_axis)
        center_x.append(x)
        center_y.append(y)

    df = pd.DataFrame(
        {
            "head_center_x": center_x,
            "head_center_y": center_y,
            "heading_dir": heading,
            "head_angle": head_angles,
        }
    )
    return df


def get_dlc_steps_in_VR_game(step_time, dlc_times):
    """
    Computes for each dlc_time the closest element index in step time.
    :param step_time: step times in the game, should be sorted in ascending order
    :param dlc_times: DLC timestamps, should be sorted in ascending order
    :return: numpy array containing the index of the closest step for each dlc timestamp.
    """
    dlc_steps = np.zeros(len(dlc_times), dtype=int)
    step_time_index = 0
    for i in range(dlc_steps.size):
        current_distance = np.abs(step_time[step_time_index] - dlc_times[i])
        found_step = False
        while not found_step:
            if step_time_index == len(step_time) - 1:
                dlc_steps[i] = step_time_index
                found_step = True
            else:
                next_distance = np.abs(step_time[step_time_index + 1] - dlc_times[i])
                if next_distance >= current_distance:
                    dlc_steps[i] = step_time_index
                    found_step = True
                else:
                    current_distance = next_distance
                    step_time_index += 1

    return dlc_steps


def compute_dlc_variables(dlc_sync):
    df = getall_dlc_heading_angles(dlc_sync)
    return df


def get_dlc_steps_in_VR_game(step_time, dlc_times):
    """
    Computes for each dlc_time the closest element index in step time.
    :param step_time: step times in the game, should be sorted in ascending order
    :param dlc_times: DLC timestamps, should be sorted in ascending order
    :return: numpy array containing the index of the closest step for each dlc timestamp.
    """
    dlc_steps = np.zeros(len(dlc_times), dtype=int)
    step_time_index = 0
    for i in range(dlc_steps.size):
        current_distance = np.abs(step_time[step_time_index] - dlc_times[i])
        found_step = False
        while not found_step:
            if step_time_index == len(step_time) - 1:
                dlc_steps[i] = step_time_index
                found_step = True
            else:
                next_distance = np.abs(step_time[step_time_index + 1] - dlc_times[i])
                if next_distance >= current_distance:
                    dlc_steps[i] = step_time_index
                    found_step = True
                else:
                    current_distance = next_distance
                    step_time_index += 1

    return dlc_steps


def find_closest_indices(pose_time, step_time):
    """
    Finds the index of the closest point in `pose_time` for each entry in `step_time`.

    Parameters:
    - pose_time: Sorted list of timestamps.
    - step_time: List of timestamps to find closest points for.

    Returns:
    A list of indices in `pose_time` for each entry in `step_time`.
    """
    closest_indices = []
    for step in step_time:
        # Find the insertion point
        idx = bisect.bisect_left(pose_time, step)
        # Check if we need to compare with the previous element (to handle edge cases)
        if idx == 0:
            closest_indices.append(idx)
        elif idx == len(pose_time):
            closest_indices.append(idx - 1)
        else:
            before = pose_time[idx - 1]
            after = pose_time[idx]
            closest_indices.append(idx if step - before > after - step else idx - 1)
    return closest_indices


def df2dj(df) -> dict:
    # data: pandas.core.frame.DataFrame
    dj_col = dict()
    dj_col["data"] = df.to_numpy()
    headers = df.columns
    dj_col["headers"] = list(headers)

    if df.columns.nlevels > 2:
        dj_col["scorer"] = headers.get_level_values("scorer").unique()[0]

    return dj_col


def h52dj(h5path: str) -> dict:
    df = pd.read_hdf(h5path)
    return df2dj(df)


def dj2h5(data, headers, scorer) -> pd.DataFrame:

    data = pd.DataFrame(data=data, columns=headers)
    if scorer:
        levels = ["scorer", "bodyparts", "coords"]
    else:
        levels = ["bodyparts", "coords"]
    return pd.DataFrame(data, columns=pd.MultiIndex.from_tuples(headers, names=levels),)


def compute_circular_angular_velocity(angles, time_intervals):
    """
    Computes the circular angular velocity of an angle changing over time.

    Parameters:
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
