from typing import List, Optional
import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.interpolate
import umap
from sklearn.decomposition import PCA
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()

import vr4mice.analysis.analysis as analysis

from vr4mice.schema import vr4mice, dlc, base_analysis


def create_bins(
    data, spatial_ybins: List[int] = [-13, 24, 50], label: str = "y"
) -> pd.DataFrame:
    """Create bins on the y axis of the data.

    Args:
        data: A dataframe.
        spatial_ybins (List[int]): 3 values list, respectively first and last values to consider and number of bins to consider.
        label: Default is `y`. Column to use to create the bins. Another possible column would be `norm_y`.

    Returns:
        The dataframe with 2 extra columns, the bin corresponding to each sample, and the center of that interval.

    """
    data["bins"] = pd.cut(
        data[label],
        bins=np.linspace(spatial_ybins[0], spatial_ybins[1], spatial_ybins[2]),
    )
    data.loc[:, "bin_centers"] = data["bins"].apply(lambda x: x.mid).astype("float")
    return data


def _grid_positions(index: pd.Index, n_points: int) -> np.ndarray:
    """Evenly spaced positions over a group's retained row index."""
    return np.linspace(index.min(), index.max(), n_points)


def interpolate_group(
    group: pd.DataFrame,
    n_points: int,
    interpolation_columns: List[str],
    value_columns: List[str],
) -> pd.DataFrame:
    """Interpolate for the provided group of data.

    Args:
        group: A dataframe containing the data to interpolate.
        num_points (int): the number of points to interpolate.
        interpolation_columns (List[str]): List of the names of the columns to group the data by.
        value_columns (List[str]): List of the names of the columns containing the values to interpolate.

    Returns:
        pandas DataFrame of length `n_points`, containing the interpolated data and the interpolation
        columns data for all groups.

    """
    # Generate new evenly spaced x values within the original range for interpolation
    x_new = _grid_positions(group.index, n_points)

    # Retrieve groupby identifiers (they are uniform within the group)
    ids = {}
    for group_column in interpolation_columns:
        ids[group_column] = group[group_column].iloc[0]

    # Dictionary to collect new interpolated values
    interpolated_data = {"time": x_new}

    for column in value_columns:

        x = group.index
        y = group[column]

        if "aperture" in column:
            y_new = np.full(x_new.shape, y.iloc[0])

        else:
            # Check for NaN values and handle them
            mask = ~np.isnan(y)

            if mask.sum() < 2:  # Need at least 2 points for interpolation
                logger.warning(
                    f"Column '{column}' has insufficient non-NaN values for interpolation. Filling with zeros."
                )
                y_new = np.zeros(x_new.shape)
            elif mask.sum() == len(y):
                # No NaN values, proceed normally
                cs = scipy.interpolate.CubicSpline(x, y)
                y_new = cs(x_new)
            else:
                # Has some NaN values - interpolate only on valid points
                x_valid = x[mask]
                y_valid = y[mask]
                cs = scipy.interpolate.CubicSpline(x_valid, y_valid)
                y_new = cs(x_new)

        # Store the interpolated values
        interpolated_data[column] = y_new

    interpolated_df = pd.DataFrame(interpolated_data)

    for group_column in interpolation_columns:
        interpolated_df[group_column] = ids[group_column]

    return interpolated_df


def interpolate(
    df: pd.DataFrame,
    n_points: int = 100,
    interpolation_columns: List[int] = ["dataset", "trial"],
    value_columns: List[int] = ["x", "norm_x", "velocity", "head_dir"],
) -> pd.DataFrame:
    """
    Interpolates the variables in the value columns provided for each group formed by the interpolation columns.

    Note: Check keys of the output for interpolated_df attributes.
    Note: By default group the data frame by ["mouse_name", "date", "attempt", "trial"].

    The dataframe is grouped by `interpolation_columns` and the values contained in the columns
    `value_columns` are interpolated so that each group is `n_points` samples.

    Args:
        df: pandas DataFrame containing the data to be interpolated.
        num_points (int): the number of points to interpolate.
        interpolation_columns (List[str]): List of the names of the columns to group the data by.
        value_columns (List[str]): List of the names of the columns containing the values to interpolate.

    Returns:
        pandas DataFrame containing the interpolated data and the interpolation columns data for all groups.
    """
    interpolated_dfs = []

    # Compute the interpolation for each trial
    interpolated_dfs = [
        interpolate_group(group, n_points, interpolation_columns, value_columns)
        for _, group in df.groupby(interpolation_columns)
    ]
    final_interpolated_df = pd.concat(interpolated_dfs).reset_index(drop=True)

    return final_interpolated_df


