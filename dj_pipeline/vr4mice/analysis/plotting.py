from typing import List, Optional, Tuple

import matplotlib as mpl
import matplotlib.collections
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D  # For custom legend handles
import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.stats as stats
import seaborn as sns
from matplotlib.collections import PathCollection
from matplotlib.transforms import Affine2D
from scipy.interpolate import CubicSpline
from scipy.stats import ttest_rel, ttest_ind

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
colors_multi_aperture = ["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"]
colors_aperture_pale = ["#EC8788", "#96B9D6"]
colors_labs = ["#FF7F0E", "#2CA02C", "#1F77B4"] # sorted: cris, mathis, tolias 
#NOTE(celia): to adapt if we put Niell instead of Cris back
colors_rewarded = ["black", "red"]


def _create_axes(
    ax: Optional[matplotlib.axes.Axes], per_aperture: bool, num_aperture: int
):
    """Create axes.

    Create `num_aperture` axes if `per_aperture` is `True` else creates a single
    axis for the figure.

    Args:
        ax: Axis of the figure. If `None`, this creates the axes based on the
        other parameters, else checks that this is valid.
        per_aperture: If `True`, the function creates `num_aperture` axes.
        num_aperture: Number of apertures presented to the mouse in the
        session.

    Returns:
        The axis, either passed to the function or created in the function.

    """
    if ax is None:
        if per_aperture:
            fig, ax = plt.subplots(1, num_aperture, figsize=(int(num_aperture * 5), 5))
        else:
            fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        fig.tight_layout(pad=0.1)
    else:
        if (
            per_aperture
            and num_aperture > 1
            and (isinstance(ax, matplotlib.axes.Axes) or len(ax) < num_aperture)
        ):
            raise ValueError(
                f"ax should contain one axis per aperture, got {len(ax)}, expect {num_aperture}."
            )
        elif not isinstance(ax, matplotlib.axes.Axes):
            raise ValueError(f"ax should contain one axis, got {len(ax)}.")
    return ax


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
    box_df: pd.DataFrame,
    box_label: str,
    edgecolor: str = "#009B9E",
    fill: bool = False,
    alpha: float = 0.6,
    linewidth: int = 4,
    coords: bool = False,
):
    """Create a matplotlib Rectangle patch for a specified box.

    Args:
        box_df (pd.DataFrame): DataFrame containing the box coordinates.
        box_label (str): Prefix of the columns representing the box dimensions.
        edgecolor (str, optional): Color of the box edge. Default is "#009B9E".
        fill (bool, optional): Whether to fill the box. Default is False.
        alpha (float, optional): Alpha transparency for the box. Default is 0.6.
        linewidth (int, optional): Width of the box edge line. Default is 4.

    Returns:
        matplotlib.patches.Rectangle: The rectangle patch representing the box.

    """

    box_x_min = box_df[f"{box_label}_box_x_min"].iloc[0]
    box_z_min = box_df[f"{box_label}_box_z_min"].iloc[0]
    box_x_max = box_df[f"{box_label}_box_x_max"].iloc[0]
    box_z_max = box_df[f"{box_label}_box_z_max"].iloc[0]

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


