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

"""
Color codes:
    - left box: purple: '#5C0A72'
    - right box: orange: '#FD672C'
    - center box: blue: '#009B9E'
    
    - SET1 colormap for the apertures, 
    4.3 = '#EC8788', 12 = '#96B9D6'
"""

colors_choice = ["#5C0A72", "#FD672C"]
colors_aperture = ["#E41A1C", "#437FB5", "#4daf4a", "#984ea3", "#ff7f00"]
colors_aperture_pale = ["#EC8788", "#96B9D6"]


def lineplot_flip_axis(ax: Optional[matplotlib.axes.Axes] = None, **kwargs):
    """Creates a seaborn line plot and flips the axes.

    This function generates a line plot using seaborn's `lineplot` function,
    then applies a transformation to flip the axes such that the x-axis becomes
    the y-axis and vice versa. The resulting plot will have the x-axis as the
    vertical axis and the y-axis as the horizontal axis.

    Args:
        ax : matplotlib.axes.Axes, optional
            The axes object to draw the plot onto. If not provided, the current
            axes will be used.
        **kwargs : keyword arguments
            Additional keyword arguments to pass to `sns.lineplot`.

    Returns:
        matplotlib.axes.Axes
            The axes object with the transformed plot.

    Examples:
        >>> import pandas as pd
        >>> import matplotlib.pyplot as plt
        >>> df = pd.DataFrame({
        ...     'x': range(10),
        ...     'y': [i**2 for i in range(10)]
        ... })
        >>> fig, ax = plt.subplots()
        >>> lineplot_flip_axis(data=df, x='x', y='y', ax=ax)
        >>> plt.show()

    Notes:
        This function applies an affine transformation to the plot elements to flip
        the axes. It scales the y-axis by -1 and rotates the plot by 90 degrees.
        The axis labels are also swapped to reflect the transformation.
    """
    if ax is None:
        line = sns.lineplot(**kwargs)
    else:
        line = sns.lineplot(**kwargs, ax=ax)

    r = Affine2D().scale(sx=1, sy=-1).rotate_deg(90)
    for x in line.images + line.lines + line.collections:
        trans = x.get_transform()
        x.set_transform(r + trans)
        if isinstance(x, PathCollection):
            transoff = x.get_offset_transform()
            x._transOffset = r + transoff

    old = line.axis()
    line.axis(old[2:4] + old[0:2])
    xlabel = line.get_xlabel()
    line.set_xlabel(line.get_ylabel())
    line.set_ylabel(xlabel)

    return line


def plot_box_rectangle(
    df_box: pd.DataFrame,
    box_label: str,
    edgecolor: str = "#009B9E",
    fill: bool = False,
    alpha: float = 0.6,
    linewidth: int = 4,
    coords: bool = False,
):
    """Create a matplotlib Rectangle patch for a specified box.

    Args:
        df_box (pd.DataFrame): DataFrame containing the box coordinates.
        box_label (str): Prefix of the columns representing the box dimensions.
        edgecolor (str, optional): Color of the box edge. Default is "#009B9E".
        fill (bool, optional): Whether to fill the box. Default is False.
        alpha (float, optional): Alpha transparency for the box. Default is 0.6.
        linewidth (int, optional): Width of the box edge line. Default is 4.

    Returns:
        matplotlib.patches.Rectangle: The rectangle patch representing the box.

    """

    box_x_min = df_box[f"{box_label}_box_x_min"].iloc[0]
    box_z_min = df_box[f"{box_label}_box_z_min"].iloc[0]
    box_x_max = df_box[f"{box_label}_box_x_max"].iloc[0]
    box_z_max = df_box[f"{box_label}_box_z_max"].iloc[0]

    start_box_coords = (
        (box_x_min, box_z_min),
        abs(box_x_min - box_x_max),
        abs(box_z_min - box_z_max),
    )

    if coords:
        return start_box_coords

    return plt.Rectangle(
        *start_box_coords,
        fill=fill,
        linewidth=linewidth,
        edgecolor=edgecolor,
        alpha=alpha,
    )