def prepare_j_shaped_trials(big_df, box_df):
    """Return the rows ``interpolate_j_shaped`` interpolates, and its value columns.

    Adds the derived kinematics to ``big_df`` (in place), keeps J-shaped
    trials and drops rows with a missing value in any interpolated column.
    """
    big_df["optimal_p"] = analysis.get_optimal_p(big_df)
    big_df["local_tortuosity"] = analysis.get_local_tortuosity(big_df, window_size=1)
    big_df["flip_one_side"] = big_df["trial_left_choice"].replace([0, 1], [1, -1])
    big_df["distance_to_choice"] = analysis.get_distance_to_choice(big_df, box_df)

    columns = [
        "heading_dir",
        "head_angle",
        "trial_tortuosity",
        "trial_duration",
        "x",
        "y",
        "aperture",
        "velocity",
        "velocity_x",
        "velocity_y",
        "trial_rewarded",
        "flip_one_side",
        "distance_to_choice",
        "optimal_p",
        "local_tortuosity",
    ]

    j_shaped = analysis.get_jshaped_trials(big_df)

    # Filter out trials with NaN values in critical columns to avoid interpolation errors
    cols_to_check = ["trial_left_choice"] + columns
    j_shaped_clean = j_shaped.dropna(subset=cols_to_check)

    if len(j_shaped_clean) < len(j_shaped):
        logger.warning(
            f"Dropped {len(j_shaped) - len(j_shaped_clean)} rows with NaN values before interpolation in j-shaped trials"
        )
    return j_shaped_clean, cols_to_check


def trial_grid_times(j_shaped, n_points=100):
    """Times of the ``interpolate_j_shaped`` samples of each trial.

    Uses the same rows and sample positions as the interpolation, so row
    ``trial_step`` of a trial is the moment of its interpolated sample.

    Args:
        j_shaped: Rows from ``prepare_j_shaped_trials``, with ``step_time``.
        n_points: Samples per trial, as in ``interpolate_j_shaped``.

    Returns:
        DataFrame with ``dataset``, ``trial``, ``trial_step`` and the
        interpolated ``step_time`` per sample.
    """
    parts = []
    for (dataset, trial), group in j_shaped.groupby(["dataset", "trial"]):
        positions = _grid_positions(group.index, n_points)
        parts.append(
            pd.DataFrame(
                {
                    "dataset": dataset,
                    "trial": int(trial),
                    "trial_step": np.arange(n_points),
                    "step_time": np.interp(
                        positions, group.index, group["step_time"].astype(float)
                    ),
                }
            )
        )
    if not parts:
        return pd.DataFrame(columns=["dataset", "trial", "trial_step", "step_time"])
    return pd.concat(parts, ignore_index=True)


def interpolate_j_shaped(big_df, box_df, n_points=100):
    j_shaped_clean, cols_to_check = prepare_j_shaped_trials(big_df, box_df)
    interpolated_j_shaped = interpolate(
        j_shaped_clean,
        n_points=n_points,
        value_columns=cols_to_check,
        interpolation_columns=["dataset", "trial"],
    )
    interpolated_j_shaped["trial_step"] = interpolated_j_shaped.groupby(
        ["dataset", "trial"], as_index=False
    ).trial.cumcount()

    interpolated_j_shaped["trial_length"] = (
        interpolated_j_shaped["trial_step"] / n_points
    )
    interpolated_j_shaped["head_angle_sin"] = np.sin(
        np.deg2rad(interpolated_j_shaped.head_angle)
    )
    interpolated_j_shaped["head_angle_cos"] = np.cos(
        np.deg2rad(interpolated_j_shaped.head_angle)
    )

    interpolated_j_shaped["heading_dir_sin"] = np.sin(
        np.deg2rad(interpolated_j_shaped.heading_dir)
    )
    interpolated_j_shaped["heading_dir_cos"] = np.cos(
        np.deg2rad(interpolated_j_shaped.heading_dir)
    )

    interpolated_j_shaped["velocity_x_fliped"] = (
        interpolated_j_shaped["velocity_x"] * interpolated_j_shaped["flip_one_side"]
    )
    return interpolated_j_shaped


