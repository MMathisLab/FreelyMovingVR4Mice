import os
import warnings
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.interpolate import CubicSpline
from vr4mice.schema import base_analysis, vr4mice, dlc

# from scipy.signal import savgol_filter, hilbert, find_peaks
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


# Filter out the UserWarning related to the deprecated features
warnings.filterwarnings("ignore", category=UserWarning)


def fetch_data(key, database):
    # fetch or populate to get df (externalize)
    if database:
        from vr4mice.schema import base_analysis

        try:
            df, interp = base_analysis.DataFrame().get_data(key)
            flag = df is False
            if not flag:
                logger.info("Data fetched for " + str(key))
            else:
                logger.info("Populating DataFrame data for " + str(key))
                df = base_analysis.DataFrame().populate(key)
                df, interp = base_analysis.DataFrame().get_data(key)
                flag = df is False
                if not flag:
                    logger.info("Data populated and fetched for " + str(key))

            rewarded = base_analysis.DataFrame().get_rewarded(key)
            choices = base_analysis.DataFrame().get_choices(key)

        except Exception as e:
            logger.warning(f"An error occurred: {e}")

        try:
            box_df_output = base_analysis.BoxDataFrame().get_data(key)
            flag = box_df_output is False
            if not flag:
                logger.info("Box data fetched for " + str(key))
            else:
                logger.info("Populating BoxDataFrame data for " + str(key))
                box_df_output = base_analysis.BoxDataFrame().populate(key)
                box_df_output = base_analysis.BoxDataFrame().get_data(key)
                flag = box_df_output is False
                if not flag:
                    logger.info("Data populated and fetched for " + str(key))

        except Exception as e:
            logger.warning(f"An error occurred: {e}")
    else:
        df, interp = create_data_frame(key, no_iti=True)
        box_df_output = get_box_df(key, interp=interp)
        rewarded = get_rewarded(df)
        choices = get_choices(df)

    return df, interp, box_df_output, rewarded, choices


def get_path(key, base, ext=".png"):
    name = str(key) + "_summary_plot" + ext
    return Path(base).joinpath(name)


def get_subtitle(key, task_name="AR Task"):
    # todo: add parcing of filename
    return task_name + ": Dataset: " + str(key["dataset"])


def vr4mice_summary_plots(key, save_path="/data/summary_plots", database=True):
    """
    Generate a summary plot for a given dataset.
    final results to email
    [DJ SummaryPlot table: path?]
    Args:
        key (dict): A dictionary containing the following keys: "mouse_name", "day", and "attempt". This specifies which dataset to generate a summary plot for.
        save_path (str, optional): The directory path where the summary plot should be saved. Defaults to "/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/".

    Returns:
        str: The full path of the saved summary plot.

    """

    df, interp, box_df_output, rewarded, choices = fetch_data(key, database)

    fig = plt.figure(figsize=(25, 20), constrained_layout=True)

    gs = plt.GridSpec(6, 8, figure=fig)
    ax1 = fig.add_subplot(gs[0:2, 0:3])

    ax2 = fig.add_subplot(gs[0:2, 3:5])
    ax3 = fig.add_subplot(gs[0:2, 5:7])

    ax4 = fig.add_subplot(gs[2, 0:1])
    ax5 = fig.add_subplot(gs[2, 1:2])
    ax6 = fig.add_subplot(gs[2, 2:3])
    ax7 = fig.add_subplot(gs[2, 3:4])
    time_plots_1 = fig.add_subplot(gs[2, 4:6])
    time_plots_2 = fig.add_subplot(gs[2, 6:8])
    ax8 = fig.add_subplot(gs[4, :])
    ax9 = fig.add_subplot(gs[5, :])

    velocity_plot_reward = fig.add_subplot(gs[3, 0:2])
    velocity_plot_choice = fig.add_subplot(gs[3, 2:4])
    heading_angle_plot = fig.add_subplot(gs[3, 4:6])

    _plot_all_trajectories(df=df, box_df=box_df_output, ax=ax1)
    _plot_rewarded_trial_trajectories(
        df=df, box_df=box_df_output, ax=[ax2, ax3], rewarded=rewarded
    )

    _plot_time_to_rewards(df, ax=[time_plots_1, time_plots_2])
    _plot_trial_velocities(df, ax=[velocity_plot_reward, velocity_plot_choice])
    _plot_heading_direction(df, ax=heading_angle_plot)
    _plot_choices(choices, ax=[ax4, ax5])
    _plot_rewards(rewarded, ax=[ax6, ax7, ax8])
    _plot_choices_by_trial(df, ax=ax9, choices=choices)

    if database:
        full_path = base_analysis.OutputPlots().get_path(
            key=key, base=save_path, ext=".png"
        )
        subtitle = base_analysis.OutputPlots().get_subtitle(
            key=key, task_name="AR Task"
        )
    else:
        full_path = get_path(key=key, base=save_path, ext=".png")
        subtitle = get_subtitle(key=key, task_name="AR Task")

    fig.suptitle(subtitle)
    plt.savefig(full_path)
    plt.close()  # interactive

    return full_path



