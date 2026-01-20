import warnings
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.optimize

from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger

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
            # "axes.titleweight": "bold",
            "axes.titlesize": font_size,
            "xtick.labelcolor": font_color,
            "xtick.labelsize": font_size,
            "ytick.labelcolor": font_color,
            "ytick.labelsize": font_size,
            "font.weight": "regular",
            # "svg.fonttype": "none",
        }
    )

    plt.rc("axes.spines", top=False, bottom=True, left=True, right=False)
    plt.rc("axes", edgecolor=font_color)


def _resample_data_frame(
    df: pd.DataFrame, resampling_period_ms: int = 20
) -> pd.DataFrame:  # in ms
    categorical_columns = ["aperture"]
    binary_columns = ["reward", "mouse_in_right", "mouse_in_left", "iti"]
    continuous_columns = df.columns[
        (~df.columns.isin(categorical_columns)) & (~df.columns.isin(binary_columns))
    ]

    t = (
        f"{resampling_period_ms}ms"
    )  # old: 0.02s, err: ValueError: invalid literal for int() with base 10: '0.02'

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

    if "level_0" in df.columns:
        df = df.drop(columns=["level_0"])

    reference_datetime = df["time"].iloc[0]
    df["time_elapsed"] = (df["time"] - reference_datetime).dt.total_seconds()

    return df


def get_rewarded(df: pd.DataFrame) -> pd.Series:
    """Creates a `trial_rewarded` pandas.Series from a single session.

    Note: `df` needs to be a single session.

    Returns:
        A pandas.Series with 1 if the trial to which the timepoint
        belongs to is rewarded and 0 else.
    """

    return df.groupby(["dataset", "trial"])["reward"].transform(lambda x: x.max())


def get_distance_to_choice(df: pd.DataFrame, box_df: pd.DataFrame) -> pd.Series:
    """Compute the distance from each point in a DataFrame to the center of the chosen reward box.

    Args:
        df (pd.DataFrame): DataFrame containing the coordinates of points, with columns 'x' and 'y'.
                           The 'x' coordinates may be flipped depending on the 'flip_one_side' column.
        box_df (pd.DataFrame): DataFrame containing the coordinates of the chosen reward box.

    Returns:
        A pandas.Series containing the distance to the chosen reward box for each point in `df`.
    """

    return pd.Series(
        np.sqrt(
            ((box_df["r_reward_x"].iloc[0] - (df["x"] * df["flip_one_side"]))) ** 2
            + (box_df["r_reward_z"].iloc[0] - df["y"]) ** 2
        )
    )


def get_local_tortuosity(df: pd.DataFrame, window_size: int = 1) -> pd.Series:
    """Compute the local tortuosity around each timepoint.

    The points to consider around a given point are taken around the point with
    a window of `window_size` on each side.

    Tortuosity is the ratio between the path length and the direct path between the
    past and future points determined using the `window_size` around the current point.

    Args:
        df (pd.DataFrame): Dataframe containing the coordinates of points, with columns 'x' and 'y'.
        window_size (int): Window size corresponding to the distance to center point to determine
            the past and future timepoint to consider to compute tortuosity between them.

    Returns:
        A pandas.Series containing the local tortuosity for each timepoint.
    """
    groupby_columns = ["dataset", "trial"]

    # Shift positions to create local windows (shift forward and backward by 1)
    x_pos_after = df.groupby(groupby_columns)["x"].shift(window_size)
    y_pos_after = df.groupby(groupby_columns)["y"].shift(window_size)
    x_pos_before = df.groupby(groupby_columns)["x"].shift(-window_size)
    y_pos_before = df.groupby(groupby_columns)["y"].shift(-window_size)

    # Calculate total path length in the local window
    local_path_length = sum(
        np.sqrt(
            (df.groupby(groupby_columns)["x"].shift(i) - df["x"]) ** 2
            + (df.groupby(groupby_columns)["y"].shift(i) - df["y"]) ** 2
        )
        + np.sqrt(
            (df["x"] - df.groupby(groupby_columns)["x"].shift(-i)) ** 2
            + (df["y"] - df.groupby(groupby_columns)["y"].shift(-i)) ** 2
        )
        for i in range(1, window_size + 1)
    )

    # Calculate direct path length between past and future points
    local_direct_path = np.sqrt(
        (x_pos_after - x_pos_before) ** 2 + (y_pos_after - y_pos_before) ** 2
    )
    local_direct_path.replace(0, np.nan, inplace=True)

    # Compute tortuosity and handle NaNs
    local_tortuosity = local_path_length / local_direct_path
    local_tortuosity.fillna(local_tortuosity.mean(), inplace=True)

    return pd.Series(local_tortuosity)