def plot_all_boxes(ax, box_df: pd.DataFrame):
    """Plot boxes on trajectory plots.

    Args:
        ax (matplotlib.axes.Axes): A matplotlib Axes object to plot the boxes on.
        box_df (pd.DataFrame): A pandas DataFrame containing the box information.
            Must have columns "<box_label>_box_x_min", "<box_label>_box_x_max",
            "<box_label>_box_z_min", and "<box_label>_box_z_max" for each box label
            ("tt", "left", "right").
    """
    start_box = plot_box_rectangle(box_df, box_label="tt", edgecolor="#009B9E")
    left_box = plot_box_rectangle(box_df, box_label="l", edgecolor="#5C0A72")
    right_box = plot_box_rectangle(box_df, box_label="r", edgecolor="#FD672C")

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
    box_df: pd.DataFrame,
    ax,
    per_side: bool = False,
    label_x: str = "x",
    label_y: str = "y",
    scatter_reward: bool = True,
):
    """Plot a session in the arena including trajectories and boxes.

    Args:
        df (pandas.DataFrame): DataFrame containing the trajectory data to plot.
        box_df (pandas.DataFrame): DataFrame containing the box data to plot.
        ax (matplotlib.axes.Axes): Axes object to plot the data onto.
        per_side (bool, optional): If True, plot trajectories separately based on
            'trial_L_choice'. Default is False.
        label_x (str, optional): Column name for the x-axis data. Default is "x".
        label_y (str, optional): Column name for the y-axis data. Default is "y".
        scatter_reward (bool, optional): If True, scatter plot the reward points. Default is True.

    """

    plot_all_boxes(ax, box_df)
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
    box_df: pd.DataFrame,
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

        box_df : pandas.DataFrame
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

    if len(df.dataset.unique()) > 1:
        raise ValueError(
            f"Only one dataset should be provided, {len(df.dataset.unique())} were provided."
        )
    num_aperture = len(df.aperture.unique())

    ax = _create_axes(ax=ax, per_aperture=per_aperture, num_aperture=num_aperture)

    if per_aperture:
        if num_aperture > 1:
            for j, aperture in enumerate(np.sort(df.aperture.unique())):
                data = df[df.aperture == aperture]
                _plot_session_in_arena(
                    df=data,
                    box_df=box_df,
                    ax=ax[j],
                    per_side=per_side,
                    label_x=label_x,
                    label_y=label_y,
                    scatter_reward=scatter_reward,
                )
                ax[j].set_title(f"{df.dataset.unique()[0]}_{aperture}")
        else:
            _plot_session_in_arena(
                df=df,
                box_df=box_df,
                ax=ax,
                per_side=per_side,
                label_x=label_x,
                label_y=label_y,
                scatter_reward=scatter_reward,
            )
    else:
        _plot_session_in_arena(
            df=df,
            box_df=box_df,
            ax=ax,
            per_side=per_side,
            label_x=label_x,
            label_y=label_y,
            scatter_reward=scatter_reward,
        )
        ax.set_title(f"{df.dataset.unique()[0]}")

    return ax


#### Trial counts


