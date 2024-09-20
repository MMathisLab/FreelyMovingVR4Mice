import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.interpolate import CubicSpline
from vr4mice.schema import base_analysis, vr4mice

# from scipy.signal import savgol_filter, hilbert, find_peaks
from vr4mice.utils.logger import Logger

from typing import List, Tuple

logger = Logger.get_logger()


# Filter out the UserWarning related to the deprecated features
warnings.filterwarnings("ignore", category=UserWarning)


def style():
    """
    Set the style of the plots.

    This function sets the font color, size and weight, and axis label properties
    for a matplotlib plot using the Google style guidelines.
    """
    font_color = "black"
    font_size = 18
    plt.rcParams.update(
        {
            "text.color": font_color,
            "axes.labelcolor": font_color,
            "axes.labelsize": font_size,
            "axes.titleweight": "bold",
            "axes.titlesize": font_size,
            "xtick.labelcolor": font_color,
            "xtick.labelsize": font_size,
            "ytick.labelcolor": font_color,
            "ytick.labelsize": font_size,
            "font.weight": "bold",
        }
    )

    plt.rc("axes.spines", top=False, bottom=True, left=True, right=False)
    plt.rc("axes", edgecolor=font_color)


def _resample_data_frame(df, resampling_period_ms=20) -> pd.DataFrame:  # in ms
    categorical_columns = ["aperture"]
    binary_columns = ["reward", "mouse_in_right", "mouse_in_left", "iti"]
    continuous_columns = df.columns[
        (~df.columns.isin(categorical_columns)) & (~df.columns.isin(binary_columns))
    ]

    t = f"{resampling_period_ms}ms"  # old: 0.02s, err: ValueError: invalid literal for int() with base 10: '0.02'

    df["time"] = pd.to_datetime(df["step_time"], unit="s")
    categorical_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[categorical_columns]
        .resample(t)  # resample to 50Hz
        .first()
        .ffill()
    )

    binary_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[binary_columns]
        .resample(t)
        .max()
        .ffill()
    )

    continuous_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[continuous_columns]
        .resample(t)
        .mean()
        .interpolate()
    )
    df = pd.concat(
        [continuous_resampled, categorical_resampled, binary_resampled], axis=1
    ).reset_index()

    reference_datetime = df["time"].iloc[0]
    df["time_elapsed"] = (df["time"] - reference_datetime).dt.total_seconds()

    return df


def get_rewarded(df):

    rewarded = df.groupby("trial", as_index=False)["reward"].transform(
        lambda x: x.max()
    )
    return rewarded


# def get_choices(df):
#    choices = df.groupby(["trial"], as_index=False).last()
#    return choices


def get_dist2reward(df, box_df):
    dist2reward = np.sqrt(
        (box_df["right_box_x_center"] - (df["x"] * df["flip_one_side"])) ** 2
        + (box_df["right_box_z_center"] - df["y"]) ** 2
    )
    return dist2reward