def cluster(
    df: pd.DataFrame,
    method: Optional[str] = "pca",
    label_x: Optional[str] = "norm_x",
    label_y: Optional[str] = "norm_y",
) -> npt.NDArray:
    """Compute dimensionality reduction using the specified method.

    This function performs dimensionality reduction on the interpolated data using
    either PCA (Principal Component Analysis) or UMAP (Uniform Manifold Approximation and Projection).

    NOTE: This function may be refactored in the future to include more dimensionality
    reduction methods or to adapt to different data structures.

    Args:
        df (pd.DataFrame): DataFrame containing interpolated data where all trials have the same size.
        method (str, optional): The dimensionality reduction algorithm to use. Options are "pca" or "umap". Default is "pca".
        label_x (str, optional): Column label for the x-axis data. Default is "norm_x".
        label_y (str, optional): Column label for the y-axis data. Default is "norm_y".

    Returns:
        np.ndarray: The computed latents using the specified method.

    """

    data_x = np.concatenate(
        df.groupby(["dataset", "trial"])[label_x].apply(np.array).values
    ).reshape(-1, 200)
    data_y = np.concatenate(
        df.groupby(["dataset", "trial"])[label_y].apply(np.array).values
    ).reshape(-1, 200)

    data = np.concatenate(
        [data_x, data_y], axis=1
    )  # NOTE(celia): to adapt based on the data to include

    if method == "umap":
        standard_embedding = umap.UMAP(
            random_state=42, n_neighbors=30, min_dist=0
        ).fit_transform(data)
    elif method == "pca":
        pca = PCA(n_components=2)
        standard_embedding = pca.fit_transform(data)
    else:
        raise NotImplementedError(f"{method}")

    return standard_embedding


def compute_start_position(
    df: pd.DataFrame, box_df: pd.DataFrame, n_bins: Optional[int] = 3
) -> pd.DataFrame:
    """Add a column `x_init_bin_center` to the dataframe.

    Group the trials per x-position at trial initialization.

    Args:
        n_bins (int): Number of bins to cut the init area in to group
            the trial.
    """

    start, end = box_df["tt_box_x_min"], box_df["tt_box_x_max"]
    bin_edges = np.linspace(start, end, n_bins + 1)
    bin_midpoints = (bin_edges[:-1] + bin_edges[1:]) / 2

    starting_positions = df.groupby("trial")["x"].first().reset_index()
    starting_positions["bin_idx"] = (
        np.digitize(starting_positions["x"], bin_edges, right=False) - 1
    )  # Adjust bin index to be 0-based
    starting_positions["x_init_bin_center"] = starting_positions["bin_idx"].apply(
        lambda x: bin_midpoints[x] if x < len(bin_midpoints) else np.nan
    )

    return pd.merge(
        df, starting_positions[["trial", "x_init_bin_center"]], on="trial", how="left"
    )


def get_data_from_list(data_set_list, game_columns, dlc_columns=None):
    big_df = []
    for d in data_set_list:
        split_d = d["dataset"].split("_")
        logger.info(split_d)
        data_set_name = d["dataset"]
        training_stage = (vr4mice.Dataset() & f"dataset = '{data_set_name}'").fetch(
            "session_label"
        )[0]

        df = base_analysis.DataFrame().get_data(
            key=d,
            columns=game_columns,
        )
        df["trial_rewarded"] = base_analysis.DataFrame().get_rewarded(key=d)
        if dlc_columns is not None:
            offline_kinematics_df = dlc.OfflineKinematics().get_data(
                key=d,
                columns=dlc_columns,
            )
            df = pd.concat([df, offline_kinematics_df], axis=1)

        df["mouse_name"] = split_d[0]
        df["date"] = split_d[1]
        df["attempt"] = split_d[2]
        df["training_stage"] = training_stage

        big_df.append(df)

    big_df = pd.concat(big_df).reset_index()

    big_df["session_increment"] = (
        big_df.groupby("mouse_name")["dataset"]
        .rank(method="dense", ascending=True)
        .astype(int)
    )

    big_df = big_df.infer_objects()

    return big_df.reset_index(drop=True)


