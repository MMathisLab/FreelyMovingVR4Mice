"""
    This script contains functions wrappers for plotting.py script:
    It fetches the columns from database tables that are only required for a function,
    Instead of fetching the whole table that is heavy as contians multiple longblobs
"""
from typing import Optional, Tuple
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.collections
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.stats as stats
import seaborn as sns
from matplotlib.collections import PathCollection
from matplotlib.transforms import Affine2D
from scipy.interpolate import CubicSpline

from vr4mice.analysis import plotting
from vr4mice.schema import vr4mice, base_analysis, dlc
from typing import List
from vr4mice.utils.logger import Logger
import inspect

logger = Logger.get_logger()


def plot_box_rectangle(
    box_label: str,
    datasets_keys: List = [],
    edgecolor: str = "#009B9E",
    fill: bool = False,
    alpha: float = 0.6,
    linewidth: int = 4,
):
    """{box_label}_box_x_min: The minimum x-coordinate of the box.
    {box_label}_box_x_max: The maximum x-coordinate of the box.
    {box_label}_box_z_min: The minimum z-coordinate of the box.
    {box_label}_box_z_max: The maximum z-coordinate of the box.

    session_labels: contains ensemble of datasets that we would like to fetch.

    """
    df = None
    label_mapping = {"left": "l", "right": "r"}

    if box_label.lower() in label_mapping:
        box_label = label_mapping[box_label.lower()]

    columns = [
        f"{box_label}_box_x_min",
        f"{box_label}_box_x_max",
        f"{box_label}_box_z_min",
        f"{box_label}_box_z_max",
    ]

    if len(datasets_keys) == 0:
        df = base_analysis.BoxDataFrame().get_all_data(columns)
    else:
        df = []
        for key in datasets_keys:
            key = {"dataset": key}
            df.append(base_analysis.BoxDataFrame().get_data(key=key, columns=columns))

        df = pd.concat(df, ignore_index=True)

    if df.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(
            f"Warning in function: {current_function}: BoxDataFrame is empty."
        )
        return False

    return plotting.plot_box_rectangle(df, box_label, edgecolor, fill, alpha, linewidth)


def plot_all_boxes(ax, datasets_keys: List = []):
    """Plot boxes on trajectory plots.

    Args:
        ax (matplotlib.axes.Axes): A matplotlib Axes object to plot the boxes on.
    """
    start_box = plot_box_rectangle(
        box_label="tt", edgecolor="#009B9E", datasets_keys=datasets_keys
    )
    left_box = plot_box_rectangle(
        box_label="left", edgecolor="#5C0A72", datasets_keys=datasets_keys
    )
    right_box = plot_box_rectangle(
        box_label="right", edgecolor="#FD672C", datasets_keys=datasets_keys
    )

    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
    ax.add_patch(start_box)
    ax.add_patch(left_box)
    ax.add_patch(right_box)


def plot_trajectories(
    ax,
    datasets_keys: List = [],
    per_side: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):

    df = None

    columns = ["trial", "trial_left_choice", "x", "y", "reward"]

    if len(datasets_keys) == 0:
        df = base_analysis.DataFrame().get_all_data(columns)
    else:
        df = []
        for key in datasets_keys:
            key = {"dataset": key}
            df.append(base_analysis.DataFrame().get_data(key=key, columns=columns))

        df = pd.concat(df, ignore_index=True)

    if df.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(f"Warning in function: {current_function}: DataFrame is empty.")
        return False

    plotting.plot_trajectories(df, ax, per_side, label_x, label_y, scatter_reward)


