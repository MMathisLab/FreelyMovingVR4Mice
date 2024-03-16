import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.signal import savgol_filter, hilbert, find_peaks
from math import sqrt, acos, atan2, copysign, pi, degrees
from IPython.display import display, clear_output
import bisect


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

def load_dlc_proc(camera_name ="Imagingsource", mouse_name ="30559", date = "2024-02-14", attempt="1", path="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/"):
    dlc_dict = pd.read_hdf(path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_DLC.hdf5")
    #TS = np.load(path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_TS.npy")
    #proc_dict = pd.DataFrame(np.load(path + camera_name + "_" + mouse_name + "_" + date + "_" + attempt + "_PROC", allow_pickle =True))
    print(camera_name + "_" + mouse_name + "_" + date + "_" + attempt)

    return(dlc_dict)

def sync_dlc_w_game(game_data, dlc):
    pose_time = np.array(dlc ["pose_time"] - game_data ["start_time"][0]) 
    step_time = np.array(game_data ["step_time"]) 
    dlc [("index", "pose_time")] = pose_time
    closest_indices = find_closest_indices(pose_time, step_time)
    #print(closest_indices)
    #print(len(closest_indices) == len(step_time))
    dlc = dlc.iloc [closest_indices].reset_index(drop=True)
    dlc [("index", "step")] =  game_data ["step"]
    dlc [("index", "step_time")] =  game_data ["step_time"]
    return(dlc)


def dlc_interpolate(trace, likelyhood, cutoff=0.6):
    trace = np.array(trace)
    low_conf = np.where(np.array(likelyhood) < cutoff)
    trace [low_conf] = np.nan
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
        key_point_x = dlc_dict[b, 'x'].copy()
        key_point_y = dlc_dict[b, 'y'].copy()
        likelihood = dlc_dict[b, 'likelihood']
        
        # Mask low likelihood points as NaN
        trace_x = dlc_interpolate(key_point_x, likelyhood=likelihood, cutoff=cutoff)
        trace_y = dlc_interpolate(key_point_y, likelyhood=likelihood, cutoff=cutoff)
        
        # Interpolate missing values
       
        
        # Apply Savitzky-Golay filter
        #if len(key_point_x.dropna()) > window_length:  # Ensure there are enough points for filtering
        trace_x = dlc_savgol_filter(trace_x, window_length, polyorder)
        trace_y = dlc_savgol_filter(trace_y, window_length, polyorder)
            
        # Update original DataFrame using loc
        dlc_dict.loc[:, (b, 'x')] = trace_x
        dlc_dict.loc[:, (b, 'y')] = trace_y

    return dlc_dict


def compute_dlc_heading_angles(filt_dlc_row):
    pose =np.array(filt_dlc_row.unstack(level='coords'))
    xy = pose[:, :2]
    conf = pose[:, 2]
    head_xy = xy [[0, 1, 2, 3, 4, 5, 6, 26],:]
    head_conf = conf [[0, 1, 2, 3, 4, 5, 6, 26]]
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
    return(center [0], center [1], heading, head_angle, body_axis, head_axis)


def getall_dlc_heading_angles(filt_dlc):
    heading =  []
    head_angles = []
    body_axis_list =[]
    head_axis_list =[]
    center_x = []
    center_y = []

    for i in range(filt_dlc.shape [0]):
        x,y,heading_angle, head_angle, body_axis, head_axis = compute_dlc_heading_angles(filt_dlc.iloc [i][:-2])
        heading.append(heading_angle)
        head_angles.append(head_angle)
        body_axis_list.append(body_axis)
        head_axis_list.append(head_axis)
        center_x.append(x)
        center_y.append(y)

    df = pd.DataFrame({"head_center_x": center_x, "head_center_y": center_y,
                      "heading_dir": heading, "head_angle": head_angles})
    return(df)


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
    return(df)
    
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
        
    