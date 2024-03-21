import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path
from scipy.interpolate import CubicSpline
from scipy import stats

# from scipy.signal import savgol_filter, hilbert, find_peaks
from vr4mice.utils.logger import Logger
from vr4mice.schema import vr4mice
from vr4mice.schema import base_analysis

logger = Logger.get_logger()

import warnings

# Filter out the UserWarning related to the deprecated features
warnings.filterwarnings("ignore", category=UserWarning)


def style():
    """
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


def _convert_angles(df):
    """
    This function converts angles in degrees to continuous values for plotting using numpy functions.

    Args:
        df (pandas.DataFrame): DataFrame containing a column with angles in degrees named 'head_dir'

    Returns:
        clean_angles (numpy.ndarray): Array of continuous angle values for plotting
    """
    clean_angles = np.rad2deg(np.sin(np.deg2rad(df["head_dir"])))
    return clean_angles


def create_data_frame(key, no_iti=True):
    """
    Create main dataframe for analysis.
    ?
    Args:
        key (dict): Dictionary containing keys for VR4Mice database. (VR4Mice)
        no_iti (bool): If True, it removes rows where iti=0.0 from dataframe (default=True).

    Returns:
        df (pandas.DataFrame): Dataframe for analysis that contains also Box data for each trial.
    """

    # this function creates the main dataframe for analysis => todo think to externalize
    # to do key naming policy or docs
    # all keys corresponds to the datajoint tables initial keys, except:
    # episode renames in trials
    # in output: z transforms in y, x in x

    logger.info("Creating dataframe for: " + str(key))

    # Note: as all attributes are used for MouseState it could be:
    # df = pd.DataFrame((vr4mice.MouseState & {"dataset": dataset}).fetch1())
    # but with fetch1 it looks faster, plus user can check and chose naming policy
    df = pd.DataFrame(
        {
            "step": (vr4mice.State & key).fetch1("step"),
            "step_time": (vr4mice.State & key).fetch1("step_time"),
            "trial": (vr4mice.State & key).fetch1(
                "episode"
            ),  # attention change of name
            "reward": (vr4mice.State & key).fetch1("reward"),
            "x": (vr4mice.MouseState & key).fetch1("x_pos"),
            "y": (vr4mice.MouseState & key).fetch1("z_pos"),
            "head_dir": (vr4mice.MouseState & key).fetch1("head_dir"),
            "mouse_can_report": (vr4mice.MouseState & key).fetch1("mouse_can_report"),
            "iti": (vr4mice.MouseState & key).fetch1("iti"),
            "mouse_correct": (vr4mice.MouseState & key).fetch1("mouse_report_correct"),
            "object_on_left": (vr4mice.MouseState & key).fetch1("obj_left"),
            "mouse_in_left": (vr4mice.MouseState & key).fetch1("report_left"),
            "mouse_in_right": (vr4mice.MouseState & key).fetch1("report_right"),
            # todo(mary) validate attributes with tom
        }
    )

    logger.info("All dataframe fetched for: " + str(key))

    df["velocity"] = np.sqrt(
        (np.gradient(df["x"]) ** 2) + (np.gradient(df["y"]) ** 2)
    ) * (1 / np.mean(df["step_time"].diff()))

    df["head_dir"] = _convert_angles(df)

    df = df[df["trial"] != 1]

    interp = dict(
        a=9,
        b=-10,
        c=-2,
        d=27,
    )

    df["x"] = np.interp(
        df["x"], [-1 * interp["a"], interp["a"]], [-1 * interp["d"], interp["d"]]
    )

    df["y"] = np.interp(
        df["y"], [interp["b"], interp["c"]], [-1 * interp["d"], interp["d"]]
    )  # attention z considered as y

    df["trial_rewarded"] = df.groupby(["trial"], as_index=False)["reward"].transform(
        lambda x: np.max(x)
    )

    df[["trial_step", "trial_step_time"]] = df.groupby(
        ["trial"], as_index=True, group_keys=False
    ).apply(lambda x: x.iloc[:] - x.iloc[0])[["step", "step_time"]]

    if no_iti:
        df = df[df.iti == 0.0]
        df["trial_step_fraction"] = df.groupby(
            ["trial"], as_index=True, group_keys=False
        ).apply(lambda x: x.iloc[:] / x.iloc[-1])["trial_step"]
        df["trial_right_choice"] = df.groupby(["trial"], as_index=False)[
            "mouse_in_right"
        ].transform(lambda x: x.iloc[-1])
        df["trial_left_choice"] = df.groupby(["trial"], as_index=False)[
            "mouse_in_left"
        ].transform(lambda x: x.iloc[-1])
    else:
        df["trial_step_fraction"] = df.groupby(
            ["trial"], as_index=True, group_keys=False
        ).apply(lambda x: x.iloc[:] / x.iloc[-1])["trial_step"]

    return df, interp


def get_box_df(key, interp):

    box_df = pd.DataFrame((vr4mice.Box & key).fetch(as_dict=True)[0])

    a = interp["a"]
    b = interp["b"]
    c = interp["c"]
    d = interp["d"]

    # same indexes among blocks
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

    box_df = box_df.iloc[1]
    return box_df


def _plot_boxes(box_df, ax):
    """
    Plot boxes on trajectory plots.
    Args:
        box_df (pd.DataFrame): A pandas DataFrame containing the box information.
            Must have columns "tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max",
            "left_box_x_min", "left_box_x_max", "left_box_z_min", "left_box_z_max",
            "right_box_x_min", "right_box_x_max", "right_box_z_min", and "right_box_z_max".

        ax (plt.Axes): A matplotlib Axes object to plot the boxes on.
    Returns:
          None.
    """
    start_box = plt.Rectangle(
        (box_df["tt_box_x_min"], box_df["tt_box_z_min"]),
        abs(box_df.tt_box_x_min - box_df.tt_box_x_max),
        abs(box_df.tt_box_z_min - box_df.tt_box_z_max),
        fill=False,
        linewidth=4,
        edgecolor="#009B9E",
        alpha=0.6,
    )
    left_box = plt.Rectangle(
        (box_df["left_box_x_min"], box_df.left_box_z_min),
        abs(box_df.left_box_x_min - box_df.left_box_x_max),
        abs(box_df.left_box_z_min - box_df.left_box_z_max),
        fill=False,
        linewidth=4,
        edgecolor="#5C0A72",
        alpha=0.6,
    )
    right_box = plt.Rectangle(
        (box_df["right_box_x_min"], box_df.right_box_z_min),
        abs(box_df.right_box_x_min - box_df.right_box_x_max),
        abs(box_df.right_box_z_min - box_df.right_box_z_max),
        fill=False,
        linewidth=4,
        edgecolor="#FD672C",
        alpha=0.6,
    )
    ax.add_patch(start_box)
    ax.add_patch(left_box)
    ax.add_patch(right_box)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)


def _plot_rewards(rewarded, ax):
    """
    Plots the mean reward and the mean reward rate for each of the target locations.
    Args:
        rewarded (pandas.DataFrame): The DataFrame containing the data to be plotted (df["rewarded"])
        ax (list): A list of three axes to be used for the subplots.
    Returns:
        None
    """
    ax[0].bar("reward", np.mean(rewarded["reward"]), color="#284553")
    ax[0].set_ylim(0, 1)
    ax[0].set_xlim(-1, 1)
    ax[0].set_ylabel("Prob.")
    ax[0].set_title("Rewarded")
    sns.barplot(
        data=rewarded,
        x="object_on_left",
        y="reward",
        ax=ax[1],
        palette=["#FD672C", "#5C0A72"],
    )
    ax[1].set_ylim(0, 1)
    ax[1].set_ylabel("Prob.")
    ax[1].set_xlabel("Object location")
    ax[1].set_xticks([0.0, 1.0], ["R", "L"])

    ax[2].bar(rewarded["trial"], rewarded["reward"], color="grey")

    # PLOT
    ax[2].plot(
        rewarded["reward"]
        .rolling(15, min_periods=1, win_type="gaussian", center=True)
        .mean(std=3),
        color="#B52916",
        linewidth=3,
    )
    ax[2].set_ylabel("Rewarded")


def _plot_choices(choices, ax):
    """
    Plots mean choices and mean target location for each trial.
    Args:
        df: A DataFrame containing choice information (df["choices"])
        ax: A numpy array of axis objects to plot on.
    Returns:
        None
    """
    ax[0].bar("P(Left)", np.mean(choices["mouse_in_left"]), color="#284553")
    ax[0].set_ylim(0, 1)
    ax[0].set_xlim(-1, 1)
    ax[0].set_title("Choices")
    ax[0].set_ylabel("Prob.")
    ax[1].bar("P(Left)", np.mean(choices["object_on_left"]), color="#284553")
    ax[1].set_ylim(0, 1)
    ax[1].set_xlim(-1, 1)
    ax[1].set_title("Target location")
    ax[1].set_ylabel("Prob.")


def _plot_all_trajectories(df, box_df, ax):
    """
    Plot all the trajectories.
    Args:
        df (pandas.DataFrame): DataFrame containing the data to plot.
        box_df (pandas.DataFrame): DataFrame containing the box data to plot.
        ax (matplotlib.axes._subplots.AxesSubplot): Axes object to plot the data onto.
    Returns:
        None
    """

    for i in range(1, int(np.max(df.trial))):  # int added
        # PLOT
        ax.plot(
            df.x[(df.trial == i)],
            df.y[(df.trial == i)],
            c="black",
            alpha=0.2,
            linewidth=2,
        )
    first = df.groupby("trial").first()
    ax.scatter(first.x, first.y, c="#2250C8", alpha=1, s=30, zorder=100)
    rewards = np.where(df["reward"] > 0)[0]
    # print(rewards)
    R_choices = np.where(df["reward"] > 0)[0]
    trial_start = np.diff(df["trial"])
    ax.scatter(
        df.x.iloc[rewards], df.y.iloc[rewards], c="#B52916", alpha=0.7, s=30, zorder=100
    )
    _plot_boxes(box_df=box_df, ax=ax)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
    ax.set_xlabel("X pos (cm)")
    ax.set_ylabel("Y pos (cm)")


def _plot_rewarded_trial_trajectories(df, box_df, ax, rewarded):
    """
    Plot trajectories for rewarded trials for the right target and the left target - RR and LR are data frames.
    Args:
        df (pandas DataFrame): The data to plot.
        box_df (pandas DataFrame): DataFrame containing the position and size of the boxes.
        ax (list of matplotlib Axes): The axes to plot on.

    Returns:
        None
    """
    df = df.groupby("trial", as_index=False).apply(lambda group: group.iloc[1:, :])

    RR = df[
        (df.trial.isin(rewarded.trial[rewarded.reward == 1.0]))
        & (df.trial.isin(rewarded.trial[rewarded.object_on_left == 0.0]))
    ]
    LR = df[
        (df.trial.isin(rewarded.trial[rewarded.reward == 1.0]))
        & (df.trial.isin(rewarded.trial[rewarded.object_on_left == 1.0]))
    ]

    if not RR.empty:
        _plot_all_trajectories(RR, box_df, ax=ax[0])

        ax[0].set_title("Right rewarded")
        _plot_boxes(box_df=box_df, ax=ax[0])

        ax[0].set_xlim(-28, 28)
        ax[0].set_ylim(-28, 28)
    else:
        logger.warning("RR is empty, can't plot rewarded trial trajectories for RR.")

    if not LR.empty:
        _plot_all_trajectories(LR, box_df, ax=ax[1])

        ax[1].set_title("Left rewarded")
        _plot_boxes(box_df=box_df, ax=ax[1])

        ax[1].set_xlim(-28, 28)
        ax[1].set_ylim(-28, 28)
    else:
        logger.warning("LR is empty, can't plot rewarded trial trajectories for LR.")


def _plot_choices_by_trial(df, ax, choices):
    """
    Plots the choices the animal makes on each trial along with its rolling mean of choices and which trials were
    rewarded.
    Args:
        df (pandas.DataFrame): The dataframe containing the data.
        ax (matplotlib.axes._subplots.AxesSubplot): The subplot axes.

    Returns:
        None.
    """

    df = df.groupby("trial", as_index=False).apply(lambda group: group.iloc[1:, :])
    rewarded = df[df.reward == 1.0]
    last = choices
    # ax.bar(rewarded.trial, rewarded.object_on_left,)
    # PLOT
    ax.plot(
        last.trial,
        last.mouse_in_left.rolling(
            10, center=True, win_type="gaussian", min_periods=1
        ).mean(std=5),
        c="black",
        linewidth=3,
    )
    ax.scatter(last.trial, last.mouse_in_left, c="black", alpha=0.3)
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.mouse_in_left == 1.0)],
        rewarded.mouse_in_left[
            (rewarded.reward == 1.0) & rewarded.mouse_in_left == 1.0
        ],
        c="#5C0A72",
    )
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.mouse_in_right == 1.0)],
        rewarded.mouse_in_left[
            (rewarded.reward == 1.0) & rewarded.mouse_in_right == 1.0
        ],
        c="#FD672C",
    )
    ax.set_xlabel("Trials")
    ax.set_ylabel("Choice (1 = Left)")


def _time_to_rewards(df):  # split
    """
    This function calculates the time it takes for the animal to enter the box for rewarded vs unrewarded trials and Left and right choices.
    called in create_data_frame to initialize box_entries values

    Args:
        df: pandas.DataFrame containing the data
        ax: a list of two matplotlib axes to plot the results

    Returns:
        box_entries
    """

    box_entries = (
        df[(df.mouse_in_right == 1.0) | (df.mouse_in_left == 1.0)]
        .groupby("trial", as_index=False)
        .first()
    )  #
    box_entries["rewarded"] = df.groupby(["trial"], as_index=False).max()["reward"]  #

    return box_entries


def _plot_time_to_rewards(df, ax):
    """
    This function plots the time it takes for the animal to enter the box for rewarded vs unrewarded trials and Left and right choices.
    Args:
        box_entries: pandas.DataFrame containing the data df["box_entries"]
        ax: a list of two matplotlib axes to plot the results
    Returns:
        None
    """

    box_entries = (
        df[(df["mouse_in_right"] == 1.0) | (df["mouse_in_left"] == 1.0)]
        .groupby("trial", as_index=False)
        .first()
    )  #
    box_entries["rewarded"] = df.groupby(["trial"], as_index=False).max()["reward"]  #

    cat1 = box_entries[box_entries["rewarded"] == 1.0]
    cat2 = box_entries[box_entries["rewarded"] == 0.0]

    p_value = stats.ttest_ind(
        np.log(cat1["trial_step_time"]), np.log(cat2["trial_step_time"])
    )[1]

    g = sns.stripplot(
        data=box_entries,
        x="rewarded",
        y="trial_step_time",
        palette=["#284553", "#B52916"],
        hue="rewarded",
        ax=ax[0],
        alpha=0.7,
        legend=False,
        zorder=1,
    )
    # sns.boxplot(data = time_diff, x = "reward", y = "step_time", palette = ["#284553", "#B52916"], hue = "reward")

    sns.pointplot(
        data=box_entries,
        x="rewarded",
        y="trial_step_time",
        estimator=np.mean,
        markers="D",
        scale=1,
        color="black",
        ax=ax[0],
        join=False,
    )
    g.set_yscale("log")
    g.set_title("Time to report")
    g.set_ylabel("log(Seconds)")
    g.set_xlabel("Reward")
    g.set_xticks([0.0, 1.0], ["incorrect", "correct"], rotation=45, fontsize=10)
    g.annotate(
        "p={p_value:.3f}",
        xy=(0.75, 0.95),
        xycoords="axes fraction",
        fontsize=12,
        color="black",
    )

    cat1 = box_entries[box_entries["mouse_in_left"] == 1.0]
    cat2 = box_entries[box_entries["mouse_in_left"] == 0.0]
    p_value = stats.ttest_ind(
        np.log(cat1["trial_step_time"]), np.log(cat2["trial_step_time"])
    )[1]

    box_entries = box_entries[box_entries.rewarded == 1.0]
    p = sns.stripplot(
        data=box_entries,
        x="mouse_in_left",
        y="trial_step_time",
        palette=["#FD672C", "#5C0A72"],
        hue="mouse_in_left",
        ax=ax[1],
        alpha=0.7,
        legend=False,
        zorder=1,
    )
    # sns.boxplot(data = time_diff, x = "reward", y = "step_time", palette = ["#284553", "#B52916"], hue = "reward")

    sns.pointplot(
        data=box_entries,
        x="mouse_in_left",
        y="trial_step_time",
        estimator=np.mean,
        markers="D",
        scale=1,
        color="black",
        ax=ax[1],
        join=False,
    )
    p.set_yscale("log")
    p.set_title("Time to Report")
    p.set_ylabel("log(Seconds)")
    p.set_xlabel("Choice (rewarded)")
    p.set_xticks([0.0, 1.0], ["R", "L"])
    p.annotate(
        "p={p_value:.3f}",
        xy=(0.75, 0.95),
        xycoords="axes fraction",
        fontsize=12,
        color="black",
    )


def interpolate_trials_cubic_spline(
    df, num_points, column_trial="trial", column_velocity="velocity"
):
    """
    Interpolates velocity and heading direction variables for each trial.
    [DJ trialInterpolated table], note: check keys of the output for interpolated_df attributes
    note-2: Group the data frame by the trial column

    Args:
        df: pandas DataFrame containing the data to be interpolated.
        num_points (int): the number of points to interpolate.
        column_trial (str): name of the column containing trial information.
        column_velocity (str): name of the column containing velocity information.

    Returns:
        pandas DataFrame containing the interpolated data.
    """

    grouped = df.groupby(column_trial)

    # Initialize an empty data frame to store the interpolated data
    interpolated_df = pd.DataFrame(
        columns=[
            column_trial,
            "index",
            column_velocity,
            "heading_dir",
            "trial_reward",
            "choice_R",
            "choice_L",
        ]
    )

    # Iterate through the groups (trials)
    for trial, group in grouped:
        # Create a new index for interpolation
        new_index = np.linspace(group.index.min(), group.index.max(), num_points)

        # Perform cubic spline interpolation on the velocity data
        cs = CubicSpline(group.index, group[column_velocity])
        interpolated_velocity = cs(new_index)
        cs = CubicSpline(group.index, group["trial_step_fraction"])
        interpolated_trial_step_fraction = cs(new_index)
        cs = CubicSpline(group.index, group["head_dir"])
        head_dir = cs(new_index)
        trial_reward = np.repeat(
            np.max(df.reward[group.index]), len(interpolated_velocity)
        )
        R_choice = np.repeat(
            np.max(df.mouse_in_right[group.index]), len(interpolated_velocity)
        )
        L_choice = np.repeat(
            np.max(df.mouse_in_left[group.index]), len(interpolated_velocity)
        )

        # Create a new data frame for the interpolated data of the current trial
        interpolated_trial_df = pd.DataFrame(
            {
                column_trial: trial,
                "index": np.linspace(0, num_points, num_points) / num_points,
                column_velocity: interpolated_velocity,
                "heading_dir": head_dir,
                "trial_reward": trial_reward,
                "choice_R": R_choice,
                "choice_L": L_choice,
            }
        )

        # Append the interpolated data to the final data frame
        interpolated_df = pd.concat(
            [interpolated_df, interpolated_trial_df], ignore_index=True
        )
    return interpolated_df


def _plot_heading_direction(df, ax):
    """
    Plots the interpolated heading direction of the mouse.
    Args:
        df (pandas.DataFrame): Input data frame.
        ax (matplotlib.axes.Axes): Axes object to use for the plot.

    Returns:
        None.
    """

    int_df = interpolate_trials_cubic_spline(df, 200)  # FETCH
    g = sns.lineplot(
        data=int_df,
        x="index",
        y="heading_dir",
        hue="choice_L",
        style="trial_reward",
        palette=["#FD672C", "#5C0A72"],
        ax=ax,
        style_order=int_df["trial_reward"].sort_values(ascending=False).unique(),
    )

    choice_legend = plt.legend(
        handles=g.get_lines()[:2],
        labels=["Correct", "Incorrect"],
        title="Right",
        loc="center right",
        bbox_to_anchor=(1, 0.7),
        fontsize=6,
    )
    reward_legend = plt.legend(
        handles=g.get_lines()[2:],
        labels=["Correct", "Incorrect"],
        title="Left",
        loc="center right",
        bbox_to_anchor=(1, 0.4),
        fontsize=6,
    )

    # Add the custom legends to the plot
    ax.add_artist(choice_legend)
    ax.add_artist(reward_legend)
    ax.set_xlabel("Trial length (interpolated)")
    ax.set_ylabel("Heading angle")

    # int_df = interpolate_trials_cubic_spline(df, 200)
    # int_df = int_df[int_df.trial_reward == 0.0]
    # g = sns.lineplot(data = int_df, x = "index", y = "heading_dir", hue = "choice_L", palette = ['#FD672C', "#5C0A72"],ax= ax, linestyle = "dashed")


def _plot_trial_velocities(df, ax):
    """
    Plots the interpolated velocity for each trial.
    Args:
        df (pandas.DataFrame): DataFrame containing trial data.
        ax (matplotlib.axes.Axes): Axes object to plot the data.

    Returns:
        None.
    """

    int_df = interpolate_trials_cubic_spline(df, 200)
    g = sns.lineplot(
        data=int_df,
        x="index",
        y="velocity",
        hue="trial_reward",
        palette=["#284553", "#B52916"],
        ax=ax[0],
    )
    g.set_xlabel("Trial length (interpolated)")
    g.set_ylabel("Velocity (cm/S)")

    handles, labels = ax[0].get_legend_handles_labels()
    ax[0].legend(
        handles=handles,
        labels=["Incorrect", "Correct"],
        title="rewarded",
        loc="upper right",
    )

    p = sns.lineplot(
        data=int_df,
        x="index",
        y="velocity",
        hue="choice_L",
        palette=["#FD672C", "#5C0A72"],
        ax=ax[1],
    )
    p.set_xlabel("Trial length (interpolated)")
    p.set_ylabel("Velocity (cm/S)")
    handles, labels = ax[1].get_legend_handles_labels()
    ax[1].legend(handles=handles, labels=["R", "L"], title="choice", loc="upper right")


def get_rewarded(df):
    rewarded = df.groupby(["trial"], as_index=False).max()
    return rewarded


def get_choices(df):
    choices = df.groupby(["trial"], as_index=False).last()
    return choices


def fetch_data(key, database):
    # fetch or populate to get df (externalize)
    if database:
        from vr4mice.schema import base_analysis

        try:
            df, interp = base_analysis.DataFrame().get_data(key)
            flag = df is False
            if not flag:
                logger.info("Data fetched for " + str(key))
            else:
                logger.info("Populating DataFrame data for " + str(key))
                df = base_analysis.DataFrame().populate(key)
                df, interp = base_analysis.DataFrame().get_data(key)
                flag = df is False
                if not flag:
                    logger.info("Data populated and fetched for " + str(key))

            rewarded = base_analysis.DataFrame().get_rewarded(key)
            choices = base_analysis.DataFrame().get_choices(key)

        except Exception as e:
            logger.warning(f"An error occurred: {e}")

        try:
            box_df_output = base_analysis.BoxDataFrame().get_data(key)
            flag = box_df_output is False
            if not flag:
                logger.info("Box data fetched for " + str(key))
            else:
                logger.info("Populating BoxDataFrame data for " + str(key))
                box_df_output = base_analysis.BoxDataFrame().populate(key)
                box_df_output = base_analysis.BoxDataFrame().get_data(key)
                flag = box_df_output is False
                if not flag:
                    logger.info("Data populated and fetched for " + str(key))

        except Exception as e:
            logger.warning(f"An error occurred: {e}")
    else:
        df, interp = create_data_frame(key, no_iti=True)
        box_df_output = get_box_df(key, interp=interp)
        rewarded = get_rewarded(df)
        choices = get_choices(df)

    return df, interp, box_df_output, rewarded, choices


def get_path(key, base, ext=".png"):
    name = str(key) + "_summary_plot" + ext
    return Path(base).joinpath(name)


def get_subtitle(key, task_name="AR Task"):
    # todo: add parcing of filename
    return task_name + ": Dataset: " + str(key["dataset"])


def vr4mice_summary_plots(key, save_path="/data/summary_plots", database=True):
    """
    Generate a summary plot for a given dataset.
    final results to email
    [DJ SummaryPlot table: path?]
    Args:
        key (dict): A dictionary containing the following keys: "mouse_name", "day", and "attempt". This specifies which dataset to generate a summary plot for.
        save_path (str, optional): The directory path where the summary plot should be saved. Defaults to "/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/".

    Returns:
        str: The full path of the saved summary plot.

    """

    df, interp, box_df_output, rewarded, choices = fetch_data(key, database)

    fig = plt.figure(figsize=(25, 20), constrained_layout=True)

    gs = plt.GridSpec(6, 8, figure=fig)
    ax1 = fig.add_subplot(gs[0:2, 0:3])

    ax2 = fig.add_subplot(gs[0:2, 3:5])
    ax3 = fig.add_subplot(gs[0:2, 5:7])

    ax4 = fig.add_subplot(gs[2, 0:1])
    ax5 = fig.add_subplot(gs[2, 1:2])
    ax6 = fig.add_subplot(gs[2, 2:3])
    ax7 = fig.add_subplot(gs[2, 3:4])
    time_plots_1 = fig.add_subplot(gs[2, 4:6])
    time_plots_2 = fig.add_subplot(gs[2, 6:8])
    ax8 = fig.add_subplot(gs[4, :])
    ax9 = fig.add_subplot(gs[5, :])

    velocity_plot_reward = fig.add_subplot(gs[3, 0:2])
    velocity_plot_choice = fig.add_subplot(gs[3, 2:4])
    heading_angle_plot = fig.add_subplot(gs[3, 4:6])

    _plot_all_trajectories(df=df, box_df=box_df_output, ax=ax1)
    _plot_rewarded_trial_trajectories(
        df=df, box_df=box_df_output, ax=[ax2, ax3], rewarded=rewarded
    )

    _plot_time_to_rewards(df, ax=[time_plots_1, time_plots_2])
    _plot_trial_velocities(df, ax=[velocity_plot_reward, velocity_plot_choice])
    _plot_heading_direction(df, ax=heading_angle_plot)
    _plot_choices(choices, ax=[ax4, ax5])
    _plot_rewards(rewarded, ax=[ax6, ax7, ax8])
    _plot_choices_by_trial(df, ax=ax9, choices=choices)

    if database:
        full_path = base_analysis.OutputPlots().get_path(
            key=key, base=save_path, ext=".png"
        )
        subtitle = base_analysis.OutputPlots().get_subtitle(
            key=key, task_name="AR Task"
        )
    else:
        full_path = get_path(key=key, base=save_path, ext=".png")
        subtitle = get_subtitle(key=key, task_name="AR Task")

    fig.suptitle(subtitle)
    plt.savefig(full_path)
    plt.close()  # interactive

    return full_path