def _plot_bar_counts(
    counts: pd.DataFrame,
    cmap: str,
    label_x: str = None,
    per_mouse: bool = False,
    per_lab: bool = False,
    alpha: float = 0.3,
    ax: Optional[matplotlib.axes.Axes] = None,
):
    """Plot bar or line counts with optional color mapping.

    Args:
        counts (pd.DataFrame): DataFrame containing count data to plot.
        label_x (str, optional): Column label for the x-axis. Default is None.
        cmap (str): Color map for the plot.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
    """

    if label_x is None:
        label_x = [str(1) for i in range(len(counts))]
        figsize = (2, 5)
        color_map = cmap
    else:
        if label_x == "aperture":
            unique_labels = (
                counts[label_x].astype(float).sort_values().astype(str).unique()
            )
        else:
            unique_labels = counts[label_x].sort_values().unique()
        
        figsize = (int(2 * len(unique_labels)), 5)
        cmap = sns.color_palette(cmap, len(unique_labels))
        color_map = {label: cmap[i] for i, label in enumerate(unique_labels)}

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

    if isinstance(label_x, str):
        sns.lineplot(
            data=counts,
            x=label_x,
            y="count",
            hue="mouse_name" if per_mouse else "lab_id" if per_lab else None,
            alpha=0.7 if per_mouse else 1,
            color="black",
            errorbar="se",
            #palette=["grey"] * counts["mouse_name"].nunique() if per_mouse else ["grey"] * counts["lab_id"].nunique() if per_lab else None,
            palette=["grey"] * counts["mouse_name"].nunique() if per_mouse else colors_labs if per_lab else None,
            err_style=None if per_mouse or per_lab else "bars",
            linewidth=1 if per_mouse else 2,
            zorder=3,
            ax=ax,
        )  # mean lines per mouse or overall

        if per_mouse:
            sns.scatterplot(
                data=counts.groupby(["aperture", "mouse_name"], as_index=False)[
                    "count"
                ].mean(),
                x=label_x,
                y="count",
                alpha=0.7,
                palette=color_map,
                zorder=4,
                hue=label_x,
                ax=ax,
                s=50,
            )  # per mouse scatter

        else:
            sns.lineplot(
                data=counts,
                x=label_x,
                y="count",
                hue="dataset",
                errorbar=None,
                alpha=alpha,
                color="grey",
                palette=["grey"] * counts["dataset"].nunique(),
                markers="o",
                linewidth=0.5,
                ax=ax,
                legend=False,
            )  # individual lines

        if per_lab:
            sns.scatterplot(
                data=counts.groupby(["aperture", "lab_id"], as_index=False)[
                    "count"
                ].mean(),
                x=label_x,
                y="count",
                alpha=0.7,
                palette=colors_labs,
                zorder=4,
                hue="lab_id",
                ax=ax,
                s=50,
            )  # per mouse scatter

    else:
        sns.barplot(
            data=counts,
            x=label_x,
            y="count",
            hue="mouse_name" if per_mouse else "lab_id" if per_lab else None,
            color="grey",
            errorbar="se",
            alpha=1,
            ax=ax,
            legend=False,
        )
        ax.set_xlabel("")
        ax.set_xticklabels([])

    sns.scatterplot(
        data=counts,
        x=label_x,
        y="count",
        alpha=alpha if per_mouse or per_lab else 1,
        hue=label_x,
        palette=["grey"] * len(counts["count"]) if per_mouse or per_lab else color_map,
        s=25 if per_mouse or per_lab else 50,
        ax=ax,
        legend=False,
        zorder=2,
    )

    if per_mouse:
        # Compute means and standard errors
        grouped_counts = counts.groupby([label_x, "mouse_name"], as_index=False)[
            "count"
        ].mean()
        means = grouped_counts.groupby(label_x)["count"].mean()
        errors = grouped_counts.groupby(label_x)["count"].sem()

        # Plot the mean line without error bars
        sns.lineplot(
            data=grouped_counts,
            x=label_x,
            y="count",
            errorbar=None,  # Disable seaborn error bars
            alpha=1,
            color="black",
            linewidth=1.5,
            ax=ax,
            legend=False,
            zorder=50,  # Mean line zorder
        )

        # Manually add error bars on top
        ax.errorbar(
            x=means.index,
            y=means,
            yerr=errors,
            fmt="none",  # No connecting line, only error bars
            ecolor="black",
            elinewidth=1.5,
            # capsize=4,
            # capthick=1.5,
            zorder=100,  # Set very high to ensure it's on top
        )


    if per_lab:
        # Compute means and standard errors
        grouped_counts = counts.groupby([label_x, "lab_id"], as_index=False)[
            "count"
        ].mean()
        means = grouped_counts.groupby(label_x)["count"].mean()
        errors = grouped_counts.groupby(label_x)["count"].sem()

        # Plot the mean line without error bars
        sns.lineplot(
            data=grouped_counts,
            x=label_x,
            y="count",
            errorbar=None,  # Disable seaborn error bars
            alpha=1,
            color="black",
            linewidth=1.5,
            ax=ax,
            legend=False,
            zorder=50,  # Mean line zorder
        )

        # Manually add error bars on top
        ax.errorbar(
            x=means.index,
            y=means,
            yerr=errors,
            fmt="none",  # No connecting line, only error bars
            ecolor="black",
            elinewidth=1.5,
            # capsize=4,
            # capthick=1.5,
            zorder=100,  # Set very high to ensure it's on top
        )


    if not per_mouse:
        ax.legend([], [], frameon=False)


