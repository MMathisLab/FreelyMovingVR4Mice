from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vr4mice.analysis.dlc_helpers import load_dlc, sync_dlc_w_game


def load_data(
    path: str = "/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/",
    mouse_name: str = "Anchovy",
    date: str = "2023-02-23",
    attempt: str = "2",
    no_iti: bool = True,
    first_n_samples: int = 3,
    spatial_ybins: List[int] = [-27, 27, 75],
):
    """
    Load and preprocess behavioral data and box coordinates.

    This function loads behavioral data from a specified file and performs data preprocessing to create a
    pandas DataFrame containing relevant information. It also extracts box coordinates and dimensions
    into a separate DataFrame.

    Note:
        Currently this function loads from the pickle file - this is tempory and we should use the Datajoint function once everybody is set up

    Parameters:
        path (str): The directory path where the data file is located.
        mouse_name (str): The name of the mouse or subject for which the data is being loaded.
        date (str): The date of the data in the format 'YYYY-MM-DD'.
        attempt (str): The attempt or session number for the data.
        no_iti (bool): A flag indicating whether to exclude inter-trial intervals (ITIs) from the data.
        first_n_sample (int): The first n samples to average to normalize trajectories, not that sampling rate is 0.2
            3 first samples (default value) corresponds to 0.6sec.

    Returns:
        df (pandas DataFrame): A DataFrame containing the preprocessed behavioral data.
        df_box (pandas DataFrame): A DataFrame containing the coordinates and dimensions of left, right, and target boxes.

    """

    state_dict = pd.read_pickle(
        path + mouse_name + "_" + date + "_" + attempt + ".pickle"
    )

    df = pd.DataFrame(
        {
            "step": state_dict["step"],
            "step_time": state_dict["step_time"],
            "trial": state_dict["episode"],
            "reward": state_dict["reward"],
            "x": state_dict["state"][:, 0],
            "y": state_dict["state"][:, 1],
            "aperture": state_dict["slit_size"][state_dict["episode"] - 1],
            "head_dir": state_dict["state"][:, 2],
            "mouse_can_report": state_dict["state"][:, 3],
            "iti": state_dict["state"][:, 4],
            "object_on_left": state_dict["state"][:, 5],
            "mouse_correct": state_dict["state"][:, 6],
            "mouse_in_L": state_dict["state"][:, 7],
            "mouse_in_R": state_dict["state"][:, 8],
            "start_time": state_dict["start_time"],
        }
    )

    df = df[
        df.trial != 1
    ]  # NOTE(celia): drop first trial which is DLC-live initialization trial

    df["x"] = np.interp(df.x, [-9, 9], [-27, 27])
    df["y"] = np.interp(df.y, [-10, -2], [-27, 27])

    # df["bins_y"] = pd.cut(
    #     df["y"], bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2])
    # )
    # df["bins_x"] = pd.cut(
    #     df["x"], bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2])
    # )
    df["norm_x"] = df.groupby("trial", as_index=False)["x"].transform(
        lambda x: x - np.mean(x.iloc[:first_n_samples])
    )
    df["norm_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda x: x - np.mean(x.iloc[:first_n_samples])
    )
    # df = df.drop(columns=["bins_x", "bins_y"])

    df["trial_rewarded"] = df.groupby("trial", as_index=False)["reward"].transform(
        lambda x: x.max()
    )
    # df[["trial_step", "trial_step_time"]] = df.groupby(
    #    "trial", as_index=True, group_keys=False
    # )[["step", "step_time"]].apply(lambda x: x.iloc[:] - x.iloc[0])

    if no_iti == True:
        df = df[df.iti == 0.0]
        # df["trial_step_fraction"] = df.groupby(
        #     "trial", as_index=True, group_keys=False
        # )["trial_step"].apply(lambda x: x.iloc[:] / x.iloc[-1])
    # else:
    #     df["trial_step_fraction"] = df.groupby(
    #         "trial", as_index=True, group_keys=False
    #     )["trial_step"].apply(lambda x: x.iloc[:] / x.iloc[-1])

    df["trial_R_choice"] = df.groupby("trial", as_index=False)["mouse_in_R"].transform(
        lambda x: x.iloc[-1]
    )
    df["trial_L_choice"] = df.groupby("trial", as_index=False)["mouse_in_L"].transform(
        lambda x: x.iloc[-1]
    )

    # resampling to 50Hz
    categorical_columns = ["aperture"]
    binary_columns = ["reward", "mouse_in_R", "mouse_in_L", "iti"]
    continuous_columns = df.columns[
        (~df.columns.isin(categorical_columns)) & (~df.columns.isin(binary_columns))
    ]

    df["time"] = pd.to_datetime(df["step_time"], unit="s")

    t = "20ms"  # old: 0.02s: ValueError: invalid literal for int() with base 10: '0.02'

    categorical_resampled = (
        df.set_index("time")
        .groupby("trial", as_index=False)[categorical_columns]
        .resample(t)
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

    # velocity and acceleration computed from time_elapsed difference (fixed interval)
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

    df["distance"] = np.sqrt(df.x.diff() ** 2 + df.y.diff() ** 2)
    df["trial_traj_path_length"] = df.groupby("trial", as_index=False)[
        "distance"
    ].transform("sum")

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
    df["trial_direct_path"] = np.sqrt(
        (
            ((df.trial_init_x - df.trial_end_x) ** 2)
            + (df.trial_init_y - df.trial_end_y) ** 2
        )
    )
    df["trial_tortuosity"] = df.trial_traj_path_length / df.trial_direct_path
    df["trial_step"] = df.groupby("trial").cumcount()

    df["choice"] = df.trial_L_choice.replace([0, 1], ["right", "left"])
    df["flip_one_side"] = df["trial_L_choice"].replace([0, 1], [1, -1])

    df["mouse_name"] = mouse_name
    df["attempt"] = attempt
    df["date"] = date
    # df["start_time"] = state_dict["start_time"]
    df["session"] = (
        df["mouse_name"].astype(str)
        + "_"
        + df["date"].astype(str)
        + "_"
        + df["attempt"].astype(str)
    )

    # Create the box dataframe
    df_box = pd.DataFrame()
    df_box = _define_box(df_box, state_dict, which="left")
    df_box = _define_box(df_box, state_dict, which="right")
    df_box = _define_box(df_box, state_dict, which="tt")
    df_box["left_reward_x"] = df[(df.reward > 0.5) & (df.trial_L_choice > 0.5)][
        "x"
    ].mean()
    df_box["left_reward_z"] = df[(df.reward > 0.5) & (df.trial_L_choice > 0.5)][
        "y"
    ].mean()
    df_box["right_reward_x"] = df[(df.reward > 0.5) & (df.trial_R_choice > 0.5)][
        "x"
    ].mean()
    df_box["right_reward_z"] = df[(df.reward > 0.5) & (df.trial_R_choice > 0.5)][
        "y"
    ].mean()

    df_box = df_box.iloc[1]

    df["distance_to_reward"] = np.sqrt(
        (df_box["right_box_x_center"] - (df["x"] * df["flip_one_side"])) ** 2
        + (df_box["right_box_z_center"] - df["y"]) ** 2
    )

    df.trial = df.trial.astype(int)
    df.aperture = df.aperture.round(2)

    # TODO(celia): check if replaced/useful?
    # df["rewarded"] = df.groupby(["trial"], as_index=False).max()
    # df["choices"] = df.groupby(["trial"], as_index=False).last()
    # df["box_entries"] = _time_to_rewards(df)

    return (df, df_box)


def _time_to_rewards(df):  # split
    """
    Calculate the time it takes for the animal to enter the box for
    rewarded vs unrewarded trials and Left and right choices.
    called in create_data_frame to initialize box_entries values

    Args:
        df: pandas.DataFrame containing the data
        ax: a list of two matplotlib axes to plot the results

    Returns:
        box_entries
    """

    box_entries = (
        df[(df.mouse_in_R == 1.0) | (df.mouse_in_L == 1.0)]
        .groupby("trial", as_index=False)
        .first()
    )
    box_entries["rewarded"] = df.groupby(["trial"], as_index=False).max()["reward"]

    return box_entries


def _define_box(df_box: pd.DataFrame, state_dict: dict, which: str):

    if which == "left":
        l_which = "L"
    elif which == "right":
        l_which = "R"
    elif which == "tt":
        l_which = "TT"
    else:
        raise NotImplementedError()

    df_box[f"{which}_box_x_min"] = np.interp(
        state_dict[f"{l_which}_box_x_min"], [-9, 9], [-27, 27]
    )
    df_box[f"{which}_box_x_max"] = np.interp(
        state_dict[f"{l_which}_box_x_max"], [-9, 9], [-27, 27]
    )
    df_box[f"{which}_box_z_min"] = np.interp(
        state_dict[f"{l_which}_box_z_min"], [-10, -2], [-27, 27]
    )
    df_box[f"{which}_box_z_max"] = np.interp(
        state_dict[f"{l_which}_box_z_max"], [-10, -2], [-27, 27]
    )
    df_box[f"{which}_box_x_center"] = (
        df_box[f"{which}_box_x_min"] + df_box[f"{which}_box_x_max"]
    ) / 2
    df_box[f"{which}_box_z_center"] = (
        df_box[f"{which}_box_z_min"] + df_box[f"{which}_box_z_max"]
    ) / 2

    return df_box


def get_rc_params():
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


# TODO(mary): add labels... (if hasn't been done)
def get_mouse_list(list_name="tolias_two_widths"):
    # NOTE(tom): This is a temporay function just to keep track of the tolias
    # lab data sets that we have and so that we can easily import into notebooks.

    if list_name == "tolias_two_widths":
        mouse_list = [
            {"mouse_name": "30559", "date": "2024-02-26", "attempt": "1"},  # 0
            {"mouse_name": "30559", "date": "2024-02-20", "attempt": "1"},  # 1
            {"mouse_name": "30559", "date": "2024-02-19", "attempt": "1"},  # 2
            {"mouse_name": "30559", "date": "2024-02-16", "attempt": "1"},  # 3
            {"mouse_name": "30559", "date": "2024-02-15", "attempt": "1"},  # 4
            {"mouse_name": "30559", "date": "2024-02-14", "attempt": "1"},  # 5
            {"mouse_name": "30559", "date": "2024-02-13", "attempt": "1"},  # 6
            {"mouse_name": "30561", "date": "2024-02-16", "attempt": "1"},  # 7
            {"mouse_name": "30561", "date": "2024-02-19", "attempt": "1"},  # 8
            {"mouse_name": "30561", "date": "2024-02-20", "attempt": "1"},  # 9
            {"mouse_name": "30561", "date": "2024-02-21", "attempt": "1"},  # 10
            {"mouse_name": "30561", "date": "2024-02-22", "attempt": "1"},  # 11
            {"mouse_name": "30561", "date": "2024-02-23", "attempt": "1"},  # 12
            {"mouse_name": "31047", "date": "2024-02-26", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-27", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-28", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-29", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-22", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-23", "attempt": "1"},
        ]
    elif list_name == "tolias_five_widths":
        mouse_list = [
            {"mouse_name": "30561", "date": "2024-02-26", "attempt": "1"},
            {"mouse_name": "30561", "date": "2024-02-27", "attempt": "1"},
            {"mouse_name": "30561", "date": "2024-02-28", "attempt": "1"},
            {"mouse_name": "30561", "date": "2024-02-29", "attempt": "1"},
            {"mouse_name": "30561", "date": "2024-02-29", "attempt": "2"},
            {"mouse_name": "31050", "date": "2024-02-26", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-27", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-28", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-29", "attempt": "1"},
        ]
    elif list_name == "tolias_training":
        mouse_list = [
            {"mouse_name": "31050", "date": "2024-02-08", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-09", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-12", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-13", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-14", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-15", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-16", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-19", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-20", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-21", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-22", "attempt": "1"},
            {"mouse_name": "31050", "date": "2024-02-23", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-08", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-09", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-12", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-13", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-14", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-15", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-16", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-19", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-20", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-21", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-22", "attempt": "1"},
            {"mouse_name": "31047", "date": "2024-02-23", "attempt": "1"},
        ]
    else:
        NotImplementedError(f"{list_name}")
    return mouse_list


# TODO: generalize
# Pass by database: do we really need bug df, or can be fetched?
def get_all_tolias_mice(mouse_list, path, load_dlc=True):
    """Grab tolias lab mice and make a big dataframe out of them."""
    big_df = []
    for m in mouse_list:
        df, df_box = load_data(
            path=path, mouse_name=m["mouse_name"], date=m["date"], attempt=m["attempt"]
        )
        if load_dlc == True:
            dlc_dict = load_dlc(
                path=path,
                mouse_name=m["mouse_name"],
                date=m["date"],
                attempt=m["attempt"],
            )
            df = sync_dlc_w_game(dlc_dict, game_data=df)

        big_df.append(df)
    return pd.concat(big_df).reset_index(), df_box