def create_data_frame(
    key: dict,
    no_iti: bool = True,
    first_n_samples: int = 3,
    spatial_ybins: List[int] = [-27, 27, 75],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create main dataframe for analysis.

    Load and preprocess behavioral data and box coordinates.

    Args:
        key (dict): Dictionary containing keys for VR4Mice database. (VR4Mice)
        no_iti (bool): If True, it removes rows where iti=0.0 from dataframe (default=True).
        first_n_sample (int): The first n samples to average to normalize trajectories, not that sampling rate is 0.2
            3 first samples (default value) corresponds to 0.6sec.
        spacial_ybins (List[int]): range to bin the y coordinates for
            normalization.

    Returns:
        df (pandas.DataFrame): Dataframe for analysis that contains also Box data for each trial.
    """
    # Note:
    # all keys corresponds to the datajoint tables initial keys, except: "episode" --> "trial"
    # in output: z transforms in y, x in x

    logger.info(f"Creating dataframe for: {key}")

    # Note:
    # all attributes are used for MouseState, the implementation could be:
    # df = pd.DataFrame((vr4mice.MouseState & {"dataset": dataset}).fetch1())
    # but with fetch1 it looks faster and more control on keys
    # TODO:(mary) checks if exists, try-catch

    slit_size = np.array(
        (vr4mice.Metadata & key).fetch1("slit_size")
    )  # TODO: check type-s
    trial = (vr4mice.State & key).fetch("episode")  # attention change of name
    trial = np.array(np.array(trial)[0], dtype=np.int32)

    aperture = slit_size[trial - 1]  # TODO check type-s
    df = pd.DataFrame(
        {
            "step": (vr4mice.State & key).fetch1(
                "step"
            ),  # can be fetched from State any time: exclude from df to save
            "step_time": (vr4mice.State & key).fetch1(
                "step_time"
            ),  # used for time calcul, but hasn't be saved
            "trial": trial,
            "reward": (vr4mice.State & key).fetch1("reward"),  # no need to save
            "x": (vr4mice.MouseState & key).fetch1("x_pos"),
            "y": (vr4mice.MouseState & key).fetch1("z_pos"),
            "aperture": aperture,  # attention! new attribute!
            "head_dir": (vr4mice.MouseState & key).fetch1(
                "head_dir"
            ),  # no need to save: can be fetched if needed
            "mouse_can_report": (vr4mice.MouseState & key).fetch1(
                "mouse_can_report"
            ),  # same: don't dave
            "iti": (vr4mice.MouseState & key).fetch1("iti"),
            "mouse_correct": (vr4mice.MouseState & key).fetch1(
                "mouse_report_correct"
            ),  # same
            "object_on_left": (vr4mice.MouseState & key).fetch1("obj_left"),
            "mouse_in_left": (vr4mice.MouseState & key).fetch1("report_left"),
            "mouse_in_right": (vr4mice.MouseState & key).fetch1("report_right"),
            # "start_time": (vr4mice.State & key).fetch1("start_time"), #we don't modify it, can be fetched from State any time
        }
    )

    logger.info(f"All dataframe fetched for: {key}")

    df = df[
        df.trial != 1
    ]  # NOTE(celia): drop first trial which is DLC-live initialization trial

    interp = dict(
        a=9,
        b=-10,
        c=-2,
        d=27,
    )
    # TODO:
    # unity_arena_size_x_min
    # x_max
    # z_min
    # z_max

    df["x"] = np.interp(
        df.x, [-1 * interp["a"], interp["a"]], [-1 * interp["d"], interp["d"]]
    )
    df["y"] = np.interp(
        df.y, [interp["b"], interp["c"]], [-1 * interp["d"], interp["d"]]
    )

    # Normalized coordinates
    df["bins_y"] = pd.cut(
        df["y"], bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2])
    )
    df["norm_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda x: x - np.mean(x.iloc[:first_n_samples])
    )

    # TODO: to think: keep as method: don't save or save separately
    # df["rewarded"] = get_rewarded(df)

    if no_iti:
        df = df[df.iti == 0.0]

    df["trial_right_choice"] = df.groupby("trial", as_index=False)[
        "mouse_in_right"
    ].transform(lambda x: x.iloc[-1])
    df["trial_left_choice"] = df.groupby("trial", as_index=False)[
        "mouse_in_left"
    ].transform(lambda x: x.iloc[-1])

    df = _resample_data_frame(df)

    # Velocity and acceleration computed from time_elapsed difference (fixed interval)
    df["velocity"] = np.sqrt(
        (np.gradient(df.x, df.time_elapsed) ** 2)
        + (np.gradient(df.y, df.time_elapsed) ** 2)
    )

    # TODO: check all new parameters in df

    df["velocity_x"] = np.gradient(df.x, df.time_elapsed)
    df["acceleration_x"] = np.gradient(df["velocity_x"], df.time_elapsed)

    df["velocity_y"] = np.gradient(df.y, df.time_elapsed)
    df["acceleration_y"] = np.gradient(df["velocity_y"], df.time_elapsed)

    df["trial_duration"] = df.groupby("trial", as_index=False)[
        "time_elapsed"
    ].transform(lambda x: x.iloc[-1] - x.iloc[0])

    # Distance between sample points and length of the trajectory
    df["distance"] = np.sqrt(df.x.diff() ** 2 + df.y.diff() ** 2)
    df["trial_traj_path_length"] = df.groupby("trial", as_index=False)[
        "distance"
    ].transform(
        "sum"
    )  # TODO: to think: it can be a method too

    # Trial start and end position
    # TODO: actually also can be the methods...
    df["trial_init_x"] = df.groupby("trial", as_index=False)["x"].transform(
        lambda x: x.iloc[0]
    )
    df["trial_init_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda y: y.iloc[0]
    )
    df["trial_end_x"] = df.groupby("trial", as_index=False)["x"].transform(
        lambda x: x.iloc[-1]
    )
    df["trial_end_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda y: y.iloc[-1]
    )

    # Direct path from start to end position
    df["trial_direct_path"] = np.sqrt(
        (
            ((df.trial_init_x - df.trial_end_x) ** 2)
            + (df.trial_init_y - df.trial_end_y) ** 2
        )
    )

    # Trial tortuosity (arc-chord ratio)
    df["trial_tortuosity"] = df.trial_traj_path_length / df.trial_direct_path

    df["trial_step"] = df.groupby("trial").cumcount()

    # Choices as string values
    df["choice"] = df.trial_left_choice.replace([0, 1], ["right", "left"])

    # Distance to reward
    df["flip_one_side"] = df["trial_left_choice"].replace([0, 1], [1, -1])

    # df["distance_to_reward"] --> to method

    df.trial = df.trial.astype(int)
    df.aperture = df.aperture.round(2)

    return df, interp


def get_box_df(key, df, interp):

    """Define the box dimensions.

    Define the arena, start area and reward areas dimensions.

    Returns:
        A dataFrame containing the dimensions.
    """
    box_df = pd.DataFrame((vr4mice.Box & key).fetch())

    for col in box_df.columns:
        for index, value in box_df[col].items():
            if isinstance(value, list):
                box_df.loc[index, col] = value[0]
    print(interp)
    a = interp["a"]
    b = interp["b"]
    c = interp["c"]
    d = interp["d"]

    # same indexes among blocks
    box_df.l_box_x_min = np.interp(box_df.l_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.l_box_x_max = np.interp(box_df.l_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.l_box_z_min = np.interp(box_df.l_box_z_min, [b, c], [-1 * d, d])
    box_df.l_box_z_max = np.interp(box_df.l_box_z_max, [b, c], [-1 * d, d])

    box_df.r_box_x_min = np.interp(box_df.r_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.r_box_x_max = np.interp(box_df.r_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.r_box_z_min = np.interp(box_df.r_box_z_min, [b, c], [-1 * d, d])
    box_df.r_box_z_max = np.interp(box_df.r_box_z_max, [b, c], [-1 * d, d])

    box_df.tt_box_x_min = np.interp(box_df.tt_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.tt_box_x_max = np.interp(box_df.tt_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.tt_box_z_min = np.interp(box_df.tt_box_z_min, [b, c], [-1 * d, d])
    box_df.tt_box_z_max = np.interp(box_df.tt_box_z_max, [b, c], [-1 * d, d])

    # Mean reward position in the reward boxes
    # Note: attention new attributes (version 2)
    box_df["l_reward_x"] = df[(df.reward > 0.5) & (df.trial_left_choice > 0.5)][
        "x"
    ].mean()
    box_df["l_reward_z"] = df[(df.reward > 0.5) & (df.trial_left_choice > 0.5)][
        "y"
    ].mean()
    box_df["r_reward_x"] = df[(df.reward > 0.5) & (df.trial_right_choice > 0.5)][
        "x"
    ].mean()
    box_df["r_reward_z"] = df[(df.reward > 0.5) & (df.trial_right_choice > 0.5)][
        "y"
    ].mean()

    # box_df = box_df.iloc[1]

    return box_df


def get_jshaped_trials(
    df: pd.DataFrame, threshold_duration: int = 5, threshold_tortuosity: int = 5
):
    """
    Separates the trials in the DataFrame into 'J-shaped' and 'wandering' based on the given thresholds.

    Args:
        df (pd.DataFrame): The DataFrame containing trial data with columns 'trial_duration' and 'trial_tortuosity'.
        threshold_duration (int): The maximum duration for a trial to be considered 'J-shaped'. Default is 5.
        threshold_tortuosity (int): The maximum tortuosity for a trial to be considered 'J-shaped'. Default is 5.

    Returns:
        tuple: A tuple containing two DataFrames:
            - j_shaped (pd.DataFrame): DataFrame containing trials that are classified as 'J-shaped'.
            - wandering (pd.DataFrame): DataFrame containing trials that are classified as 'wandering'.
    """
    j_shaped = df[
        (df.trial_duration <= threshold_duration)
        & (df.trial_tortuosity <= threshold_tortuosity)
    ]
    # NOTE: add reward param?
    # wandering = df[~df.index.isin(j_shaped.index)]
    return j_shaped  # , wandering


def get_all_datasets(mouse_list=None, load_dlc=True):
    """Fetch all mice and make a big dataframe out of them."""
    # mouse list can be list of keys: [{key1}, {key2}]

    big_df = []

    dfs = []

    # TODO: make the getter for df_box in a propper way

    if load_dlc:
        if mouse_list:
            for key in mouse_list:
                df = dlc.SyncDLCWGame().get_data(key)
                dfs.append(df)
        else:
            dfs = dlc.SyncDLCWGame().get_all_data()

        return dfs

    # load_dlc False case
    if mouse_list:
        for key in mouse_list:
            df = dlc.DataFrame().get_data(key)
            dfs.append(df)
    else:
        dfs = dlc.SyncDLCWGame().get_all_data()
        # = (base_analysis.DataFrame().get_data()

        # & keys).fetch(as_dict=True)[0] # or keep .npy?
        # else:
        #    df, box_df = (base_analysis.DataFrame()).fetch(as_dict=True)[0] # or keep .npy?

        if load_dlc == True:
            dlc_dict = load_dlc(
                path=path,
                mouse_name=m["mouse_name"],
                date=m["date"],
                attempt=m["attempt"],
            )
            df = sync_dlc_w_game(dlc_dict, game_data=df)

        big_df.append(df)
    return pd.concat(big_df).reset_index(), box_df