def plot_trial_count(
    df,  # TODO(celia): provide correct columns directly?
    per_aperture: bool = False,
    alpha: float = 0.5,
    per_mouse: bool = False,
    per_lab: bool = False,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot the count of trials per session or per aperture.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """

    num_aperture = len(df.aperture.unique())
    ax = _create_axes(ax=ax, per_aperture=per_aperture, num_aperture=1)

    group_cols = ["dataset"]

    if per_aperture:
        group_cols.append("aperture")
        
    if per_mouse and per_lab:
        raise ValueError(
            "Cannot plot per mouse and per lab at the same time, please choose one.")

    if per_mouse:
        group_cols.append("mouse_name")
    elif per_lab:
        group_cols.append("lab_id")


    if per_aperture:
        counts = (
            df.groupby(group_cols + ["trial"])
            .aperture.first()
            .groupby(level="dataset")
            .value_counts()
            .sort_values()
        ).reset_index(name="count")
        counts = pd.DataFrame(counts)
        counts.sort_values(by="aperture", inplace=True)
        counts["aperture"] = counts.aperture.round(2).astype(str)
    else:
        counts = df.groupby(group_cols).trial.nunique()
        counts = pd.DataFrame(counts.reset_index())
        counts = counts.rename(columns={"trial": "count"})

    _plot_bar_counts(
        counts=counts,
        label_x="aperture" if per_aperture else None,
        per_lab=per_lab,
        per_mouse=per_mouse,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    ax.set_ylabel("#Trials / session")
    ax.set_xlim(-0.5, num_aperture - 0.5)

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
    # print(stats)


def plot_rate(
    df,  # TODO(celia): provide correct columns directly?
    label_x: str,
    per_aperture: bool = False,
    per_mouse: bool = False,
    per_lab: bool = False,
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot the rate for a given `label_x` column per session or per aperture.

    This works specifically for plotting the choice rate, the reward rate,
    the target location rate, the trial count.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_x (str): Name of the column
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """

    num_aperture = len(df.aperture.unique())
    ax = _create_axes(ax=ax, per_aperture=per_aperture, num_aperture=1)

    group_cols = ["dataset"]

    if per_aperture:
        group_cols.append("aperture")
        
    if per_mouse and per_lab:
        raise ValueError(
            "Cannot plot per mouse and per lab at the same time, please choose one.")

    if per_mouse:
        group_cols.append("mouse_name")
    elif per_lab:
        group_cols.append("lab_id")

    counts = (
        df[df[label_x] == 1].groupby(group_cols).trial.nunique()
        / df.groupby(group_cols).trial.nunique()
    )

    if per_aperture:
        if per_lab: 
            counts = pd.DataFrame(counts.reset_index().sort_values(by=["aperture", "lab_id"]))
        else: 
            counts = pd.DataFrame(counts.reset_index().sort_values(by="aperture"))
        counts.aperture = counts.aperture.round(2).astype(str)
    else:
        if per_lab: 
            counts = pd.DataFrame(counts.reset_index().sort_values(by="lab_id"))
        else: 
            counts = pd.DataFrame(counts.reset_index())
    counts = counts.rename(columns={"trial": "count"})

    _plot_bar_counts(
        counts=counts,
        label_x="aperture" if per_aperture else None,
        per_lab=per_lab,
        alpha=alpha,
        per_mouse=per_mouse,
        ax=ax,
        cmap=cmap,
    )

    ax.set_xlim(-0.5, num_aperture - 0.5)

    if per_aperture:
        stats = pd.DataFrame(
            zip(
                counts.groupby("aperture")["count"].mean(),
                counts.groupby("aperture")["count"].sem(),
            ),
            columns=["mean", "sem"],
            index=counts.groupby("aperture")["count"].mean().index,
        )
        for i in counts.aperture.unique():
            for j in counts.aperture.unique():
                if i < j:
                    stat = ttest_rel(
                        counts[counts["aperture"] == i]["count"],
                        counts[counts["aperture"] == j]["count"],
                    )
                    print(f"{i}-{j}: {stat}")

    else:
        stats = (counts["count"].mean(), counts["count"].sem())

    print(stats)


def plot_rewards(
    df,  # TODO(celia): provide correct columns directly?
    per_aperture: bool = False,
    per_lab: bool = False,
    per_mouse: bool = False,
    alpha: float = 0.5,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
):
    """Plot the success rate per session or per aperture.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
    """
    num_aperture = len(df.aperture.unique())
    ax = _create_axes(ax=ax, per_aperture=per_aperture, num_aperture=1)

    group_cols = ["dataset"]

    if per_aperture:
        group_cols.append("aperture")

    if per_mouse:
        group_cols.append("mouse_name")

    # Calculate success rate
    counts = (
        df[df.trial_rewarded == 1].groupby(group_cols).trial.nunique()
        / df.groupby(group_cols).trial.nunique()
    )
    counts = pd.DataFrame(counts.reset_index())

    # If per_aperture, ensure aperture is formatted correctly
    if per_aperture:
        counts.aperture = counts.aperture.round(2).astype(str)

    counts = counts.rename(columns={"trial": "count"})
    
    _plot_bar_counts(
        counts=counts,
        label_x="aperture" if per_aperture else None,
        per_lab=per_lab,
        per_mouse=per_mouse,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    ax.set_ylim([0, 1])
    ax.set_xlim(-0.5, num_aperture - 0.5)
    ax.set_ylabel("Success rate")

    if per_aperture:
        ax.hlines(
            xmin=-0.25,
            xmax=num_aperture - 0.75,
            y=0.7,
            color="purple",
            linestyles="dashed",
        )
        stats = pd.DataFrame(
            zip(
                counts.groupby("aperture")["count"].mean(),
                counts.groupby("aperture")["count"].std(),
            ),
            columns=["mean", "sem"],
            index=counts.groupby("aperture")["count"].mean().index,
        )
    else:
        stats = (counts["count"].mean(), counts["count"].std())
        ax.hlines(xmin=-0.5, xmax=0.5, y=0.7, color="purple", linestyles="dashed")
    return counts


def plot_time_to_reward(
    df,
    label_x: str,
    xticks: List[str],
    ax: Optional[matplotlib.axes.Axes] = None,
    alpha: float = 0.5,
    cmap: Optional[str] = None,
    log_scale: bool = True,
):
    """Plot the time to reward per session.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_x (str): Name of the column to use to group the time to rewards.
        xticks (List[str]): List of x labels corresponding to the groups used to group the time
            to rewards. Note that they should be orderded as the user want them to appear on the scheme.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        cmap (str, optional): Color map for the plot.
        log_scale (bool): If True, the time to reward is plotted in log-scale, else
            in normal scale. Default is True.
    """
    ax = _create_axes(ax=ax, per_aperture=False, num_aperture=1)

    if not cmap:
        cmap = (
            colors_aperture
            if label_x == "aperture"
            else colors_rewarded
            if label_x == "trial_rewarded"
            else colors_choice
        )

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
        df[["dataset", "trial", label_x]].drop_duplicates(), on=["dataset", "trial"]
    )
    counts = counts.dropna()

    counts["count"] = counts["step_to_reward"] * 0.02
    if label_x == "aperture":
        counts.aperture = counts.aperture.astype(float)
    counts.sort_values(by=label_x, inplace=True)
    mean_counts = counts.groupby(["dataset", label_x], as_index=False)["count"].mean()

    mean_counts[label_x] = mean_counts[label_x].astype(str)
    _plot_bar_counts(
        counts=mean_counts,
        label_x=label_x,
        alpha=alpha,
        ax=ax,
        cmap=cmap,
    )

    counts[label_x] = counts[label_x].astype(str)
    sns.stripplot(
        data=counts, x=label_x, y="count", palette=cmap, hue=label_x, ax=ax, alpha=0.4
    )

    if log_scale:
        ax.set_yscale("log")
    ax.set_ylabel("Time to report (s)")
    ax.set_xlabel("")
    ax.set_xlim(-0.5, len(list(counts[label_x].unique())) - 0.5)

    ax.set_xticks(np.arange(len(list(counts[label_x].unique()))), xticks)
    ax.legend([], [], frameon=False)


def pairplot_std_decision_point(
    df: pd.DataFrame,
    label_parameter: str,
    ax: Optional[matplotlib.axes.Axes] = None,
    per_mouse: bool = False,
    per_lab: bool = False,
    cmap: str = "Set2",
):
    """Plot the decision point based on a specified label parameter.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_parameter (str): Column label for the parameter to plot.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        per_mouse (bool): TODO
    """
    ax = _create_axes(ax=ax, per_aperture=False, num_aperture=1)

    groupby_cols = ["dataset", "aperture"]

    if per_lab and per_mouse:
        raise ValueError(
            "Cannot plot per mouse and per lab at the same time, please choose one."
        )

    if per_mouse:
        groupby_cols.append("mouse_name")
    elif per_lab:
        groupby_cols.append("lab_id")

    counts = df.groupby(groupby_cols, as_index=False).std()

    counts["count"] = counts[label_parameter]
    counts = pd.DataFrame(counts.reset_index())
    counts.aperture = counts.aperture.round(2).astype(str)

    _plot_bar_counts(
        counts=counts,
        label_x="aperture",
        per_mouse=per_mouse,
        per_lab=per_lab,
        alpha=0.2,
        ax=ax,
        cmap=cmap if per_mouse else colors_aperture,
    )
    ax.invert_xaxis()
    ax.set_ylabel(f"{label_parameter}")

    for i in counts.aperture.unique():
        for j in counts.aperture.unique():
            if i < j:
                stat = stats.ttest_rel(
                    counts[counts["aperture"] == i][label_parameter],
                    counts[counts["aperture"] == j][label_parameter],
                )
                print(f"{i}-{j}: {stat}")


def pairplot_average_decision_point(
    df: pd.DataFrame,
    label_parameter: str,
    ax: Optional[matplotlib.axes.Axes] = None,
    per_mouse: bool = False,
    per_lab: bool = False,
    cmap: str = "Set2",
):
    """Plot the decision point based on a specified label parameter.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_parameter (str): Column label for the parameter to plot.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
    """
    ax = _create_axes(ax=ax, per_aperture=False, num_aperture=1)

    groupby_cols = ["dataset", "aperture"]

    if per_lab and per_mouse:
        raise ValueError(
            "Cannot plot per mouse and per lab at the same time, please choose one."
        )
        
    if per_mouse:
        groupby_cols.append("mouse_name")
    elif per_lab:
        groupby_cols.append("lab_id")
        
    counts = df.groupby(groupby_cols, as_index=False).mean(numeric_only=True)

    if label_parameter == "y":
        counts["count"] = np.abs(counts[label_parameter] - 27)
    elif label_parameter in ["heading_dir", "head_angle", "velocity_x"]:
        counts["count"] = np.abs(counts[label_parameter])
    else:
        counts["count"] = counts[label_parameter]
    #counts = pd.DataFrame(counts.reset_index())
    #counts.aperture = counts.aperture.round(2).astype(str)
    
    
    if per_lab: 
        counts = pd.DataFrame(counts.reset_index().sort_values(by=["aperture", "lab_id"]))
    else: 
        counts = pd.DataFrame(counts.reset_index().sort_values(by="aperture"))
    counts.aperture = counts.aperture.round(2).astype(str)

    

    _plot_bar_counts(
        counts=counts,
        label_x="aperture",
        per_lab=per_lab,
        per_mouse=per_mouse,
        alpha=0.2,
        ax=ax,
        cmap=cmap if per_mouse or per_lab else colors_aperture,
    )
    ax.invert_xaxis()
    if label_parameter == "y":
        ax.set_ylabel(f"Distance to screen (cm)")
    else:
        ax.set_ylabel(f"{label_parameter}")

    if len(counts.aperture.unique()) > 2:
        ax.set_xlabel("Occluder (%)")
    else:
        ax.set_xlabel("Occluder")

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

    data = df.groupby(["dataset", "trial"]).first()

    sns.histplot(
        data=data,
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
    if ax is None:
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
    return ax


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
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
    """
    trial = trial.reset_index(drop=True)
    points = np.array([trial[label_x], trial[label_y]]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)

    lc = matplotlib.collections.LineCollection(
        segments,
        cmap=cmap,
        alpha=alpha,
    )
    # lc.set_norm(plt.Normalize(vmin=vrange[0], vmax=vrange[1]))
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

    if len(df.dataset.unique()) > 1:
        raise ValueError(
            f"Only one dataset should be provided, {len(df.dataset.unique())} were provided."
        )

    for _, trial in df.groupby(["trial"]):
        _plot_parameter_on_trial_traj(
            trial, vrange, label_parameter, label_x, label_y, cmap, alpha, ax
        )


### INIT POSITION


def plot_init_position_histogram(
    df: pd.DataFrame,
    box_df: pd.DataFrame,
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
            DataFrame containing the trial data with columns 'dataset', 'trial', 'trial_init_x', and 'trial_init_y'.
            The DataFrame should contain data from only one dataset.

        box_df : pandas.DataFrame
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
            f"Only one dataset should be provided, {len(df.dataset.unique())} were provided."
        )

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))

    hist, xedges, yedges, img = ax.hist2d(
        df.groupby(["trial"]).first().trial_init_x,
        df.groupby(["trial"]).first().trial_init_y,
        bins=bins,
        cmap=cmap,
        range=[
            (box_df["tt_box_x_min"].iloc[0], box_df["tt_box_x_max"].iloc[0]),
            (box_df["tt_box_z_min"].iloc[0], box_df["tt_box_z_max"].iloc[0]),
        ],  # range of the box
        vmax=vmax,
        density=is_density,
    )

    if is_colorbar:
        cbar = plt.colorbar(img, ax=ax)

    plt.close()

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
        labels.append(df.groupby(["dataset", "trial"])[label].apply("first").values)

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


def plot_rolling_reward(df, ax):

    rewarded = df.groupby("trial")["reward"].max().reset_index()
    ax.bar(rewarded.trial, rewarded.reward, color="grey")

    ax.plot(
        rewarded.reward.rolling(
            15, min_periods=1, win_type="gaussian", center=True
        ).mean(std=3),
        color="#B52916",
        linewidth=3,
    )
    ax.set_ylabel("Rewarded")


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

    ax[0].bar("P(Left)", np.mean(choices.trial_left_choice), color="#284553")
    ax[0].set_ylim(0, 1)
    ax[0].set_xlim(-1, 1)
    ax[0].set_title("Choices")
    ax[0].set_ylabel("Prob.")
    ax[1].bar("P(Left)", np.mean(choices.object_on_left), color="#284553")
    ax[1].set_ylim(0, 1)
    ax[1].set_xlim(-1, 1)
    ax[1].set_title("Target location")
    ax[1].set_ylabel("Prob.")


def _time_to_rewards(df):
    """Calculate the time it takes for the animal to enter the box.

    This is for rewarded vs unrewarded trials and left and right choices.

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


def _plot_time_to_rewards(
    box_entries, ax
):  # NOTE(celia): deprecated, replaced by plot_time_to_rewards()
    """Plot the time it takes for the animal to enter the box.

    This is for rewarded vs unrewarded trials and left and right choices.

    Args:
        box_entries: pandas.DataFrame containing the data df["box_entries"]
        ax: a list of two matplotlib axes to plot the results

    """
    cat1 = box_entries[box_entries["trial_rewarded"] == 1.0]
    cat2 = box_entries[box_entries["trial_rewarded"] == 0.0]

    p_value = stats.ttest_ind(
        np.log(cat1["trial_step_time"]), np.log(cat2["trial_step_time"])
    )[1]

    g = sns.stripplot(
        data=box_entries,
        x="trial_rewarded",
        y="trial_step_time",
        palette=["#284553", "#B52916"],
        hue="trial_rewarded",
        ax=ax[0],
        alpha=0.7,
        legend=False,
        zorder=1,
    )

    sns.pointplot(
        data=box_entries,
        x="trial_rewarded",
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

    box_entries = box_entries[box_entries.trial_rewarded == 1.0]
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

    sns.pointplot(
        data=box_entries,
        x="mouse_in_L",
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


def plot_choices_by_trial(df, ax):
    """Plots choices per trial on a roling window.

    Args:
        df (pandas.DataFrame): The dataframe containing the data.
        ax (matplotlib.axes._subplots.AxesSubplot): The subplot axes.

    """

    df = df.groupby("trial", as_index=False).apply(lambda group: group.iloc[1:, :])
    rewarded = df[df.reward == 1.0]
    last = df.groupby(["trial"], as_index=False).last()

    ax.plot(
        last.trial,
        last.trial_left_choice.rolling(
            10, center=True, win_type="gaussian", min_periods=1
        ).mean(std=5),
        c="black",
        linewidth=3,
    )
    ax.scatter(last.trial, last.trial_left_choice, c="black", alpha=0.3)
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.trial_left_choice == 1.0)],
        rewarded.trial_left_choice[
            (rewarded.reward == 1.0) & rewarded.trial_left_choice == 1.0
        ],
        c=colors_choice[0],
    )
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.trial_right_choice == 1.0)],
        rewarded.trial_left_choice[
            (rewarded.reward == 1.0) & rewarded.trial_right_choice == 1.0
        ],
        c=colors_choice[1],
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
            np.max(df.trial_left_choice[group.index]), len(interpolated_velocity)
        )
        L_choice = np.repeat(
            np.max(df.trial_left_choice[group.index]), len(interpolated_velocity)
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


def plot_training_phases(
    ax, data, y="session_reward", hue=None, ylim=None, ylabel=None, x_label="num_train_stage"
):
    """
    Plot training phases with individual trajectories and group means.

    Parameters:
    -----------
    data : DataFrame
        The dataframe containing the training data
    y_var : str, optional (default="session_reward")
        The variable to plot on the y-axis
    hue_var : str, optional
        The variable to use for coloring the lines/points (e.g., "lab_id")
        If None, all lines will be grey and points will be black
    """

    # Plot individual trajectories
    if hue:
        sns.lineplot(
            data=data,
            x=x_label,
            y=y,
            units="mouse_name",
            hue=hue,
            estimator=None,
            marker="o",
            zorder=0,
            alpha=0.3,
            ax=ax,
            legend=False,
        )
        sns.pointplot(data=data, x=x_label, y=y, hue=hue, capsize=0.1, ax=ax)
    else:
        sns.lineplot(
            data=data,
            x=x_label,
            y=y,
            units="mouse_name",
            estimator=None,
            marker="o",
            color="grey",
            zorder=0,
            alpha=0.3,
            ax=ax,
        )
        sns.pointplot(
            data=data, x=x_label, y=y, color="black", capsize=0.1, ax=ax
        )

    if x_label == "num_train_stage":
        # Set labels and limits
        ax.set_xlabel("Training Phase")
        ax.set_ylabel(ylabel)
        sns.despine(offset=10)

        if ylim:
            ax.set_ylim(0, 1)

        # Define tick positions and labels
        stage_positions = np.arange(6)
        stage_labels = ["First", "Middle", "Last", "First", "Middle", "Last"]
        stage_colors = ["#3FB47C", "#3FB47C", "#1F6F49", "#FF1493", "#FF1493", "#FF1493"]

        ax.set_xticks(stage_positions)
        ax.set_xticklabels(stage_labels, rotation=0, fontsize=12)
        
        # Color the x-tick labels
        for j, label in enumerate(ax.get_xticklabels()):
            label.set_color(stage_colors[j])


    # Add reference lines
    if y == "session_reward":
        ax.axhline(0.5, linestyle="dashed", color="black", alpha=0.5)
        ax.axhline(0.70, linestyle="dashed", color="red", alpha=0.3)


    # Improve legend if hue is used
    # if hue:
    #     ax.legend(
    #         title=hue.replace("_", " ").title(),
    #         bbox_to_anchor=(1.05, 1),
    #         loc="upper left",
    #     )
        
    return ax


def plot_mean_xy_trajectory(
    df, cmap=["red", "blue"], color_by="choice", style_by="aperture"
):
    """
    Plots mean trajectories with flexible assignment of colors and line styles.

    Parameters:
    -----------
    df : DataFrame
        Contains columns: x, y, sem_x, sem_y, aperture, trial_left_choice
    cmap : list or matplotlib colormap
        Color scheme for different choices
    color_by : str ('choice' or 'aperture')
        Which variable to represent with colors
    style_by : str ('choice' or 'aperture')
        Which variable to represent with line styles
    """

    if color_by not in ["choice", "aperture"]:
        raise ValueError("color_by must be either 'choice' or 'aperture'")
    if style_by not in ["choice", "aperture"]:
        raise ValueError("style_by must be either 'choice' or 'aperture'")
    if color_by == style_by:
        raise ValueError("color_by and style_by must represent different variables")

    choices = df.trial_left_choice.unique()
    apertures = df.aperture.unique()

    if color_by == "choice":
        color_var = "trial_left_choice"
        color_values = choices
    else:
        color_var = "aperture"
        color_values = apertures

    if isinstance(cmap, list):
        if len(cmap) < len(color_values):
            raise ValueError(
                f"Need at least {len(color_values)} colors, got {len(cmap)}"
            )
        colors = {val: cmap[i] for i, val in enumerate(color_values)}
    else:
        colors = {
            val: cmap(i / (len(color_values) - 1)) for i, val in enumerate(color_values)
        }

    if style_by == "choice":
        style_var = "trial_left_choice"
        style_values = choices
    else:
        style_var = "aperture"
        style_values = apertures

    line_styles = ["-", "--", ":", "-."]
    styles = {
        val: line_styles[i % len(line_styles)] for i, val in enumerate(style_values)
    }

    fig, ax = plt.subplots(figsize=(5, 5))

    group_vars = [color_var, style_var]
    for (color_val, style_val), data in df.groupby(group_vars):
        color = colors[color_val]
        style = styles[style_val]
        label = f"{color_var.capitalize()} {color_val} | {style_var.capitalize()} {style_val}"

        # Main trajectory
        ax.plot(data.x, data.y, color=color, linestyle=style, label=label, linewidth=2)

        # Error bands
        alpha = 0.15
        ax.fill_betweenx(
            data.y, data.x - data.sem_x, data.x + data.sem_x, color=color, alpha=alpha
        )
        ax.fill_between(
            data.x, data.y - data.sem_y, data.y + data.sem_y, color=color, alpha=alpha
        )

    legend_elements = []

    for val in color_values:
        legend_elements.append(
            Line2D(
                [0],
                [0],
                color=colors[val],
                lw=4,
                label=f"{color_var.capitalize()} {val}",
            )
        )
    for val in style_values:
        legend_elements.append(
            Line2D(
                [0],
                [0],
                color="black",
                linestyle=styles[val],
                lw=2,
                label=f"{style_var.capitalize()} {val}",
            )
        )

    ax.legend(handles=legend_elements, loc="lower right")
    ax.grid(False)
    ax.set_xlim(-18, 18)
    ax.set_ylim(0, 23)
    ax.vlines(x=-15, ymin=2, ymax=7, color="black", linewidth=2)
    ax.hlines(y=2, xmin=-15, xmax=-5, color="black", linewidth=2)
    plt.axis("off")

    return fig, ax
