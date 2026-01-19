from typing import List, Optional, Tuple

import matplotlib as mpl
import matplotlib.collections
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy.stats as stats
import seaborn as sns
from matplotlib.collections import PathCollection
from matplotlib.lines import Line2D  # For custom legend handles
from matplotlib.transforms import Affine2D
from scipy.interpolate import CubicSpline

"""
Color codes:
    - left box: purple: '#5C0A72'
    - right box: orange: '#FD672C'
    - center box: blue: '#009B9E'
    
    - SET1 colormap for the apertures, 
    4.3 = '#E41A1C', 12 = '#437FB5'
"""

colors_choice = ["#5C0A72", "#FD672C"]
colors_aperture = ["#E41A1C", "#437FB5", "#4daf4a", "#984ea3", "#ff7f00"]
colors_multi_aperture = ["#fde725", "#5ec962", "#21918c", "#3b528b", "#440154"]
colors_aperture_pale = ["#EC8788", "#96B9D6"]
colors_labs = ["#FF7F0E", "#2CA02C", "#1F77B4"]  # sorted: cris, mathis, tolias
# NOTE(celia): to adapt if we put Niell instead of Cris back
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


def plot_session_3d(
    df: pd.DataFrame,
    box_df: pd.DataFrame,
    trial_ids: Optional[List[int]] = None,
    ax: Optional[mpl.axes.Axes] = None,
    label_x: str = "x",
    label_y: str = "y",
    color_by_choice: bool = True,
    color_by_aperture: bool = False,
    decision_points: Optional[pd.DataFrame] = None,
):
    """Plot multiple trial trajectories in 3D space with time component.

    Args:
        df: DataFrame containing the trajectory data.
        box_df: DataFrame containing the box data.
        trial_ids: List of specific trials to plot. If None, plots all trials.
        ax: Optional matplotlib 3D axes to plot on.
        label_x: Label for x-axis (default "x").
        label_y: Label for y-axis (default "y").
        color_by_choice: If True, color by left/right choice (purple/orange). Default True.
        color_by_aperture: If True, color by aperture. Takes precedence over color_by_choice. Default False.
        decision_points: Optional DataFrame with columns 'trial', 'x', 'y', 'trial_length'
            indicating decision point coordinates and time for each trial.

    Returns:
        The 3D axes object with the plot.
    """
    if len(df.dataset.unique()) > 1:
        raise ValueError(
            f"Only one dataset should be provided, {len(df.dataset.unique())} were provided."
        )

    # Select specific trials or all trials
    if trial_ids is None:
        trial_ids = sorted(df["trial"].unique())
    elif not isinstance(trial_ids, (list, np.ndarray)):
        trial_ids = [trial_ids]

    if ax is None:
        fig = plt.figure(figsize=(14, 8))
        ax = fig.add_subplot(111, projection="3d")

    # Get max time across all trials for box placement
    # Time will be normalized to 0-1 range
    max_time = 1.0

    # Get box coordinates
    tt_coords = plot_box_rectangle(box_df, box_label="tt", coords=True)
    l_coords = plot_box_rectangle(box_df, box_label="l", coords=True)
    r_coords = plot_box_rectangle(box_df, box_label="r", coords=True)

    # Plot start box (tt) at first timestep (time=0)
    tt_x_min, tt_z_min = tt_coords[0]
    tt_width, tt_height = tt_coords[1], tt_coords[2]

    # Draw start box corners at time=0
    box_corners_time = np.array([0, 0, 0, 0, 0])
    box_x = np.array(
        [tt_x_min, tt_x_min + tt_width, tt_x_min + tt_width, tt_x_min, tt_x_min]
    )
    box_y = np.array(
        [tt_z_min, tt_z_min, tt_z_min + tt_height, tt_z_min + tt_height, tt_z_min]
    )
    ax.plot(
        box_corners_time,
        box_x,
        box_y,
        color="#009B9E",
        linewidth=3,
        label="Start Box (tt)",
    )

    # Plot left box at last timestep
    l_x_min, l_z_min = l_coords[0]
    l_width, l_height = l_coords[1], l_coords[2]

    box_corners_time_last = np.array([max_time, max_time, max_time, max_time, max_time])
    box_x_l = np.array(
        [l_x_min, l_x_min + l_width, l_x_min + l_width, l_x_min, l_x_min]
    )
    box_y_l = np.array(
        [l_z_min, l_z_min, l_z_min + l_height, l_z_min + l_height, l_z_min]
    )
    ax.plot(
        box_corners_time_last,
        box_x_l,
        box_y_l,
        color="#5C0A72",
        linewidth=3,
        label="Left Box (l)",
    )

    # Plot right box at last timestep
    r_x_min, r_z_min = r_coords[0]
    r_width, r_height = r_coords[1], r_coords[2]

    box_x_r = np.array(
        [r_x_min, r_x_min + r_width, r_x_min + r_width, r_x_min, r_x_min]
    )
    box_y_r = np.array(
        [r_z_min, r_z_min, r_z_min + r_height, r_z_min + r_height, r_z_min]
    )
    ax.plot(
        box_corners_time_last,
        box_x_r,
        box_y_r,
        color="#FD672C",
        linewidth=3,
        label="Right Box (r)",
    )

    # Plot each trial
    for trial_id in trial_ids:
        trial_data = df[df["trial"] == trial_id]

        if trial_data.empty:
            continue

        # Extract coordinates
        x = trial_data[label_x].values
        y = trial_data[label_y].values
        time = trial_data.index.values

        # Normalize time to 0-1 range
        time = time - time[0]
        if len(time) > 1 and time[-1] > 0:
            time = time / time[-1]

        # Determine color based on aperture or choice
        if color_by_aperture and "aperture" in trial_data.columns:
            aperture_val = trial_data["aperture"].iloc[0]
            # Get unique apertures and assign colors
            unique_apertures = sorted(df["aperture"].unique())
            aperture_idx = unique_apertures.index(aperture_val)
            color = (
                colors_aperture[aperture_idx]
                if aperture_idx < len(colors_aperture)
                else colors_aperture[0]
            )
            choice_label = f"Aperture {aperture_val:.1f}"
        elif color_by_choice and "trial_left_choice" in trial_data.columns:
            left_choice = trial_data["trial_left_choice"].iloc[0]
            color = colors_choice[0] if left_choice == 1 else colors_choice[1]
            choice_label = "Left" if left_choice == 1 else "Right"
        else:
            color = "gray"
            choice_label = "Unknown"

        # Plot trajectory (time as x-axis, left to right)
        ax.plot(
            time,
            x,
            y,
            color=color,
            linewidth=2,
            alpha=0.7,
            label=f"Trial {trial_id} ({choice_label})",
        )

        # Plot start position
        ax.scatter(
            [time[0]],
            [x[0]],
            [y[0]],
            c=["#2250C8"],
            s=30,
            marker="o",
            alpha=0.8,
            zorder=5,
        )

        # Plot last position
        ax.scatter(
            [time[-1]],
            [x[-1]],
            [y[-1]],
            c=["#B52916"],
            s=30,
            marker="o",
            alpha=0.8,
            zorder=6,
        )

    # Plot decision points if provided
    if decision_points is not None:
        for trial_id in trial_ids:
            trial_decision = decision_points[decision_points["trial"] == trial_id]
            if not trial_decision.empty:
                # Get decision point coordinates
                dec_x = trial_decision["x"].values[0]
                dec_y = trial_decision["y"].values[0]
                dec_time = trial_decision["trial_length"].values[0]
                print("Decision Time:", dec_time)

                # Plot decision point as a larger marker
                ax.scatter(
                    [dec_time],
                    [dec_x],
                    [dec_y],
                    c="deeppink",
                    s=40,
                    marker="o",
                    alpha=1,
                    zorder=10,
                )

    # Labels and formatting
    ax.set_xlabel("Trial progression", labelpad=40)
    ax.set_ylabel(label_x, labelpad=10)
    ax.set_zlabel(label_y, labelpad=10)

    # Set tick labels to only show -20, 0, and 20
    ax.set_yticks([-20, 0, 20])
    ax.set_zticks([-20, 0, 20])

    # Set box aspect ratio to make time axis longer (time, x, y aspect ratios)
    ax.set_box_aspect([4, 1, 1])
    ax.view_init(elev=10, azim=30)

    # Invert time axis
    ax.invert_xaxis()

    # Remove grid
    ax.grid(False)

    ax.set_title(f"{df.dataset.unique()[0]} - {len(trial_ids)} Trials")

    return ax