def apply_inclusion_criteria(
    data: pd.DataFrame,
    return_excluded: Optional[bool] = False,
    consider_reward_drop: Optional[bool] = True,
    min_reward: float = 0.7,
    max_reward_drop: float = 0.25,
    reward_basis: str = "widest",
    min_narrow_reward: Optional[float] = None,
    return_details: bool = False,
) -> tuple:
    """Filter datasets by reward-based inclusion criteria.

    Rewards are compared at the narrowest and widest apertures present in
    ``data``. The defaults reproduce the published (batch1) selection:

    1. Reward: the widest-aperture reward must be > ``min_reward``. With
       ``reward_basis="best_extreme"``, the larger of the narrowest and widest
       rewards is used instead.
    2. Reward drop, when ``consider_reward_drop`` is True:
       ``abs(reward_widest - reward_narrowest)`` must be < ``max_reward_drop``.
       If ``min_narrow_reward`` is set, a dataset whose narrowest-aperture
       reward is > ``min_narrow_reward`` also passes this criterion (e.g. 0.5:
       a large drop is tolerated while the hardest condition is above chance).

    Apertures are rounded to two decimals before grouping, so float noise does
    not split one aperture into two. Rewards are averaged within each trial,
    then across trials, ignoring missing values. A dataset without a reward at
    either extreme aperture (for example, sessions from tasks with different
    apertures in one call) is excluded, with a warning.

    Args:
        data: Input dataframe containing at least ``dataset``, ``aperture``,
            ``trial``, and ``trial_rewarded``.
        return_excluded: If True, return rows from datasets that fail the
            criteria instead of those that pass.
        consider_reward_drop: Whether to apply the reward-drop criterion.
        min_reward: Minimum reward, applied according to ``reward_basis``.
        max_reward_drop: Maximum absolute reward difference between the widest
            and narrowest apertures.
        reward_basis: ``"widest"`` or ``"best_extreme"``.
        min_narrow_reward: Optional narrowest-aperture reward above which the
            reward-drop criterion passes on its own. None disables it.
        return_details: If True, also return the criteria used.

    Returns:
        ``(filtered_data, reward_table)``, or ``(filtered_data, reward_table,
        criteria_details)`` when ``return_details`` is True.

    Raises:
        ValueError: If columns are missing, there are no trials, apertures are
            not numeric, fewer than two apertures are present, or a criterion
            is out of range.
    """
    reward_bases = ("widest", "best_extreme")
    if reward_basis not in reward_bases:
        raise ValueError(
            f"reward_basis must be one of {reward_bases}, got {reward_basis!r}"
        )
    if not 0 <= min_reward <= 1:
        raise ValueError(f"min_reward must be within [0, 1], got {min_reward}")
    if not 0 <= max_reward_drop <= 1:
        raise ValueError(
            f"max_reward_drop must be within [0, 1], got {max_reward_drop}"
        )
    if min_narrow_reward is not None and not 0 <= min_narrow_reward <= 1:
        raise ValueError(
            f"min_narrow_reward must be None or within [0, 1], got {min_narrow_reward}"
        )
    required = ["dataset", "aperture", "trial", "trial_rewarded"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"Inclusion criteria need columns {missing}")
    if data.empty:
        raise ValueError("No trials to apply inclusion criteria to")

    try:
        apertures = pd.to_numeric(data["aperture"]).round(2)
    except (TypeError, ValueError) as err:
        raise ValueError("Apertures must be numeric") from err
    reward_table = (
        data[required]
        .assign(aperture=apertures)
        .groupby(["dataset", "aperture", "trial"], as_index=False)["trial_rewarded"]
        .mean()
    )
    reward_table = reward_table.groupby(["dataset", "aperture"], as_index=False)[
        "trial_rewarded"
    ].mean()
    pivoted_reward = reward_table.pivot(index="dataset", columns="aperture")

    # Extract aperture values from the MultiIndex columns (second level)
    aperture_values = [
        col[1] for col in pivoted_reward.columns if col[0] == "trial_rewarded"
    ]

    if len(aperture_values) < 2:
        raise ValueError(
            f"Not enough occluder sizes found to apply inclusion criteria. "
            f"Found {len(aperture_values)}, need at least 2."
        )

    narrowest_aperture = min(aperture_values)
    widest_aperture = max(aperture_values)
    narrowest_reward = pivoted_reward[("trial_rewarded", narrowest_aperture)]
    widest_reward = pivoted_reward[("trial_rewarded", widest_aperture)]

    # Both extremes are required whichever criteria are enabled.
    pivoted_reward["has_extreme_rewards"] = (
        narrowest_reward.notna() & widest_reward.notna()
    )
    missing_extreme = pivoted_reward.index[~pivoted_reward["has_extreme_rewards"]]
    if len(missing_extreme):
        logger.warning(
            "Excluded for lacking a reward at aperture %s or %s: %s",
            narrowest_aperture,
            widest_aperture,
            ", ".join(map(str, missing_extreme)),
        )
    pivoted_reward["reward_drop"] = widest_reward - narrowest_reward
    pivoted_reward["best_extreme_reward"] = pd.concat(
        [narrowest_reward, widest_reward], axis=1
    ).max(axis=1, skipna=False)
    criterion_reward = (
        widest_reward
        if reward_basis == "widest"
        else pivoted_reward["best_extreme_reward"]
    )
    pivoted_reward["passes_min_reward"] = criterion_reward > min_reward
    pivoted_reward["passes_reward_drop"] = (
        pivoted_reward["reward_drop"].abs() < max_reward_drop
    )
    if min_narrow_reward is not None:
        pivoted_reward["passes_narrow_reward"] = narrowest_reward > min_narrow_reward
        pivoted_reward["passes_reward_drop"] |= pivoted_reward["passes_narrow_reward"]

    pivoted_reward["included_by_criteria"] = (
        pivoted_reward["has_extreme_rewards"] & pivoted_reward["passes_min_reward"]
    )
    if consider_reward_drop:
        pivoted_reward["included_by_criteria"] &= pivoted_reward["passes_reward_drop"]

    criteria_details = {
        "min_reward": float(min_reward),
        "reward_basis": reward_basis,
        "max_reward_drop": float(max_reward_drop),
        "consider_reward_drop": bool(consider_reward_drop),
        "min_narrow_reward": (
            None if min_narrow_reward is None else float(min_narrow_reward)
        ),
        "narrowest_aperture": float(narrowest_aperture),
        "widest_aperture": float(widest_aperture),
        "aperture_values": [float(value) for value in aperture_values],
    }
    for name, value in criteria_details.items():
        pivoted_reward[f"criteria_{name}"] = [value] * len(pivoted_reward)

    reward_table = pivoted_reward
    included_datasets = reward_table.index[reward_table["included_by_criteria"]]

    if return_excluded:
        filtered_data = data[data.dataset.isin(included_datasets) == 0]
    else:
        filtered_data = data[data.dataset.isin(included_datasets)]

    if return_details:
        return filtered_data, reward_table, criteria_details

    return filtered_data, reward_table


