from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation

from analysis.dlc_helpers import filter_dlc


def plot_frame_keypoints(dlc_dict: dict, frame_number: int = 1):
    body_parts = dlc_dict.columns.get_level_values(0).unique()[:-2]

    for b in body_parts:
        key_point = dlc_dict[b].iloc[frame_number]
        plt.scatter(key_point.x, key_point.y, alpha=key_point.likelihood)

    plt.xlim(0, 700)
    plt.ylim(0, 700)
    plt.show()


def plot_on_subplot(
    ax, data_dict: dict, frame_number: int, heading_direction: Tuple[int]
):
    body_parts = data_dict.columns.get_level_values(0).unique()[:-2]
    for b in body_parts:
        x = data_dict[b]["x"][frame_number]
        y = data_dict[b]["y"][frame_number]
        likelihood = data_dict[b]["likelihood"][frame_number]
        ax.scatter(x, y, alpha=likelihood, c=likelihood, vmin=0, vmax=1)

    mean_x = np.mean([data_dict[b]["x"][frame_number] for b in body_parts])
    mean_y = np.mean([data_dict[b]["y"][frame_number] for b in body_parts])
    ax.arrow(
        mean_x,
        mean_y,
        heading_direction[0],
        heading_direction[1],
        width=1,
        color="red",
        length_includes_head=True,
    )
    x = data_dict[b]["x"][frame_number]
    y = data_dict[b]["y"][frame_number]
    ax.set_xlim(0, 550)
    ax.set_ylim(0, 550)


def update_plots(
    frame_number: int,
    dlc_dict: dict,
    orig,
    axs,
    heading_direction: Tuple[int] = (10, 5),
):
    axs[0].clear()
    axs[1].clear()
    print(frame_number)

    plot_on_subplot(axs[0], dlc_dict, frame_number, heading_direction)
    axs[0].set_title("Modified Data")
    plot_on_subplot(axs[1], orig, frame_number, heading_direction)
    axs[1].set_title("Original Data")


def make_animated_movie(
    dlc_data: pd.DataFrame,
    frames: List[int] = [1, 500, 10],
    cutoff: float = 0.3,
    window_length: int = 9,
    polyorder: int = 3,
    path: str = "/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_animation.mp4",
):
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    orig = dlc_data.copy()
    filt_dlc = filter_dlc(
        dlc_data.copy(), cutoff=cutoff, window_length=window_length, polyorder=polyorder
    )

    ani = FuncAnimation(
        fig,
        update_plots,
        frames=range(frames[0], frames[1], frames[2]),
        fargs=(filt_dlc, orig, axs),
        interval=10,
    )
    ani.save(path, fps=10, extra_args=["-vcodec", "libx264"])


def plot_dlc_heading_direction(
    ax, df: pd.DataFrame, computed_dlc: pd.DataFrame, frame: int
):
    ax.clear()

    ax.set_xlabel("X coordinate")
    ax.set_ylabel("Y coordinate")
    ax.set_xlim(0, 700)
    ax.set_ylim(0, 700)
    ax.axis("equal")

    row = df.iloc[frame]
    computed_row = computed_dlc.iloc[frame]

    heading_dir_radians = np.radians(computed_row.heading_dir)
    heading_angle = np.radians(computed_row.head_angle)

    # Convert the heading to vector components
    u = np.cos(heading_dir_radians)
    v = np.sin(heading_dir_radians)
    uh = np.cos(heading_angle + heading_dir_radians)
    vh = np.sin(heading_angle + heading_dir_radians)

    # Plot all keypoints for the current frame
    keypoints = row.unstack(level="coords")[["x", "y"]].values
    likelihood = row.unstack(level="coords")["likelihood"].values
    ax.scatter(
        keypoints[:, 0], keypoints[:, 1], c=likelihood, alpha=0.5, vmin=0, vmax=1
    )

    # Plot the heading direction as an arrow
    ax.quiver(
        computed_row.head_center_x,
        computed_row.head_center_y,
        u,
        v,
        color="red",
        scale=15,
        width=0.005,
    )
    ax.quiver(
        computed_row.head_center_x,
        computed_row.head_center_y,
        uh,
        vh,
        color="green",
        scale=15,
        width=0.005,
    )
    ax.set_xlim(0, 600)
    ax.set_ylim(0, 700)


def update(frame: int, ax, df: pd.DataFrame, computed_dlc: pd.DataFrame):
    """Animate each frame."""
    print(frame)
    plot_dlc_heading_direction(ax, df, computed_dlc, frame)


def create_animation_dlc_w_heading_angle(
    df: pd.DataFrame, computed_dlc: pd.DataFrame, frames: List[int]
):
    """
    df: dlc key points, computed dlc is the head angle table and frames is a range of frames.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ani = FuncAnimation(
        fig, update, frames=frames, fargs=(ax, df, computed_dlc), interval=50
    )
    plt.close(fig)
    return ani