def _plot_session_in_arena(
    ax,
    datasets_keys: List = [],
    per_side: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    plot_all_boxes(ax=ax, datasets_keys=datasets_keys)
    plot_trajectories(
        ax=ax,
        datasets_keys=datasets_keys,
        per_side=per_side,
        label_x=label_x,
        label_y=label_y,
        scatter_reward=scatter_reward,
    )


# TODO: sync with a function from DJ
def plot_session(
    dataset_key: str,  # NOTE: since 1 session only
    ax: Optional[mpl.axes.Axes] = None,
    per_side: bool = False,
    per_aperture: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    key = f"dataset='{dataset_key}'"
    if not (base_analysis.DataFrame() & key):
        logger.warning(
            f"{dataset_key} hasn't been found in base_analysis.DataFrame() table."
        )
        return False

    aperture = base_analysis.DataFrame().get_data(key, ["aperture"])
    if aperture is False or aperture is None:
        logger.warning(
            f"'aperture' entry for {dataset_key} hasn't been found in base_analysis.DataFrame() table."
        )
        return False
    num_aperture = len(aperture.aperture.unique())

    if ax is None:
        if per_aperture:
            fig, ax = plt.subplots(1, num_aperture, figsize=(int(num_aperture * 5), 5))
        else:
            fig, ax = plt.subplots(1, 1, figsize=(5, 5))

        if per_aperture and num_aperture == 1:
            ax = [ax]

        if per_aperture:
            # TODO(celia): add tests on axes.
            for j, aperture in enumerate(np.sort(aperture.aperture.unique())):
                _plot_session_in_arena(
                    ax=ax[j],
                    datasets_keys=[dataset_key],
                    per_side=per_side,
                    label_x=label_x,
                    label_y=label_y,
                    scatter_reward=scatter_reward,
                )
                ax[j].set_title(f"{dataset_key}_{aperture}")
        else:
            _plot_session_in_arena(
                datasets_keys=[dataset_key],
                ax=ax,
                per_side=per_side,
                label_x=label_x,
                label_y=label_y,
                scatter_reward=scatter_reward,
            )
            ax.set_title(f"{dataset_key}")

    fig.tight_layout(pad=0.1)


def plot_rewards(
    datasets_keys: List = [],
    per_aperture: bool = False,
    per_day: bool = False,  # TODO(celia): to add for Fig.2 E.
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):

    # columns = ["dataset", "trial_rewarded", "aperture", "trial"]

    if len(datasets_keys) == 0:
        df = base_analysis.DataFrame().get_all_rewarded()
    else:
        df = []
        for key in datasets_keys:
            key = {"dataset": key}
            df.append(base_analysis.DataFrame().get_rewarded(key=key))

        df = pd.concat(df, ignore_index=True)

    if df.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(
            f"Warning in function: {current_function}: BoxDataFrame is empty."
        )
        return False

    return plotting.plot_rewards(df, per_aperture, per_day, alpha, ax, cmap)


def plot_time_to_reward(
    datasets_keys: List = [],
    ax: Optional[matplotlib.axes.Axes] = None,
    alpha: float = 0.5,
    cmap: str = "Set1",
):
    columns = ["dataset", "trial_step", "mouse_in_left", "mouse_in_right"]

    if len(datasets_keys) == 0:
        df_rew = base_analysis.DataFrame().get_all_rewarded()
        df_data = base_analysis.DataFrame().get_all_data(columns)
        df = pd.concat(
            [df_rew, df_data[df_data.columns.difference(["dataset"])]],
            axis=1,
            join="inner",
        )
    else:
        df = []
        for key in datasets_keys:
            key = {"dataset": key}
            df_rew = base_analysis.DataFrame().get_rewarded(key=key)
            df_data = base_analysis.DataFrame().get_data(key, columns)
            df.append(
                pd.concat(
                    [df_rew, df_data[df_data.columns.difference(["dataset"])]],
                    axis=1,
                    join="inner",
                )
            )

        df = pd.concat(df, ignore_index=True)

    if df.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(
            f"Warning in function: {current_function}: BoxDataFrame is empty."
        )
        return False
    return plotting.plot_time_to_reward(df, ax, alpha, cmap)


def plot_init_position_histogram(
    datasets_keys: List = [],
    ax: Optional[matplotlib.axes.Axes] = None,
    bins=3,
    cmap="magma",
    vmax=10,
    is_colorbar: bool = True,
    is_density: bool = False,
):

    current_function = inspect.currentframe().f_code.co_name
    columns_df = ["dataset", "trial", "trial_init_x", "trial_init_y"]
    columns_bx = ["tt_box_x_min", "tt_box_x_max", "tt_box_z_min", "tt_box_z_max"]

    if len(datasets_keys) == 0:
        df = base_analysis.DataFrame().get_all_data(columns_df)
        df_box = base_analysis.BoxDataFrame().get_all_data(columns_bx)
    else:
        df_data = []
        df_box = []
        for key in datasets_keys:
            key = {"dataset": key}
            df_data_tmp = base_analysis.DataFrame().get_data(key, columns_df)
            if df_data_tmp is False or df_data_tmp is None:
                logger.warning(
                    f"Warning in function: {current_function}: {key} is missing in DataFrame table."
                )
                return False

            df_data.append(df_data_tmp)

            df_box_tmp = base_analysis.BoxDataFrame().get_data(
                key=key, columns=columns_bx
            )

            if df_box_tmp is False or df_box_tmp is None:
                logger.warning(
                    f"Warning in function: {current_function}: {key} is missing in BoxDataFrame table."
                )
                return False

            df_box.append(df_box_tmp)

        df = pd.concat(df_data, ignore_index=True)
        df_box = pd.concat(df_box, ignore_index=True)

    if df.empty or df_box.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(
            f"Warning in function: {current_function}: BoxDataFrame is empty."
        )
        return False

    return plotting.plot_init_position_histogram(
        df, df_box, ax, bins, cmap, vmax, is_colorbar, is_density
    )


def plot_trial_count(
    datasets_keys: List = [],
    per_aperture: bool = False,
    per_day: bool = False,  # TODO(celia): to add for Fig.2 E.
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):

    df = None

    columns = ["dataset", "trial", "aperture"]

    if len(datasets_keys) == 0:
        df = base_analysis.DataFrame().get_all_data(columns)
    else:
        df = []
        for key in datasets_keys:
            key = {"dataset": key}
            df.append(base_analysis.DataFrame().get_data(key=key, columns=columns))

        df = pd.concat(df, ignore_index=True)

    if df.empty:
        current_function = inspect.currentframe().f_code.co_name
        logger.warning(f"Warning in function: {current_function}: DataFrame is empty.")
        return False
    plotting.plot_trial_count(df, per_aperture, per_day, alpha, ax, cmap)