def get_training_stage_per_mouse(big_df, mouse_name, inv=False):
    training_stages = ["ar_detection_no_velthr", "ar_detection_velthr", "ar_discrim"]
    if inv:
        training_stages = [f"{stage}_inv" for stage in training_stages]
        training_stages[0] = "ar_det_no_velthr_inv"

    new_df_list = []
    mouse_df = big_df[big_df.mouse_name == mouse_name].copy()

    df = mouse_df[(mouse_df.training_stage == training_stages[0])].copy()

    early = df[df.session_increment == df.session_increment.unique()[0]].copy()
    early["num_train_stage"] = 0
    new_df_list.append(early)

    mid = df[df.session_increment == df.session_increment.unique()[-1]].copy()  # -2
    mid["num_train_stage"] = 1
    new_df_list.append(mid)

    df = mouse_df[(mouse_df.training_stage == training_stages[0])].copy()
    late = df[df.session_increment == df.session_increment.unique()[-1]].copy()  # 0
    late["num_train_stage"] = 2
    new_df_list.append(late)

    df = mouse_df[(mouse_df.training_stage == training_stages[2])].copy()

    early = df[df.session_increment == df.session_increment.unique()[0]].copy()
    early["num_train_stage"] = 3
    new_df_list.append(early)

    late = df[df.session_increment == df.session_increment.unique()[-1]].copy()  # 1
    late["num_train_stage"] = 5
    new_df_list.append(late)

    if len(df.session_increment.unique()) > 2:
        mid = df[df.session_increment == df.session_increment.unique()[-2]].copy()
        mid["num_train_stage"] = 4
        new_df_list.append(mid)
    return pd.concat(new_df_list)