def get_optimal_p(
    df: pd.DataFrame, groupby_columns: List[str] = ["dataset", "trial"]
) -> pd.Series:
    """Get the optimal parameter p to parametrize a trial trajectory with a L-p curve.

    Note: L-p curves are parametrized by p which control the angularity of the curve.
    The higher p is the higher the curve is angular (compared to a more rounded curve).

    Parametrization is as follow: (|x|^p/a^p + |y|^p/b^p)^(1/p) = 1

    Args:
        df (pd.DataFrame): Dataframe containing the coordinates of points, with columns 'x' and 'y'.

    Returns:
        A pandas.Series containing the optimal p to parametrize the trajectory of the trial to
        which each timepoint belongs.
    """

    def _compute_optimal_p(trial_data):
        """Compute the optimal p for a given trial."""
        x = trial_data["x"].values
        y = trial_data["y"].values
        points = np.vstack((x, y)).T

        # Normalize the points to fit a scaled L-p curve
        max_norm = np.max(np.linalg.norm(points, axis=1))
        normalized_points = points / max_norm

        def _loss_function(p: float):
            """Loss function for normalized L-p curve fitting."""
            distances = np.power(
                (
                    np.abs(normalized_points[:, 0]) ** p
                    + np.abs(normalized_points[:, 1]) ** p
                )
                / 2,
                1 / p,
            )
            return np.sum((distances - normalized_points[:, 1]) ** 2)

        initial_p = 2.0
        result = scipy.optimize.minimize(_loss_function, initial_p, bounds=[(1, 25)])
        return result.x[0]

    optimal_p_per_trial = df.groupby(groupby_columns).apply(_compute_optimal_p)
    return df.set_index(groupby_columns).index.map(optimal_p_per_trial)


def set_first_xy_to_nan(group: pd.DataFrame) -> pd.DataFrame:
    """
    Sets the first x and y positions of the given DataFrame to np.nan.

    This function is designed to be used with groups from a pandas `DataFrameGroupBy` object,
    typically resulting from a groupby operation. It addresses the spawning error in the Unity
    game at the start of each trial, where the virtual mouse is spawned at incorrect coordinates.
    It removes these initial points so they can be interpolated or estimated from neighboring values.

    Args:
        group (pd.DataFrame): A subset DataFrame from a pandas groupby operation, usually grouped by trial.

    Returns:
        pd.DataFrame: The modified DataFrame with the first x- y- and head_dir values set to np.nan.
    """
    group.loc[group.index[0], ["x", "y", "head_dir"]] = np.nan
    return group


