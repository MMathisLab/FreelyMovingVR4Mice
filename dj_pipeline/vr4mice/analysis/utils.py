from typing import List, Optional

import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.interpolate
import umap
from sklearn.decomposition import PCA

"""
Color codes:
    - left box: purple: '#5C0A72'
    - right box: orange: '#FD672C'
    - center box: blue: '#009B9E'
    
    - SET1 colormap for the apertures, 
    4.3 = '#EC8788', 12 = '#96B9D6'
"""


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
    data["bin_centers"] = data["bins"].apply(lambda x: x.mid).astype("float")  # - 25
    return data


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
    x_new = np.linspace(group.index.min(), group.index.max(), n_points)

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
            # Fit Cubic Spline
            cs = scipy.interpolate.CubicSpline(x, y)

            # Interpolate y values at the new x positions
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
    interpolation_columns: List[int] = ["session", "trial"],
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
        df.groupby(["session", "trial"])[label_x].apply(np.array).values
    ).reshape(-1, 200)
    data_y = np.concatenate(
        df.groupby(["session", "trial"])[label_y].apply(np.array).values
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
    df: pd.DataFrame, df_box: pd.DataFrame, n_bins: Optional[int] = 3
) -> pd.DataFrame:
    """Add a column `x_init_bin_center` to the dataframe.

    Group the trials per x-position at trial initialization.

    Args:
        n_bins (int): Number of bins to cut the init area in to group
            the trial.
    """

    start, end = df_box["tt_box_x_min"], df_box["tt_box_x_max"]
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