def plot_all_boxes(ax, df_box: pd.DataFrame):
    """Plot boxes on trajectory plots.

    Args:
        ax (matplotlib.axes.Axes): A matplotlib Axes object to plot the boxes on.
        df_box (pd.DataFrame): A pandas DataFrame containing the box information.
            Must have columns "<box_label>_box_x_min", "<box_label>_box_x_max",
            "<box_label>_box_z_min", and "<box_label>_box_z_max" for each box label
            ("tt", "left", "right").
    """
    start_box = plot_box_rectangle(df_box, box_label="tt", edgecolor="#009B9E")
    left_box = plot_box_rectangle(df_box, box_label="left", edgecolor="#5C0A72")
    right_box = plot_box_rectangle(df_box, box_label="right", edgecolor="#FD672C")

    ax.add_patch(start_box)
    ax.add_patch(left_box)
    ax.add_patch(right_box)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)


def plot_trajectories(
    df: pd.DataFrame,
    ax,
    per_side: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    """
    Plot all the trajectories.

    Args:
        df (pandas.DataFrame): DataFrame containing the data to plot.
        ax (matplotlib.axes.Axes): Axes object to plot the data onto.
        per_side (bool, optional): If True, plot trajectories separately based on
            'trial_L_choice'. Default is False.
        label_x (str, optional): Column name for the x-axis data. Default is "x".
        label_y (str, optional): Column name for the y-axis data. Default is "y".
        scatter_reward (bool, optional): If True, scatter plot the reward points. Default is True.

    """
    for i in range(1, np.max(df.trial)):
        if per_side:
            ax.plot(
                df[label_x][((df.trial == i) & (df.trial_left_choice == 1))],
                df[label_y][((df.trial == i) & (df.trial_left_choice == 1))],
                c="#5C0A72",
                alpha=0.2,
                linewidth=2,
            )
            ax.plot(
                df[label_x][((df.trial == i) & (df.trial_left_choice == 0))],
                df[label_y][((df.trial == i) & (df.trial_left_choice == 0))],
                c="#FD672C",
                alpha=0.2,
                linewidth=2,
            )
        else:
            ax.plot(
                df[label_x][(df.trial == i)],
                df[label_y][(df.trial == i)],
                c="black",
                alpha=0.2,
                linewidth=2,
            )

    first = df.groupby("trial").first()
    ax.scatter(first.x, first.y, c="#2250C8", alpha=1, s=30, zorder=100)

    if scatter_reward:
        rewards = np.where(df["reward"] > 0)[0]

        ax.scatter(
            df.x.iloc[rewards],
            df.y.iloc[rewards],
            c="#B52916",
            alpha=0.7,
            s=20,
            zorder=100,
        )
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
    ax.set_xlabel("x position (cm)")
    ax.set_ylabel("y position (cm)")


def _plot_session_in_arena(
    df: pd.DataFrame,
    df_box: pd.DataFrame,
    ax,
    per_side: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    """Plot a session in the arena including trajectories and boxes.

    Args:
        df (pandas.DataFrame): DataFrame containing the trajectory data to plot.
        df_box (pandas.DataFrame): DataFrame containing the box data to plot.
        ax (matplotlib.axes.Axes): Axes object to plot the data onto.
        per_side (bool, optional): If True, plot trajectories separately based on
            'trial_L_choice'. Default is False.
        label_x (str, optional): Column name for the x-axis data. Default is "x".
        label_y (str, optional): Column name for the y-axis data. Default is "y".
        scatter_reward (bool, optional): If True, scatter plot the reward points. Default is True.

    """

    plot_all_boxes(ax, df_box)
    plot_trajectories(
        df=df,
        ax=ax,
        per_side=per_side,
        label_x=label_x,
        label_y=label_y,
        scatter_reward=scatter_reward,
    )


def plot_session(
    df: pd.DataFrame,
    df_box: pd.DataFrame,
    ax: Optional[matplotlib.axes.Axes] = None,
    per_side: bool = False,
    per_aperture: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    """
    Plots trajectories of sessions on given axes with optional initial position histograms.

    Args:
        df : pandas.DataFrame
            DataFrame containing the trial data with columns.

        df_box : pandas.DataFrame
            DataFrame containing the boundary values for the box.

        ax : list of matplotlib.axes.Axes
            List of matplotlib axes on which to plot the trajectories and histograms.

        per_side : bool, optional
            Whether to plot trajectories per side (default is False).

        per_aperture : bool, optional
            Whether to plot one plot per aperture width (default is False).

        label_x : str, optional
            Label for the x-axis data in the trajectory plot (default is "x").

        label_y : str, optional
            Label for the y-axis data in the trajectory plot (default is "y").

        scatter_reward : bool, optional
            Whether to scatter plot the reward positions (default is True).

    """

    if len(df.session.unique()) > 1:
        raise ValueError(
            f"Only one session should be provided, {len(df.session.unique())} were provided."
        )
    num_aperture = len(df.aperture.unique())

    if ax is None:
        if per_aperture:
            fig, ax = plt.subplots(1, num_aperture, figsize=(int(num_aperture * 5), 5))
        else:
            fig, ax = plt.subplots(1, 1, figsize=(5, 5))

        if per_aperture:
            # TODO(celia): add tests on axes.
            for j, aperture in enumerate(np.sort(df.aperture.unique())):
                data = df[df.aperture == aperture]
                _plot_session_in_arena(
                    df=data,
                    df_box=df_box,
                    ax=ax[j],
                    per_side=per_side,
                    label_x=label_x,
                    label_y=label_y,
                    scatter_reward=scatter_reward,
                )
                ax[j].set_title(f"{df.session.unique()[0]}_{aperture}")
        else:
            _plot_session_in_arena(
                df=df,
                df_box=df_box,
                ax=ax,
                per_side=per_side,
                label_x=label_x,
                label_y=label_y,
                scatter_reward=scatter_reward,
            )
            ax.set_title(f"{df.session.unique()[0]}")

    fig.tight_layout(pad=0.1)


#### Trial counts


def _plot_bar_counts(
    counts: pd.DataFrame,
    label_x: str = None,
    per_day: bool = False,  # TODO(celia): to add for Fig.2 E.
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot bar or line counts with optional color mapping.

    Args:
        counts (pd.DataFrame): DataFrame containing count data to plot.
        label_x (str, optional): Column label for the x-axis. Default is None.
        per_day (bool, optional): If True, plot per day. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """
    if label_x is None:
        label_x = [str(1) for i in range(len(counts))]
        figsize = (2, 5)
        counts["color"] = "grey"
        color_map = cmap
    else:
        unique_labels = counts[label_x].unique()
        figsize = (int(2 * len(unique_labels)), 5)
        cmap = sns.color_palette(cmap, len(unique_labels))
        color_map = {label: cmap[i] for i, label in enumerate(unique_labels)}
        counts["color"] = counts[label_x].map(color_map)

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

    if isinstance(label_x, str):
        sns.lineplot(
            data=counts,
            x=label_x,
            y="count",
            alpha=1,
            color="black",
            errorbar="se",
            err_style="bars",
            linewidth=2,
        )

        sns.lineplot(
            data=counts,
            x=label_x,
            y="count",
            hue="dataset",
            errorbar=None,
            alpha=alpha,
            color="black",
            palette=["grey"] * counts["dataset"].nunique(),
            markers="o",
        )
    else:
        sns.barplot(
            data=counts, x=label_x, y="count", color="grey", errorbar="se", alpha=alpha
        )
        ax.set_xlabel("")
        ax.set_xticklabels([])

    sns.scatterplot(
        data=counts, x=label_x, y="count", alpha=1, hue=label_x, palette=color_map)

    plt.legend([], [], frameon=False)


def plot_trial_count(
    df,  # TODO(celia): provide correct columns directly?
    per_aperture: bool = False,
    per_day: bool = False,  # TODO(celia): to add for Fig.2 E.
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot the count of trials per session or per aperture.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        per_day (bool, optional): If True, plot per day. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """
    if per_aperture:
        counts = (
            df.groupby(["dataset", "trial"])
            .aperture.first()
            .groupby(level="dataset")
            .value_counts()
            .sort_values()
        )
        counts = pd.DataFrame(counts.reset_index())
        counts.aperture = counts.aperture.round(2).astype(str)
    else:
        counts = df.groupby(["dataset"]).trial.nunique()
        counts = pd.DataFrame(counts.reset_index())
        counts = counts.rename(columns={"trial": "count"})

    _plot_bar_counts(
        counts=counts,
        label_x="aperture" if per_aperture else None,
        per_day=per_day,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    plt.ylabel("#Trials / session")

    if per_aperture:
        stats = pd.DataFrame(
            zip(
                df.groupby(["dataset", "aperture"])
                .trial.nunique()
                .groupby("aperture")
                .mean(),
                df.groupby(["dataset", "aperture"])
                .trial.nunique()
                .groupby("aperture")
                .sem(),
            ),
            columns=["mean", "sem"],
            index=df.groupby(["dataset", "aperture"])
            .trial.nunique()
            .groupby("aperture")
            .mean()
            .index,
        )

    else:
        stats = (
            df.groupby(["dataset"]).trial.nunique().mean(),
            df.groupby(["dataset"]).trial.nunique().sem(),
        )
    print(stats)


# NOTE(mary): we have dataset as PK, no 'session'
def plot_rewards(
    df,  # TODO(celia): provide correct columns directly?
    per_aperture: bool = False,
    per_day: bool = False,  # TODO(celia): to add for Fig.2 E.
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot the success rate per session or per aperture.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        per_day (bool, optional): If True, plot per day. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """
    if per_aperture:
        counts = (
            df[df.trial_rewarded == 1].groupby(["dataset", "aperture"]).trial.nunique()
            / df.groupby(["dataset", "aperture"]).trial.nunique()
        )
        counts = pd.DataFrame(counts.reset_index())
        counts.aperture = counts.aperture.round(2).astype(str)
    else:
        counts = (
            df[df.trial_rewarded == 1].groupby(["dataset"]).trial.nunique()
            / df.groupby(["dataset"]).trial.nunique()
        )
        counts = pd.DataFrame(counts.reset_index())
    counts = counts.rename(columns={"trial": "count"})

    _plot_bar_counts(
        counts=counts,
        label_x="aperture" if per_aperture else None,
        per_day=per_day,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    if per_aperture:
        plt.hlines(
            xmin=-0.25,
            xmax=len(df.aperture.unique()) - 0.75,
            y=0.7,
            color="purple",
            linestyles="dashed",
        )
        stats = pd.DataFrame(
            zip(
                counts.groupby("aperture")["count"].mean(),
                counts.groupby("aperture")["count"].sem(),
            ),
            columns=["mean", "sem"],
            index=counts.groupby("aperture")["count"].mean().index,
        )
    else:
        stats = (
            counts["count"].mean(),
            counts["count"].sem(),
        )
        plt.hlines(xmin=-0.5, xmax=0.5, y=0.7, color="purple", linestyles="dashed")

    print(stats)


def plot_time_to_reward(
    df,
    ax: Optional[matplotlib.axes.Axes] = None,
    alpha: float = 0.5,
    cmap: str = "Set1",
):
    """Plot the time to reward per session.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """

    def _time_to_reward_box(group):
        first_event_index = group[
            (group["mouse_in_left"] == 1) | (group["mouse_in_right"] == 1)
        ].index
        if len(first_event_index) > 0:
            return group.loc[first_event_index[0], "trial_step"]
        else:
            return None

    counts = (
        df.groupby(["dataset", "trial"])
        .apply(_time_to_reward_box)
        .reset_index(name="step_to_reward")
    )
    counts = counts.merge(
        df[["dataset", "trial", "trial_rewarded"]].drop_duplicates(),
        on=["dataset", "trial"],
    )
    counts = counts.dropna()

    counts["count"] = counts["step_to_reward"] * 0.02
    counts["trial_rewarded"] = counts["trial_rewarded"].astype(str)
    counts = counts.groupby(["dataset", "trial_rewarded"], as_index=False)[
        "count"
    ].mean()

    _plot_bar_counts(
        counts=counts,
        label_x="trial_rewarded",
        per_day=False,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    plt.ylabel("Time to report (s)")
    plt.xlabel("")
    plt.xticks([0, 1], ["Uncorrect", "Correct"])


def plot_decision_point(df, label_parameter, ax: Optional[matplotlib.axes.Axes] = None):
    """Plot the decision point based on a specified label parameter.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_parameter (str): Column label for the parameter to plot.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
    """
    counts = df.groupby(["session", "aperture"], as_index=False).mean(
        numeric_only=True
    )  # one value per session per aperture

    counts["count"] = np.abs(counts[label_parameter] - 27)
    counts = pd.DataFrame(counts.reset_index())
    counts.aperture = counts.aperture.round(2).astype(str)

    _plot_bar_counts(
        counts=counts,
        label_x="aperture",
        per_day=False,
        alpha=0.2,
        ax=ax,
        cmap="Set1",
    )

    ax.set_ylim(0, 25)
    ax.invert_xaxis()
    ax.set_ylabel("Distance to screen (cm)")

    for i in counts.aperture.unique():
        for j in counts.aperture.unique():
            if i < j:
                stat = stats.ttest_rel(
                    counts[counts["aperture"] == i][label_parameter],
                    counts[counts["aperture"] == j][label_parameter],
                )
                print(f"{i}-{j}: {stat}")


### TORTUOSITY / DURATION


def _plot_distribution(
    df: pd.DataFrame,
    param: str,
    log_scale: bool = True,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
    bins: int = 100,
):
    """Plot a histogram distribution of a parameter with optional log scale.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        param (str): The parameter to plot the distribution for.
        log_scale (bool, optional): If True, use log scale for the x-axis. Default is True.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
        bins (int, optional): Number of bins for the histogram. Default is 100.
    """
    sns.histplot(
        data=df.groupby(["session", "trial"]).first(),
        x=param,
        kde=True,
        palette=cmap,
        ax=ax,
        hue="aperture",
        element="bars",
        multiple="stack",
        stat="probability",
        bins=bins,
        log_scale=log_scale,
    )


def plot_tortuosity_duration_distribution(
    df: pd.DataFrame,
    log_scale: bool = True,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
    bins: int = 100,
):
    """Plot the distribution of trial tortuosity and duration.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        log_scale (bool, optional): If True, use log scale for the x-axis. Default is True.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
        bins (int, optional): Number of bins for the histogram. Default is 100.
    """
    if ax is None:  # TODO(celia): add tests
        fig, ax = plt.subplots(1, 2, figsize=(15, 5))

    _plot_distribution(
        df,
        param="trial_tortuosity",
        log_scale=log_scale,
        ax=ax[0],
        cmap=cmap,
        bins=bins,
    )
    ax[0].set_ylabel("Probability")

    _plot_distribution(
        df, param="trial_duration", log_scale=log_scale, ax=ax[1], cmap=cmap, bins=bins
    )
    ax[1].set_ylabel("Probability")

    fig.tight_layout(pad=2.0)


### PARAMETERS IN TRAJECTORY


def _plot_parameter_on_trial_traj(
    trial,
    vrange: Tuple[int],
    label_parameter: str,
    label_x: str = "x",
    label_y: str = "y",
    cmap: str = "magma",
    alpha: float = 0.4,
    ax: Optional[matplotlib.axes.Axes] = None,
):
    """Plot a parameter on a single trial trajectory.

    Args:
        trial (pd.DataFrame): DataFrame containing the trial data.
        vrange (Tuple[int]): Tuple specifying the range for the parameter values.
        label_parameter (str): Column label for the parameter to plot.
        label_x (str, optional): Column label for the x-axis data. Default is "x".
        label_y (str, optional): Column label for the y-axis data. Default is "y".
        cmap (str, optional): Color map for the plot. Default is "magma".
        alpha (float, optional): Alpha transparency for the plot. Default is 0.4.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None."""
    trial = trial.reset_index(drop=True)
    points = np.array([trial[label_x], trial[label_y]]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    lc = matplotlib.collections.LineCollection(
        segments,
        cmap=cmap,
        alpha=alpha,
    )
    lc.set_norm(plt.Normalize(vmin=vrange[0], vmax=vrange[1]))
    lc.set_array(trial[label_parameter])
    lc.set_linewidth(1)

    ax.add_collection(lc)
    ax.autoscale()
    ax.margins(0.1)


def plot_parameter_on_session_traj(
    df: pd.DataFrame,
    vrange: Tuple[int],
    label_parameter: str,
    per_aperture: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    cmap: str = "magma",
    alpha: float = 0.4,
    ax: Optional[matplotlib.axes.Axes] = None,
):
    """Plot a parameter on session trajectories.

    Args:
        df (pd.DataFrame): DataFrame containing the session data to plot.
        vrange (Tuple[int]): Tuple specifying the range for the parameter values.
        label_parameter (str): Column label for the parameter to plot.
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        label_x (str, optional): Column label for the x-axis data. Default is "x".
        label_y (str, optional): Column label for the y-axis data. Default is "y".
        cmap (str, optional): Color map for the plot. Default is "magma".
        alpha (float, optional): Alpha transparency for the plot. Default is 0.4.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.

    """

    if len(df.session.unique()) > 1:
        raise ValueError(
            f"Only one session should be provided, {len(df.session.unique())} were provided."
        )

    for _, trial in df.groupby(["trial"]):
        _plot_parameter_on_trial_traj(
            trial, vrange, label_parameter, label_x, label_y, cmap, alpha, ax
        )


### INIT POSITION


def plot_init_position_histogram(
    df: pd.DataFrame,
    df_box: pd.DataFrame,
    ax: Optional[matplotlib.axes.Axes] = None,
    bins=3,
    cmap="magma",
    vmax=10,
    is_colorbar: bool = True,
    is_density: bool = False,
):
    """
    Plots a 2D histogram of initial trial positions within a specified box range.

    Args:
        df : pandas.DataFrame
            DataFrame containing the trial data with columns 'session', 'trial', 'trial_init_x', and 'trial_init_y'.
            The DataFrame should contain data from only one session.

        df_box : pandas.DataFrame
            DataFrame containing the boundary values for the box.

        ax : matplotlib.axes.Axes
            The matplotlib axes on which to plot the histogram.

        bins : int, optional
            The number of bins for the histogram along each dimension (default is 3).

        cmap : str, optional
            The colormap used for the histogram (default is "magma").

        vmax : int, optional
            The maximum value for the color scale. Values above this will be clipped to vmax (default is 10).

    """
    if len(df.dataset.unique()) > 1:
        raise ValueError(
            f"Only one session should be provided, {len(df.session.unique())} were provided."
        )

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))

    hist, xedges, yedges, img = ax.hist2d(
        df.groupby(["trial"]).first().trial_init_x,
        df.groupby(["trial"]).first().trial_init_y,
        bins=bins,
        cmap=cmap,
        range=[
            (df_box["tt_box_x_min"].iloc[0], df_box["tt_box_x_max"].iloc[0]),
            (df_box["tt_box_z_min"].iloc[0], df_box["tt_box_z_max"].iloc[0]),
        ],  # range of the box
        vmax=vmax,
        density=is_density,
    )

    if is_colorbar:
        cbar = plt.colorbar(img, ax=ax)

    return hist


### CLUSTERING
def plot_clustering(
    df: pd.DataFrame,
    embedding: npt.NDArray,
    colors=["Set1", "cool", "cool", "viridis", "Set1"],
    axes_labels=[
        "trial_L_choice",
        "trial_init_x",
        "trial_init_y",
        "trial_tortuosity",
        "aperture",
    ],
    method_name="PC",
):
    """Plot the results of the clustering used to compute standard_embedding and color per labels.

    Args:
        embedding: the latent components computed with the dimensionality reduction
            algorithm of the users choice (see in `clustering.py`).
        colors: List of colormap, associated to each labels.
        axes_labels: List of names of each labels.

    Returns:
        The figure with `len(labels)` axes.
    """
    # Compute labels
    labels = []
    for label in axes_labels:
        labels.append(df.groupby(["session", "trial"])[label].apply("first").values)

    # Create the figure
    fig, axes = plt.subplots(1, len(labels), figsize=(int(5 * len(labels)), 5))
    axes = axes.flatten()

    for i in range(len(labels)):
        scatter = axes[i].scatter(
            embedding[:, 0], embedding[:, 1], c=labels[i], s=0.3, cmap=colors[i]
        )

        axes[i].set_title(axes_labels[i])
        axes[i].set_xlabel(f"{method_name}1")
        axes[i].set_ylabel(f"{method_name}2")

        # Add a colorbar
        if not axes_labels[i] in ["trial_L_choice", "aperture"]:
            cbar = plt.colorbar(scatter, ax=axes[i])
            # cbar.set_label(axes_labels[i])

    plt.tight_layout(pad=1.5)


### DECISION POINT


def plot_decision_points_on_trajectory(
    df,
    df_box,
    decision_point=None,
    color="deeppink",
    trials=list(range(25, 30)),
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap="PuOr",
):
    """

    Example:
    ```
    fig = plt.figure(figsize = (15,15), constrained_layout=True)
    gs = plt.GridSpec(3, 5, figure=fig)
    ax = fig.add_subplot(gs[:2, :])

    colors=["red", "blue", "green", "purple", "orange"]

    for i, thr in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
        print("-->", thr)
        ax2 = fig.add_subplot(gs[2, i])
        decision_point = df.groupby(["session", "trial"], as_index=False).apply(lambda x: regression.find_decision_point_per_trial(x, thr))
        regression.plot_decision_points_on_trajectory(df, df_box, decision_point, color=colors[i], ax=ax, trials=list(range(10, 20)))
        regression.pair_plot(decision_point, ax=ax2)

    plt.savefig("figure.svg")
    ```

    """
    if ax is None:
        fig = plt.figure(figsize=(8, 7), constrained_layout=True)
        gs = plt.GridSpec(1, 1, figure=fig)
        ax = fig.add_subplot(gs[0, 0])

    plot_all_boxes(ax=ax, df_box=df_box)
    ax.set_xlim(-27, 27)
    ax.set_ylim(-27, 27)

    for idx_trial, trial in df.groupby("trial"):
        if idx_trial in trials:
            trial = trial.reset_index(drop=True)
            _plot_parameter_on_trial_traj(
                trial, (0, 1), "proba_left", "x", "y", "PuOr", 1, ax
            )

            if decision_point is not None:
                mpl.rcParams["lines.markersize"] = 10
                ax.scatter(
                    decision_point[decision_point["trial"] == idx_trial]["x"],
                    decision_point[decision_point["trial"] == idx_trial]["y"],
                    color=color,
                )

            ax.legend([], [], frameon=False)
        else:
            continue


### DEPRECATED (from analysis)


def _plot_rewards(rewarded, ax):  # NOTE(celia): deprecated, replace by plot_rewards()
    """
    Plots the mean reward and the mean reward rate for each of the target locations.
    Args:
        rewarded (pandas.DataFrame): The DataFrame containing the data to be plotted (df["rewarded"])
        ax (list): A list of three axes to be used for the subplots.
    Returns:
        None
    """

    ax[0].bar("reward", np.mean(rewarded.reward), color="#284553")
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

    ax[2].bar(rewarded.trial, rewarded.reward, color="grey")

    # PLOT
    ax[2].plot(
        rewarded.reward.rolling(
            15, min_periods=1, win_type="gaussian", center=True
        ).mean(std=3),
        color="#B52916",
        linewidth=3,
    )
    ax[2].set_ylabel("Rewarded")


def _plot_choices(
    choices, ax
):  # NOTE(celia): deprecated, replaced by plot_trial_counts()
    """
    Plots mean choices and mean target location for each trial.
    Args:
        choices: A DataFrame containing choice information (df["choices"])
        ax: A numpy array of axis objects to plot on.
    Returns:
        None
    """

    ax[0].bar("P(Left)", np.mean(choices.mouse_in_L), color="#284553")
    ax[0].set_ylim(0, 1)
    ax[0].set_xlim(-1, 1)
    ax[0].set_title("Choices")
    ax[0].set_ylabel("Prob.")
    ax[1].bar("P(Left)", np.mean(choices.object_on_left), color="#284553")
    ax[1].set_ylim(0, 1)
    ax[1].set_xlim(-1, 1)
    ax[1].set_title("Target location")
    ax[1].set_ylabel("Prob.")


def _time_to_rewards(df):  # NOTE(celia): deprecated, replaced by plot_time_to_rewards()
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
        df[(df.mouse_in_R == 1.0) | (df.mouse_in_L == 1.0)]
        .groupby("trial", as_index=False)
        .first()
    )
    box_entries["rewarded"] = df.groupby(["trial"], as_index=False).max()["reward"]

    return box_entries


def _plot_heading_direction(
    df, ax
):  # NOTE(celia): deprecated, replaced by a simple sns.lineplot (see figures_analysis)
    """
    Plots the interpolated heading direction of the mouse.
    [no DJ]
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


def _plot_trial_velocities(
    df, ax
):  # NOTE(celia): deprecated, replaced by a simple sns.lineplot (see figures_analysis)
    """
    Plots the interpolated velocity for each trial.
    [no DJ]
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


def _plot_all_trajectories(
    df, box_df, ax
):  # NOTE(celia): deprecated, replaced by plot_session()
    """
    Plot all the trajectories.
    Args:
        df (pandas.DataFrame): DataFrame containing the data to plot.
        box_df (pandas.DataFrame): DataFrame containing the box data to plot.
        ax (matplotlib.axes._subplots.AxesSubplot): Axes object to plot the data onto.
    Returns:
        None
    """
    for i in range(1, np.max(df.trial)):
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
    plot_all_boxes(box_df=box_df, ax=ax)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)
    ax.set_xlabel("X pos (cm)")
    ax.set_ylabel("Y pos (cm)")


def _plot_rewarded_trial_trajectories(
    df, box_df, ax
):  # NOTE(celia): deprecated, replaced by plot_session() and specific data
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

    rewarded = df.groupby(["trial"], as_index=False).max()

    RR = df[
        (df.trial.isin(rewarded.trial[rewarded.reward == 1.0]))
        & (df.trial.isin(rewarded.trial[rewarded.object_on_left == 0.0]))
    ]
    LR = df[
        (df.trial.isin(rewarded.trial[rewarded.reward == 1.0]))
        & (df.trial.isin(rewarded.trial[rewarded.object_on_left == 1.0]))
    ]

    _plot_all_trajectories(RR, box_df, ax=ax[0])
    _plot_all_trajectories(LR, box_df, ax=ax[1])

    ax[0].set_title("Right rewarded")
    plot_all_boxes(box_df=box_df, ax=ax[0])

    ax[1].set_title("Left rewarded")
    plot_all_boxes(box_df=box_df, ax=ax[1])

    ax[0].set_xlim(-28, 28)
    ax[0].set_ylim(-28, 28)

    ax[1].set_xlim(-28, 28)
    ax[1].set_ylim(-28, 28)


def _plot_choices_by_trial(
    df, ax
):  # NOTE(celia): deprecated, replaced by plot_trial_count()
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
    last = df.groupby(["trial"], as_index=False).last()
    # ax.bar(rewarded.trial, rewarded.object_on_left,)
    # PLOT
    ax.plot(
        last.trial,
        last.mouse_in_L.rolling(
            10, center=True, win_type="gaussian", min_periods=1
        ).mean(std=5),
        c="black",
        linewidth=3,
    )
    ax.scatter(last.trial, last.mouse_in_L, c="black", alpha=0.3)
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.mouse_in_L == 1.0)],
        rewarded.mouse_in_L[(rewarded.reward == 1.0) & rewarded.mouse_in_L == 1.0],
        c="#5C0A72",
    )
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.mouse_in_R == 1.0)],
        rewarded.mouse_in_L[(rewarded.reward == 1.0) & rewarded.mouse_in_R == 1.0],
        c="#FD672C",
    )
    ax.set_xlabel("Trials")
    ax.set_ylabel("Choice (1 = Left)")


def interpolate_trials_cubic_spline(
    df, num_points, column_trial="trial", column_velocity="velocity"
):  # NOTE(celia): deprecated, replaced by utils.interpolate(), this was actually wrong (we integrate with time now)
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
            np.max(df.mouse_in_R[group.index]), len(interpolated_velocity)
        )
        L_choice = np.repeat(
            np.max(df.mouse_in_L[group.index]), len(interpolated_velocity)
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
        interpolated_df = interpolated_df.append(
            interpolated_trial_df, ignore_index=True
        )

    return interpolated_df