def plot_keypoints(keypoints: pd.DataFrame, keypoints_list: List[str], confidence: float, xlim: tuple, cmap: str, key: dict) -> None:
    """
    Creates a summary plot for a list of keypoints.
    This function plots the x,y an confidence for a given window for each of a list of keypoints.
    
    Args:
    - keypoints: DataFrame or dictionary containing keypoint data with 'x', 'y', and 'likelihood'.
    - keypoints_list: List of keypoint names (strings) to be plotted.
    - confidence: Confidence threshold for coloring points.
    - xlim: Tuple specifying the x-axis limits for the plots.
    - cmap: Colormap to be used for plotting.
    - key: Identifier for the plot title.
    """
    

    num_keypoints = len(keypoints_list)
    num_cols = 2  
    num_rows = int(np.ceil(num_keypoints / num_cols))  

    
    fig, ax = plt.subplots(num_rows * 3, num_cols, sharex=True, figsize=(15, 6 * num_rows))
    fig.suptitle(f"DLC tracking summary plot - {key}")

 
    for i, keypoint in enumerate(keypoints_list):
        
        col = i % num_cols  
        row_offset = (i // num_cols) * 3  
        
        # X position plot
        ax[row_offset, col].scatter(keypoints.pose_time - keypoints.pose_time[0], keypoints[keypoint].x, 
                                    c=keypoints[keypoint].likelihood < confidence, s=1, alpha=0.5, cmap=cmap)
        ax[row_offset, col].set_ylabel(f"X pos")
        ax[row_offset, col].set_title(f"{keypoint}")
        
        # Y position plot
        ax[row_offset + 1, col].scatter(keypoints.pose_time - keypoints.pose_time[0], keypoints[keypoint].y, 
                                        c=keypoints[keypoint].likelihood < confidence, s=1, alpha=0.5, cmap=cmap)
        ax[row_offset + 1, col].set_ylabel(f"Y pos")
        
        # Confidence plot
        ax[row_offset + 2, col].scatter(keypoints.pose_time - keypoints.pose_time[0], keypoints[keypoint].likelihood, 
                                        c=keypoints[keypoint].likelihood < confidence, s=1, alpha=0.5, cmap=cmap)
        ax[row_offset + 2, col].set_ylabel(f"Confidence")
        ax[row_offset + 2, col].set_ylim(0, 1)
        
        # Set xlim for each of the 3 rows
        for j in range(3):
            ax[row_offset + j, col].set_xlim(xlim)
        
        # Only set xlabel for the confidence plot (the bottom plot in each column)
        ax[row_offset + 2, col].set_xlabel('Time')

    plt.tight_layout()  
    plt.show()


def plot_keypoints_summary(key, save_path="", keypoints_list = ["head_midpoint", "nose", "neck", "tail_base"], xlim=(0, 800), confidence=0.6, cmap="bwr") -> str:
    """
    Generates DLC tracking summary plot for a given dataset.
    
    Args:
    - key: key for dataset {"dataset": "Jacana_2024-08-01_1"}
    - keypoints_list: List of keypoint names (strings) to be plotted.
    - confidence: DLC confidence threshold for coloring points.
    - xlim: Tuple specifying the x-axis limits for the plots.
    - cmap: Colormap to be used for plotting.
    - key: Identifier for the plot title.
    
    Returns:
    - Figure_save_path
    """
    # Get keypoints data
    figure_save_path = save_path + key ["dataset"] + ".png"
    print(figure_save_path)
    keypoints = dlc.DLCKptsDf().get_data(key=key)
    plot_keypoints(keypoints, keypoints_list, xlim=xlim, cmap=cmap, confidence=confidence, key=key["dataset"])
    plt.savefig(figure_save_path, transparent=True)
    return(figure_save_path)
