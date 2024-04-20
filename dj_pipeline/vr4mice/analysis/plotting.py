import matplotlib.pyplot as plt
import numpy as np

from matplotlib.transforms import Affine2D
from matplotlib.collections import PathCollection

import seaborn as sns

"""
Color codes:
    - left box: purple: '#5C0A72'
    - right box: orange: '#FD672C'
    - center box: blue: '#009B9E'
    
    - SET2 colormap for the apertures, 
    4.3 = '#EC8788', 12 = '#96B9D6'
"""


def plot_box_rectangle(
    df_box, box_label, edgecolor="#009B9E", fill=False, alpha=0.6, linewidth=4
):
    return plt.Rectangle(
        (df_box[f"{box_label}_box_x_min"], df_box[f"{box_label}_box_z_min"]),
        abs(df_box[f"{box_label}_box_x_min"] - df_box[f"{box_label}_box_x_max"]),
        abs(df_box[f"{box_label}_box_z_min"] - df_box[f"{box_label}_box_z_max"]),
        fill=fill,
        linewidth=linewidth,
        edgecolor=edgecolor,
        alpha=alpha,
    )


def plot_all_boxes(ax, df_box):
    """Visualise boxes on tajectory plots."""

    start_box = plot_box_rectangle(df_box, box_label="tt", edgecolor="#009B9E")
    left_box = plot_box_rectangle(df_box, box_label="left", edgecolor="#5C0A72")
    right_box = plot_box_rectangle(df_box, box_label="right", edgecolor="#FD672C")

    ax.add_patch(start_box)
    ax.add_patch(left_box)
    ax.add_patch(right_box)
    ax.set_xlim(-28, 28)
    ax.set_ylim(-28, 28)


def plot_all_trajectories(
    ax, df, per_side=False, label_x="x", label_y="y", scatter_reward=True
):
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
        if per_side:
            ax.plot(
                df[label_x][((df.trial == i) & (df.trial_L_choice == 1))],
                df[label_y][((df.trial == i) & (df.trial_L_choice == 1))],
                c="#5C0A72",
                alpha=0.2,
                linewidth=2,
            )
            ax.plot(
                df[label_x][((df.trial == i) & (df.trial_L_choice == 0))],
                df[label_y][((df.trial == i) & (df.trial_L_choice == 0))],
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

        R_choices = np.where(df["reward"] > 0)[0]
        trial_start = np.diff(df["trial"])
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
    ax.set_xlabel("X pos (cm)")
    ax.set_ylabel("Y pos (cm)")


def lineplot_flip_axis(ax=None, **kwargs):
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


def plot_trajectories_per_session_aperture(
    df,
    df_box,
    ax,
    init_histo=True,
    bins_init_histo=10,
    vmax_init_histo=10,
    cmap_init_histo="magma",
    label_x="x",
    label_y="y",
    scatter_reward=True,
):
    for i, session in enumerate(df.session.unique()):
        for j, aperture in enumerate(
            np.sort(df[df.session == session].aperture.unique())
        ):
            data = df[(df.session == session) & (df.aperture == aperture)]
            if init_histo:
                ax[i][j].hist2d(
                    data.groupby(["trial"]).first().trial_init_x,
                    data.groupby(["trial"]).first().trial_init_y,
                    bins=bins_init_histo,
                    cmap=cmap_init_histo,
                    range=[(-12, 12), (-20.25, 6.75)],
                    vmax=vmax_init_histo,
                )
            plot_all_boxes(ax[i][j], df_box)
            plot_all_trajectories(
                ax[i][j],
                data,
                per_side=True,
                label_x=label_x,
                label_y=label_y,
                scatter_reward=scatter_reward,
            )
            ax[i][j].set_title(f"{session}_{aperture}")
