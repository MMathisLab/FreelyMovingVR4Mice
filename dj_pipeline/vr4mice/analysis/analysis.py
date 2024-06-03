import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from typing import List, Tuple
from vr4mice.schema import vr4mice


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


def _resample_data_frame(df, resampling_period=0.02) -> pd.DataFrame:
    categorical_columns = ["aperture"]
    binary_columns = ["reward", "mouse_in_R", "mouse_in_L", "iti"]
    continuous_columns = df.columns[
        (~df.columns.isin(categorical_columns)) & (~df.columns.isin(binary_columns))
    ]

    df["time"] = pd.to_datetime(df["step_time"], unit="s")
    categorical_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[categorical_columns]
        .resample(f"{resampling_period}s")  # resample to 50Hz
        .first()
        .ffill()
    )

    binary_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[binary_columns]
        .resample("0.02s")
        .max()
        .ffill()
    )

    continuous_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[continuous_columns]
        .resample("0.02s")
        .mean()
        .interpolate()
    )
    df = pd.concat(
        [continuous_resampled, categorical_resampled, binary_resampled], axis=1
    ).reset_index()

    reference_datetime = df["time"].iloc[0]
    df["time_elapsed"] = (df["time"] - reference_datetime).dt.total_seconds()

    return df


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
    dataset = (vr4mice.VR4Mice() & key).fetch()[0][0]
    mouse_state = (vr4mice.MouseState() & {"dataset": dataset}).fetch(as_dict=True)[0]
    state = (vr4mice.State() & {"dataset": dataset}).fetch(as_dict=True)[0]

    df = pd.DataFrame(
        {
            "step": state["step"],
            "step_time": state["step_time"],
            "trial": state["episode"],
            "reward": state["reward"],
            "x": mouse_state["x_pos"],
            "y": mouse_state["z_pos"],
            "aperture": mouse_state["slit_size"][mouse_state["episode"] - 1],
            "head_dir": mouse_state["head_dir"],
            "mouse_can_report": mouse_state["mouse_can_report"],
            "iti": mouse_state["iti"],
            "object_on_left": mouse_state["obj_left"],
            "mouse_correct": mouse_state["mouse_report_correct"],
            "mouse_in_L": mouse_state["report_left"],
            "mouse_in_R": mouse_state["report_right"],
            "start_time": mouse_state["start_time"],
        }
    )

    df = df[
        df.trial != 1
    ]  # NOTE(celia): drop first trial which is DLC-live initialization trial

    df["x"] = np.interp(df.x, [-9, 9], [-27, 27])
    df["y"] = np.interp(df.y, [-10, -2], [-27, 27])

    # Normalized coordinates
    df["bins_y"] = pd.cut(
        df["y"], bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2])
    )
    df["norm_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda x: x - np.mean(x.iloc[:first_n_samples])
    )

    # Define the arena, start and reward areas dimensions
    box_df = _get_box_df(dataset)

    # Mean reward position in the reward boxes
    box_df["left_reward_x"] = df[(df.reward > 0.5) & (df.trial_L_choice > 0.5)][
        "x"
    ].mean()
    box_df["left_reward_z"] = df[(df.reward > 0.5) & (df.trial_L_choice > 0.5)][
        "y"
    ].mean()
    box_df["right_reward_x"] = df[(df.reward > 0.5) & (df.trial_R_choice > 0.5)][
        "x"
    ].mean()
    box_df["right_reward_z"] = df[(df.reward > 0.5) & (df.trial_R_choice > 0.5)][
        "y"
    ].mean()

    box_df = box_df.iloc[1]

    df["trial_rewarded"] = df.groupby("trial", as_index=False)["reward"].transform(
        lambda x: x.max()
    )
    # df[["trial_step", "trial_step_time"]] = df.groupby(
    #    "trial", as_index=True, group_keys=False
    # )[["step", "step_time"]].apply(lambda x: x.iloc[:] - x.iloc[0])

    if no_iti:
        df = df[df.iti == 0.0]
        # df["trial_step_fraction"] = df.groupby(
        #    "trial", as_index=True, group_keys=False
        # )["trial_step"].apply(lambda x: x.iloc[:] / x.iloc[-1])
    # else:
    # df["trial_step_fraction"] = df.groupby(
    #    "trial", as_index=True, group_keys=False
    # )["trial_step"].apply(lambda x: x.iloc[:] / x.iloc[-1])

    df["trial_R_choice"] = df.groupby("trial", as_index=False)["mouse_in_R"].transform(
        lambda x: x.iloc[-1]
    )
    df["trial_L_choice"] = df.groupby("trial", as_index=False)["mouse_in_L"].transform(
        lambda x: x.iloc[-1]
    )

    df = _resample_data_frame(df)

    # Velocity and acceleration computed from time_elapsed difference (fixed interval)
    df["velocity"] = np.sqrt(
        (np.gradient(df.x, df.time_elapsed) ** 2)
        + (np.gradient(df.y, df.time_elapsed) ** 2)
    )

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
    ].transform("sum")

    # Trial start and end position
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
    df["choice"] = df.trial_L_choice.replace([0, 1], ["right", "left"])

    # Distance to reward
    df["flip_one_side"] = df["trial_L_choice"].replace([0, 1], [1, -1])
    df["distance_to_reward"] = np.sqrt(
        (box_df["right_box_x_center"] - (df["x"] * df["flip_one_side"])) ** 2
        + (box_df["right_box_z_center"] - df["y"]) ** 2
    )

    # TODO(celia): how does the naming work with DJ?
    # df["mouse_name"] = mouse_name
    # df["attempt"] = attempt
    # df["date"] = date
    # df["session"] = (
    #     df["mouse_name"].astype(str)
    #     + "_"
    #     + df["date"].astype(str)
    #     + "_"
    #     + df["attempt"].astype(str)
    # )

    df.trial = df.trial.astype(int)
    df.aperture = df.aperture.round(2)

    return (df, box_df)


def _get_box_df(dataset) -> pd.DataFrame:
    """Define the box dimensions.

    Define the arena, start area and reward areas dimensions.

    Returns:
        A dataFrame containing the dimensions.
    """

    box_df = pd.DataFrame((vr4mice.Box() & {"dataset": dataset}).fetch(as_dict=True)[0])
    # Unity game dimension to real sm metadata
    a = 9
    b = -10
    c = -2
    d = 27

    # Same indexes among blocks
    box_df.left_box_x_min = np.interp(box_df.left_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.left_box_x_max = np.interp(box_df.left_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.left_box_z_min = np.interp(box_df.left_box_z_min, [b, c], [-1 * d, d])
    box_df.left_box_z_max = np.interp(box_df.left_box_z_max, [b, c], [-1 * d, d])

    box_df.right_box_x_min = np.interp(box_df.right_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.right_box_x_max = np.interp(box_df.right_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.right_box_z_min = np.interp(box_df.right_box_z_min, [b, c], [-1 * d, d])
    box_df.right_box_z_max = np.interp(box_df.right_box_z_max, [b, c], [-1 * d, d])

    box_df.tt_box_x_min = np.interp(box_df.tt_box_x_min, [-1 * a, a], [-1 * d, d])
    box_df.tt_box_x_max = np.interp(box_df.tt_box_x_max, [-1 * a, a], [-1 * d, d])
    box_df.tt_box_z_min = np.interp(box_df.tt_box_z_min, [b, c], [-1 * d, d])
    box_df.tt_box_z_max = np.interp(box_df.tt_box_z_max, [b, c], [-1 * d, d])

    return box_df
