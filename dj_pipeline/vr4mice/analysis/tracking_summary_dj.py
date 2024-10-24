from typing import List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vr4mice.schema import  dlc


def plot_keypoints(
    keypoints: pd.DataFrame,
    keypoints_list: List[str],
    confidence: float,
    xlim: tuple,
    cmap: str,
    key: dict,
) -> None:
    """
    Creates a summary plot for a list of keypoints.
    This function plots the x,y an confidence for a given window for each of a list of keypoints.

    Args:
        keypoints: DataFrame or dictionary containing keypoint data with 'x', 'y', and 'likelihood'.
        keypoints_list: List of keypoint names (strings) to be plotted.
        confidence: Confidence threshold for coloring points.
        xlim: Tuple specifying the x-axis limits for the plots.
        cmap: Colormap to be used for plotting.
        key: Identifier for the plot title.
    """

    num_keypoints = len(keypoints_list)
    num_cols = 2
    num_rows = int(np.ceil(num_keypoints / num_cols))

    fig, ax = plt.subplots(
        num_rows * 3, num_cols, sharex=True, figsize=(15, 6 * num_rows)
    )
    fig.suptitle(f"DLC tracking summary plot - {key}")

    for i, keypoint in enumerate(keypoints_list):

        col = i % num_cols
        row_offset = (i // num_cols) * 3

        # X position plot
        ax[row_offset, col].scatter(
            keypoints.pose_time - keypoints.pose_time[0],
            keypoints[keypoint].x,
            c=keypoints[keypoint].likelihood < confidence,
            s=1,
            alpha=0.5,
            cmap=cmap,
        )
        ax[row_offset, col].set_ylabel(f"X pos")
        ax[row_offset, col].set_title(f"{keypoint}")

        # Y position plot
        ax[row_offset + 1, col].scatter(
            keypoints.pose_time - keypoints.pose_time[0],
            keypoints[keypoint].y,
            c=keypoints[keypoint].likelihood < confidence,
            s=1,
            alpha=0.5,
            cmap=cmap,
        )
        ax[row_offset + 1, col].set_ylabel(f"Y pos")

        # Confidence plot
        ax[row_offset + 2, col].scatter(
            keypoints.pose_time - keypoints.pose_time[0],
            keypoints[keypoint].likelihood,
            c=keypoints[keypoint].likelihood < confidence,
            s=1,
            alpha=0.5,
            cmap=cmap,
        )
        ax[row_offset + 2, col].set_ylabel(f"Confidence")
        ax[row_offset + 2, col].set_ylim(0, 1)

        # Set xlim for each of the 3 rows
        for j in range(3):
            ax[row_offset + j, col].set_xlim(xlim)

        # Only set xlabel for the confidence plot (the bottom plot in each column)
        ax[row_offset + 2, col].set_xlabel("Time")

    plt.tight_layout()
    plt.show()


def plot_keypoints_summary(
    key,
    save_path="",
    keypoints_list=["head_midpoint", "nose", "neck", "tail_base"],
    xlim=(0, 800),
    confidence=0.6,
    cmap="bwr",
) -> str:
    """
    Generates DLC tracking summary plot for a given dataset.

    Args:
        key: key for dataset {"dataset": "Jacana_2024-08-01_1"}
        keypoints_list: List of keypoint names (strings) to be plotted.
        confidence: DLC confidence threshold for coloring points.
        xlim: Tuple specifying the x-axis limits for the plots.
        cmap: Colormap to be used for plotting.
        key: Identifier for the plot title.

    Returns:
        Figure_save_path
    """
    # Get keypoints data
    figure_save_path = save_path + key["dataset"] + ".png"
    print(figure_save_path)
    keypoints = dlc.DLCKptsDf().get_data(key=key)
    plot_keypoints(
        keypoints,
        keypoints_list,
        xlim=xlim,
        cmap=cmap,
        confidence=confidence,
        key=key["dataset"],
    )
    plt.savefig(figure_save_path, transparent=True)
    return figure_save_path