def create_data_frame(
    key: dict,
    iti: bool = True,
    first_n_samples: int = 3,
    spatial_ybins: List[int] = [-27, 27, 75],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create main dataframe for analysis.

    Load and preprocess behavioral data and box coordinates.

    Args:
        key (dict): Dictionary containing keys for VR4Mice database. (VR4Mice)
        iti (bool): If False, it removes rows where iti=0.0 from dataframe (default=True).
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
    trial = (vr4mice.State & key).fetch("episode")  # change of name
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

    unity_to_physical_arena_size = dict(
        unity_arena_size_x_min=9,
        unity_arena_size_z_max=-10,
        unity_arena_size_z_min=-2,
        physical_arena_size=27,
    )

    df["x"] = np.interp(
        df.x,
        [
            -1 * unity_to_physical_arena_size["unity_arena_size_x_min"],
            unity_to_physical_arena_size["unity_arena_size_x_min"],
        ],
        [
            -1 * unity_to_physical_arena_size["physical_arena_size"],
            unity_to_physical_arena_size["physical_arena_size"],
        ],
    )
    df["y"] = np.interp(
        df.y,
        [
            unity_to_physical_arena_size["unity_arena_size_z_max"],
            unity_to_physical_arena_size["unity_arena_size_z_min"],
        ],
        [
            -1 * unity_to_physical_arena_size["physical_arena_size"],
            unity_to_physical_arena_size["physical_arena_size"],
        ],
    )

    # Handling for first frame in trial - the first frame results in the default x,y position and head_dir for virtual mouse.
    # They therefore needs to be set to a nan and then interpolated from neighboring points.
    df = (
        df.groupby("trial", as_index=False)
        .apply(set_first_xy_to_nan)
        .reset_index(drop=True)
    )
    df[["x", "y", "head_dir"]] = df[["x", "y", "head_dir"]].interpolate()
    # First trial cannot be interpolated so back fill this point this with the next value
    df[["x", "y", "head_dir"]] = df[["x", "y", "head_dir"]].bfill()

    # Normalized coordinates
    df["bins_y"] = pd.cut(
        df["y"], bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2])
    )
    df["norm_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda x: x - np.mean(x.iloc[:first_n_samples])
    )
    if not iti:
        df = df[df.iti == 0.0]

    trial_right_choice = (
        df[df["iti"] == 0].groupby("trial")["mouse_in_right"].last().reset_index()
    )
    df = df.merge(trial_right_choice, on="trial", suffixes=("", "_trial_right_choice"))
    df.rename(
        columns={"mouse_in_right_trial_right_choice": "trial_right_choice"},
        inplace=True,
    )

    trial_left_choice = (
        df[df["iti"] == 0].groupby("trial")["mouse_in_left"].last().reset_index()
    )
    df = df.merge(trial_left_choice, on="trial", suffixes=("", "_trial_left_choice"))
    df.rename(
        columns={"mouse_in_left_trial_left_choice": "trial_left_choice"}, inplace=True
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

    trial_duration = (
        df[df["iti"] == 0]
        .groupby("trial")["time_elapsed"]
        .agg(["first", "last"])
        .reset_index()
    )
    trial_duration["trial_duration"] = trial_duration["last"] - trial_duration["first"]
    df = df.merge(trial_duration[["trial", "trial_duration"]], on="trial")

    if iti:
        iti_duration = (
            df[df["iti"] == 1]
            .groupby("trial")["time_elapsed"]
            .agg(["first", "last"])
            .reset_index()
        )
        iti_duration["iti_duration"] = iti_duration["last"] - iti_duration["first"]
        df = df.merge(iti_duration, on="trial")

    # Distance between sample points and length of the trajectory
    df["distance"] = np.sqrt(df.x.diff() ** 2 + df.y.diff() ** 2)

    # Trial trajectory length only on the non-ITI part
    trial_traj_path_length = (
        df[df["iti"] == 0].groupby("trial")["distance"].sum().reset_index()
    )
    df = df.merge(
        trial_traj_path_length, on="trial", suffixes=("", "_trial_traj_path_length")
    )
    df.rename(
        columns={"distance_trial_traj_path_length": "trial_traj_path_length"},
        inplace=True,
    )

    # Trial start and end position
    df["trial_init_x"] = df.groupby("trial", as_index=False)["x"].transform(
        lambda x: x.iloc[0]
    )
    df["trial_init_y"] = df.groupby("trial", as_index=False)["y"].transform(
        lambda y: y.iloc[0]
    )
    trial_end_x = df[df["iti"] == 0].groupby("trial")["x"].last().reset_index()
    df = df.merge(trial_end_x, on="trial", suffixes=("", "_trial_end_x"))
    df.rename(columns={"x_trial_end_x": "trial_end_x"}, inplace=True)

    trial_end_y = df[df["iti"] == 0].groupby("trial")["y"].last().reset_index()
    df = df.merge(trial_end_y, on="trial", suffixes=("", "_trial_end_y"))
    df.rename(columns={"y_trial_end_y": "trial_end_y"}, inplace=True)

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

    df["flip_one_side"] = df["trial_left_choice"].replace([0, 1], [1, -1])

    df.trial = df.trial.astype(int)
    df.aperture = df.aperture.round(2)

    df = df.drop(columns=["first", "last"])

    return df, unity_to_physical_arena_size


def get_box_df(
    key: dict, df: pd.DataFrame, unity_to_physical_arena_size: dict
) -> pd.DataFrame:
    """Define the box dimensions based on arena, start area, and reward area sizes.

    This function takes in the data related to arena box positions, interpolates
    unity-based coordinates to physical space, and calculates the reward positions
    within the left and right boxes based on trial results.

    Args:
        key (dict): Dictionary containing keys for VR4Mice database. (VR4Mice)
        df (pd.DataFrame): A DataFrame containing trial data, including reward and choice columns.
        unity_to_physical_arena_size (dict): A dictionary to interpolate physical arena sizes based
            on Unity-based arena sizes.

    Returns:
        pd.DataFrame: A DataFrame containing the adjusted box dimensions in physical space and
            the mean reward positions for the left and right reward boxes.
    """
    box_df = (vr4mice.Box & key).to_pandas()

    for col in box_df.columns:
        for index, value in box_df[col].items():
            if isinstance(value, list):
                box_df.loc[index, col] = value[0]

    a = unity_to_physical_arena_size["unity_arena_size_x_min"]
    b = unity_to_physical_arena_size["unity_arena_size_z_max"]
    c = unity_to_physical_arena_size["unity_arena_size_z_min"]
    d = unity_to_physical_arena_size["physical_arena_size"]

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

    return box_df


def get_jshaped_trials(
    df: pd.DataFrame, threshold_duration: int = 5, threshold_tortuosity: int = 5
) -> pd.DataFrame:
    """
    Separates the trials in the DataFrame into 'J-shaped' and 'wandering' based on the given thresholds.

    Note:
        It also adds a column j-shaped to the df, to indicate if a given
        trial is j-shaped or no.

    Args:
        df (pd.DataFrame): The DataFrame containing trial data with columns 'trial_duration' and 'trial_tortuosity'.
        threshold_duration (int): The maximum duration for a trial to be considered 'J-shaped'. Default is 5.
        threshold_tortuosity (int): The maximum tortuosity for a trial to be considered 'J-shaped'. Default is 5.

    Returns:
        tuple: A tuple containing two DataFrames:
            - j_shaped (pd.DataFrame): DataFrame containing trials that are classified as 'J-shaped'.
            - wandering (pd.DataFrame): DataFrame containing trials that are classified as 'wandering'.
    """
    df.loc[:, "is_j_shaped"] = np.where(
        (df.trial_duration <= threshold_duration)
        & (df.trial_tortuosity <= threshold_tortuosity),
        1,
        0,
    )

    j_shaped = df[df["is_j_shaped"] == 1]
    return j_shaped


def mean_xy_trajectory(
    df,
    index_columns=[
        "dataset",
        "mouse_name",
        "aperture",
        "trial_left_choice",
        "trial_length",
    ],
    values=["x", "y"],
):
    mean_df = df.groupby(index_columns, as_index=False)[values].mean()
    mean_df[["sem_x", "sem_y"]] = df.groupby(index_columns, as_index=False)[
        values
    ].sem()[values]
    mean_df[["std_x", "std_y"]] = df.groupby(index_columns, as_index=False)[
        values
    ].std()[values]
    return mean_df