def _plot_bar_counts(
    counts: pd.DataFrame,
    cmap: str,
    label_x: str = None,
    per_mouse: bool = False,
    per_lab: bool = False,
    alpha: float = 0.3,
    ax: Optional[matplotlib.axes.Axes] = None,
    color_sessions_by_lab: bool = True,
):
    """Plot bar or line counts with optional color mapping.

    Args:
        counts (pd.DataFrame): DataFrame containing count data to plot.
        label_x (str, optional): Column label for the x-axis. Default is None.
        cmap (str): Color map for the plot.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        color_sessions_by_lab (bool, optional): If True and per_lab=True, color individual
            session points by lab color. If False, use grey. Default is True.
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
        # Create explicit lab palette if per_lab
        if per_lab:
            if not "lab_id" in counts.columns:
                raise ValueError(
                    "per_lab is True but 'lab_id' column not in counts DataFrame."
                )
            unique_labs = sorted(counts["lab_id"].unique())
            lab_palette = {lab: colors_labs[i] for i, lab in enumerate(unique_labs)}

        sns.lineplot(
            data=counts,
            x=label_x,
            y="count",
            hue="mouse_name" if per_mouse else "lab_id" if per_lab else None,
            alpha=0.7 if per_mouse else 1,
            color="black",
            errorbar="se",
            palette=(
                ["grey"] * counts["mouse_name"].nunique()
                if per_mouse
                else lab_palette if per_lab else None
            ),
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
            grouped_data = counts.groupby(["aperture", "lab_id"], as_index=False)[
                "count"
            ].mean()
            unique_labs = sorted(grouped_data["lab_id"].unique())
            lab_palette = {lab: colors_labs[i] for i, lab in enumerate(unique_labs)}

            sns.scatterplot(
                data=grouped_data,
                x=label_x,
                y="count",
                alpha=0.7,
                palette=lab_palette,
                zorder=4,
                hue="lab_id",
                ax=ax,
                s=50,
            )  # per lab scatter

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

    # Plot individual session points
    if per_lab and color_sessions_by_lab and "lab_id" in counts.columns:
        # Color by lab
        unique_labs = sorted(counts["lab_id"].unique())
        lab_palette = {lab: colors_labs[i] for i, lab in enumerate(unique_labs)}
        sns.scatterplot(
            data=counts,
            x=label_x,
            y="count",
            alpha=alpha,
            hue="lab_id",
            palette=lab_palette,
            s=25,
            ax=ax,
            legend=False,
            zorder=2,
        )
    else:
        # Use grey or color_map for other cases
        sns.scatterplot(
            data=counts,
            x=label_x,
            y="count",
            alpha=alpha if per_mouse or per_lab else 1,
            hue=label_x,
            palette=(
                ["grey"] * len(counts["count"]) if per_mouse or per_lab else color_map
            ),
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
            zorder=100,
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
            zorder=100,  # Set very high to ensure it's on top
        )

    if not per_mouse:
        ax.legend([], [], frameon=False)


def _plot_bias_horizontal(
    counts: pd.DataFrame,
    label_x: str,
    per_mouse: bool = False,
    per_lab: bool = False,
    alpha: float = 0.3,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
    color_sessions_by_lab: bool = True,
):
    """Plot bias as horizontal bars with session means per condition.

    Args:
        counts (pd.DataFrame): DataFrame containing bias data with 'count' column.
        label_x (str): Column label for the categories (e.g., "aperture").
        per_mouse (bool, optional): If True, plot per mouse. Default is False.
        per_lab (bool, optional): If True, plot per lab. Default is False.
        alpha (float, optional): Alpha transparency for individual points. Default is 0.3.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
        color_sessions_by_lab (bool, optional): If True and per_lab=True, color individual
            session points by lab color. If False, use grey. Default is True.
    """
    if label_x == "aperture":
        unique_labels = counts[label_x].astype(float).sort_values().astype(str).unique()
    else:
        unique_labels = counts[label_x].sort_values().unique()

    figsize = (5, int(2 * len(unique_labels)))
    cmap_colors = sns.color_palette(cmap, len(unique_labels))
    color_map = {label: cmap_colors[i] for i, label in enumerate(unique_labels)}

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

    # Plot individual session points
    if per_lab and color_sessions_by_lab and "lab_id" in counts.columns:
        # Color individual sessions by lab
        # Create explicit lab_id to color mapping
        unique_labs = sorted(counts["lab_id"].unique())
        lab_palette = {lab: colors_labs[i] for i, lab in enumerate(unique_labs)}

        sns.scatterplot(
            data=counts,
            x="count",
            y=label_x,
            alpha=alpha,
            hue="lab_id",
            palette=lab_palette,
            s=50,
            ax=ax,
            legend=False,
            zorder=2,
        )
    else:
        # Use grey for individual sessions
        sns.scatterplot(
            data=counts,
            x="count",
            y=label_x,
            alpha=alpha,
            s=50,
            ax=ax,
            legend=False,
            zorder=2,
            color="grey",
        )

    # Compute and plot means
    if per_mouse and "mouse_name" in counts.columns:
        grouped_counts = counts.groupby([label_x, "mouse_name"], as_index=False)[
            "count"
        ].mean()

        # Plot per-group means as smaller points
        sns.scatterplot(
            data=grouped_counts,
            x="count",
            y=label_x,
            alpha=0.7,
            s=80,
            ax=ax,
            legend=False,
            zorder=3,
            hue=label_x if label_x == "aperture" else label_x,
            palette=color_map,
        )

        # Compute overall means
        means = grouped_counts.groupby(label_x)["count"].mean()
        errors = grouped_counts.groupby(label_x)["count"].sem()
    elif per_lab and "lab_id" in counts.columns:
        grouped_counts = counts.groupby([label_x, "lab_id"], as_index=False)[
            "count"
        ].mean()

        # Create explicit lab_id to color mapping
        unique_labs = sorted(grouped_counts["lab_id"].unique())
        lab_palette = {lab: colors_labs[i] for i, lab in enumerate(unique_labs)}

        # Plot per-lab means as colored points
        sns.scatterplot(
            data=grouped_counts,
            x="count",
            y=label_x,
            alpha=0.7,
            palette=lab_palette,
            hue="lab_id",
            s=80,
            ax=ax,
            legend=False,
            zorder=3,
        )

        # Compute overall means
        means = grouped_counts.groupby(label_x)["count"].mean()
        errors = grouped_counts.groupby(label_x)["count"].sem()
    else:
        means = counts.groupby(label_x)["count"].mean()
        errors = counts.groupby(label_x)["count"].sem()

    # Plot overall means with error bars
    y_positions = range(len(means.index))
    ax.scatter(
        means.values,
        y_positions,
        color="black",
        s=70,
        marker="o",
        zorder=5,
    )

    ax.errorbar(
        x=means.values,
        y=y_positions,
        xerr=errors.values,
        fmt="none",
        ecolor="black",
        elinewidth=2,
        capsize=5,
        capthick=2,
        zorder=4,
    )
    return ax


def plot_trial_count(
    df,
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
            "Cannot plot per mouse and per lab at the same time, please choose one."
        )

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


def plot_rate(
    df,
    label_x: str,
    per_aperture: bool = False,
    per_mouse: bool = False,
    per_lab: bool = False,
    alpha: float = 0.5,
    plot_bias: bool = False,
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "Set1",
    color_sessions_by_lab: bool = True,
):
    """Plot the rate for a given `label_x` column per session or per aperture.

    This works specifically for plotting the choice rate, the reward rate,
    the target location rate, the trial count.

    Args:
        df (pd.DataFrame): DataFrame containing the data to plot.
        label_x (str): Name of the column
        per_aperture (bool, optional): If True, plot per aperture. Default is False.
        per_mouse (bool, optional): If True, plot per mouse. Default is False.
        per_lab (bool, optional): If True, plot per lab. Default is False.
        alpha (float, optional): Alpha transparency for the plot. Default is 0.5.
        plot_bias (bool, optional): If True, plot the bias (2*rate - 1). Default is False.
            Used for the choice rate to choice bias.
        ax (matplotlib.axes.Axes, optional): Matplotlib Axes object to plot on. Default is None.
        cmap (str, optional): Color map for the plot. Default is "Set1".
        color_sessions_by_lab (bool, optional): If True and per_lab=True with plot_bias=True,
            color individual session points by lab. If False, use grey. Default is True.
    """

    num_aperture = len(df.aperture.unique())
    ax = _create_axes(ax=ax, per_aperture=per_aperture, num_aperture=1)

    group_cols = ["dataset"]

    if per_aperture:
        group_cols.append("aperture")

    if per_mouse and per_lab:
        raise ValueError(
            "Cannot plot per mouse and per lab at the same time, please choose one."
        )

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
            counts = pd.DataFrame(
                counts.reset_index().sort_values(by=["aperture", "lab_id"])
            )
        else:
            counts = pd.DataFrame(counts.reset_index().sort_values(by="aperture"))
        counts.aperture = counts.aperture.round(2).astype(str)
    else:
        if per_lab:
            counts = pd.DataFrame(counts.reset_index().sort_values(by="lab_id"))
        else:
            counts = pd.DataFrame(counts.reset_index())
    counts = counts.rename(columns={"trial": "count"})

    if plot_bias:
        counts["count"] = 2 * counts["count"] - 1  # to have it between -1 and 1
        print(counts[counts["count"] > 0.5].dataset.tolist())
        _plot_bias_horizontal(
            counts=counts,
            label_x="aperture" if per_aperture else None,
            per_mouse=per_mouse,
            per_lab=per_lab,
            alpha=alpha,
            ax=ax,
            cmap=cmap,
            color_sessions_by_lab=color_sessions_by_lab,
        )
    else:
        _plot_bar_counts(
            counts=counts,
            label_x="aperture" if per_aperture else None,
            per_lab=per_lab,
            alpha=alpha,
            per_mouse=per_mouse,
            ax=ax,
            cmap=cmap,
            color_sessions_by_lab=color_sessions_by_lab,
        )
        ax.set_xlim(-0.5, num_aperture - 0.5)

    if per_aperture and not plot_bias:
        data_for_stats = counts
        if per_mouse:
            data_for_stats = counts.groupby(["mouse_name", "aperture"], as_index=False)[
                "count"
            ].mean()

        stats_tests = pd.DataFrame(
            zip(
                data_for_stats.groupby("aperture")["count"].mean(),
                data_for_stats.groupby("aperture")["count"].sem(),
            ),
            columns=["mean", "sem"],
            index=data_for_stats.groupby("aperture")["count"].mean().index,
        )

        for i in data_for_stats.aperture.unique():
            t_null, p_null = stats.ttest_1samp(
                data_for_stats[data_for_stats["aperture"] == i]["count"], 0
            )
            print(f"{i} vs chance 0: t={t_null:.2f}, p={p_null:.3f}")

            for j in data_for_stats.aperture.unique():
                if i < j:
                    if per_mouse:
                        pairs = data_for_stats.pivot(
                            index="mouse_name", columns="aperture", values="count"
                        )
                        if (i in pairs.columns) and (j in pairs.columns):
                            a = pairs[i]
                            b = pairs[j]
                            mask = a.notna() & b.notna()
                            stat = stats.ttest_rel(a[mask], b[mask])
                            print(f"{i}-{j} (paired across mice): {stat}")
                    else:
                        stat = stats.ttest_rel(
                            counts[counts["aperture"] == i]["count"],
                            counts[counts["aperture"] == j]["count"],
                        )
                        print(f"{i}-{j}: {stat}")

    else:
        data_for_stats = counts
        if per_mouse and "mouse_name" in counts.columns:
            if "aperture" in counts.columns:
                data_for_stats = counts.groupby(
                    ["mouse_name", "aperture"], as_index=False
                )["count"].mean()
            else:
                data_for_stats = counts.groupby(["mouse_name"], as_index=False)[
                    "count"
                ].mean()

        if "aperture" in data_for_stats.columns:
            for i in data_for_stats.aperture.unique():
                t_null, p_null = stats.ttest_1samp(
                    data_for_stats[data_for_stats["aperture"] == i]["count"], 0
                )
                print(f"{i} vs chance 0: t={t_null:.2f}, p={p_null:.3f}")

                mean_i = data_for_stats[data_for_stats["aperture"] == i]["count"].mean()
                sem_i = data_for_stats[data_for_stats["aperture"] == i]["count"].sem()
                print(f"{i}: mean={mean_i:.3f} ± {sem_i:.3f}")
    return counts


def plot_rewards(
    df,
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
        stats = pd.DataFrame(
            zip(
                counts.groupby("aperture")["count"].mean(),
                counts.groupby("aperture")["count"].sem(),
            ),
            columns=["mean", "sem"],
            index=counts.groupby("aperture")["count"].mean().index,
        )
    else:
        stats = (counts["count"].mean(), counts["count"].std())
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
            else colors_rewarded if label_x == "trial_rewarded" else colors_choice
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
    _plot_bar_counts(counts=mean_counts, label_x=label_x, alpha=alpha, ax=ax, cmap=cmap)

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

    if per_lab:
        counts = pd.DataFrame(
            counts.reset_index().sort_values(by=["aperture", "lab_id"])
        )
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

    stats_results = []
    for i in counts.aperture.unique():
        for j in counts.aperture.unique():
            if i < j:
                stat = stats.ttest_rel(
                    counts[counts["aperture"] == i][label_parameter],
                    counts[counts["aperture"] == j][label_parameter],
                )
                print(f"{i}-{j}: {stat}")
                print(
                    counts[counts["aperture"] == j][label_parameter].mean()
                    - counts[counts["aperture"] == i][label_parameter].mean()
                )
                stats_results.append((i, j, stat.statistic, stat.pvalue))
    return counts, stats_results


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

    lc = matplotlib.collections.LineCollection(segments, cmap=cmap, alpha=alpha)
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
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))

    hist, _, _, img = ax.hist2d(
        df.groupby(["dataset", "trial"]).first().trial_init_x,
        df.groupby(["dataset", "trial"]).first().trial_init_y,
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


def plot_rolling_reward(df, ax=None, rolling_window=15, per_aperture=False):
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 3))

    if per_aperture:
        group = ["aperture", "trial"]
    else:
        group = "trial"

    if "reward" in df.columns:
        rewarded = df.groupby(group)["reward"].max().reset_index()
    elif "trial_rewarded" in df.columns:
        rewarded = df.groupby(group)["trial_rewarded"].max().reset_index()
        rewarded = rewarded.rename(columns={"trial_rewarded": "reward"})
    else:
        raise ValueError(
            "DataFrame must contain either 'reward' or 'trial_rewarded' column."
        )

    rewarded["rolling_reward"] = rewarded.reward.rolling(
        rolling_window, min_periods=1, win_type="gaussian", center=True
    ).mean(std=3)

    ax.bar(rewarded.trial, rewarded.reward, color="grey")
    sns.lineplot(
        data=rewarded,
        x="trial",
        y="rolling_reward",
        hue="aperture" if per_aperture else None,
        palette=(
            colors_aperture[1] + colors_aperture[0] if per_aperture else ["#B52916"]
        ),
        linewidth=3,
        ax=ax,
    )
    ax.set_ylabel("Rewarded")
    ax.set_xlabel("Trial")


def plot_rolling_variable(df, label, ax=None, rolling_window=15, per_aperture=False):
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 3))

    if per_aperture:
        group = ["aperture", "trial"]
    else:
        group = "trial"

    df_grouped = df.groupby(group)[label].mean().reset_index()
    df_grouped["rolling_" + label] = (
        df_grouped[label]
        .rolling(rolling_window, min_periods=1, win_type="gaussian", center=True)
        .mean(std=3)
    )

    df_grouped.sort_values(by="aperture", inplace=True)

    ax.bar(df_grouped.trial, df_grouped[label], color="grey")
    sns.lineplot(
        data=df_grouped,
        x="trial",
        y="rolling_" + label,
        hue="aperture" if per_aperture else None,
        palette=(
            [colors_aperture[1], colors_aperture[0]] if per_aperture else ["#B52916"]
        ),
        linewidth=3,
        ax=ax,
    )
    ax.set_ylabel(label)
    ax.set_xlabel("Trial")


def plot_rolling_aperture_diff(df, label, ax=None, rolling_window=15, color="#B52916"):
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 3))

    # Group by trial and aperture to get raw means
    df_grouped = df.groupby(["trial", "aperture"])[label].mean().reset_index()

    # Pivot so each aperture has its own column (trials without a specific aperture will be NaN)
    df_pivot = df_grouped.pivot(index="trial", columns="aperture", values=label)
    apertures = df_pivot.columns

    # Compute rolling mean for each column independently
    # This interpolates/smooths over the gaps where that aperture wasn't present
    df_rolling = df_pivot.rolling(
        rolling_window, min_periods=1, win_type="gaussian", center=True
    ).mean(std=3)

    # Compute the difference between the smoothed series
    diff_col = f"diff_{label}"
    df_rolling[diff_col] = df_rolling[apertures[1]] - df_rolling[apertures[0]]

    ax.axhline(0, color="black", linestyle="--", alpha=0.5)

    sns.lineplot(
        data=df_rolling,
        x=df_rolling.index,
        y=diff_col,
        color=color,
        linewidth=3,
        ax=ax,
    )

    ax.set_ylabel(f"$\Delta$ Rolling {label}")
    ax.set_xlabel("Trial")
    ax.set_title(f"{apertures[1]} minus {apertures[0]}")


def plot_choices_by_trial(df, ax=None):
    """Plots choices per trial on a rolling window.

    Args:
        df (pandas.DataFrame): The dataframe containing the data.
        ax (matplotlib.axes._subplots.AxesSubplot): The subplot axes.

    """
    if ax is None:
        fig, ax = plt.subplots()

    df = df.groupby("trial", as_index=False).apply(lambda group: group.iloc[1:, :])

    if "reward" in df.columns:
        rewarded = df[df.reward == 1.0]
    else:
        rewarded = df[df.trial_rewarded == 1.0]
        rewarded = rewarded.rename(columns={"trial_rewarded": "reward"})

    last = df.groupby(["trial"], as_index=False).last()

    # choice plot
    ax.plot(
        last.trial,
        last.trial_left_choice.rolling(
            10, center=True, win_type="gaussian", min_periods=1
        ).mean(std=5),
        c="black",
        linewidth=3,
    )
    # choice scatter
    ax.scatter(last.trial, last.trial_left_choice, c="black", alpha=0.3)

    # rewarded left choice scatter
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.trial_left_choice == 1.0)],
        rewarded.trial_left_choice[
            (rewarded.reward == 1.0) & rewarded.trial_left_choice == 1.0
        ],
        c=colors_choice[0],
    )
    # rewarded right choice scatter
    ax.scatter(
        rewarded.trial[(rewarded.reward == 1.0) & (rewarded.trial_left_choice == 0.0)],
        rewarded.trial_left_choice[
            (rewarded.reward == 1.0) & rewarded.trial_left_choice == 0.0
        ],
        c=colors_choice[1],
    )
    ax.set_xlabel("Trials")
    ax.set_ylabel("Choice (1 = Left)")


def plot_training_phases(
    ax,
    data,
    y="session_reward",
    hue=None,
    ylim=None,
    ylabel=None,
    x_label="num_train_stage",
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
        sns.pointplot(data=data, x=x_label, y=y, color="black", capsize=0.1, ax=ax)

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
        stage_colors = [
            "#3FB47C",
            "#3FB47C",
            "#1F6F49",
            "#FF1493",
            "#FF1493",
            "#FF1493",
        ]

        ax.set_xticks(stage_positions)
        ax.set_xticklabels(stage_labels, rotation=0, fontsize=12)

        # Color the x-tick labels
        for j, label in enumerate(ax.get_xticklabels()):
            label.set_color(stage_colors[j])

    # Add reference lines
    if y == "session_reward":
        ax.axhline(0.5, linestyle="dashed", color="black", alpha=0.5)
        ax.axhline(0.70, linestyle="dashed", color="red", alpha=0.3)

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

    line_styles = ["-", (0, (5, 5)), ":", "-."]
    styles = {
        val: line_styles[i % len(line_styles)] for i, val in enumerate(style_values)
    }

    fig, ax = plt.subplots(figsize=(5, 5))

    plt.axvline(x=0, ymax=0.95, color="black", linestyle="--", linewidth=1)

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

    ax.grid(False)
    ax.set_xlim(-18, 18)
    ax.set_ylim(0, 23)
    plt.axis("off")

    return fig, ax
