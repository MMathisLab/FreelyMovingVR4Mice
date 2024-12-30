import uuid
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import LineCollection
from matplotlib.widgets import Button

from mlagents_envs.side_channel.side_channel import SideChannel
from mlagents_envs.side_channel.side_channel import IncomingMessage
from uuid import UUID


class DebugLogSideChannel(SideChannel):
    def __init__(self):
        # Use the same UUID as the one in the Unity code
        super().__init__(UUID("6146928a-ea90-4477-b497-c2f10400de1b"))

    def on_message_received(self, msg: IncomingMessage) -> None:
        log_message = msg.read_string()
        print(f"Unity Debug Log: {log_message}")


def generate_uuid():
    return uuid.uuid4()


def generate_zone_patches():
    # Define the active regions (starting box and report boxes) of the Unity game arena
    screen = patches.Rectangle(
        (-10, -2), 20, 1, linewidth=4, edgecolor="r", facecolor="none"
    )
    start_box = patches.Rectangle(
        (-4, -9), 8, 4, linewidth=2, edgecolor="g", facecolor="none"
    )
    report_r = patches.Rectangle(
        (5, -4), 5, 2, linewidth=2, edgecolor="b", facecolor="none"
    )
    report_l = patches.Rectangle(
        (-10, -4), 5, 2, linewidth=2, edgecolor="b", facecolor="none"
    )
    return screen, start_box, report_r, report_l


def plot_trajectories(data):
    """
    Helper function that plots the trajectories of the mouse within the Unity game arena
    """

    data_df = dict_to_data_frame(data)
    episodes_df = data_df[data_df.ITI == 0].copy(deep=True)
    ITIs_df = data_df[data_df.ITI == 1].copy(deep=True)
    episode_nums = episodes_df.episode.unique()

    # Create a figure and axis
    fig, ax = plt.subplots(figsize=(7, 5))
    plt.subplots_adjust(bottom=0.2)  # Make space for the button
    trajectory_index = [0]

    def update_plot(ep_num):
        ax.clear()
        trajectory = episodes_df[episodes_df.episode == ep_num]
        reward = (
            True if ITIs_df[ITIs_df.episode == ep_num].reward.values[0] == 1 else False
        )

        x = trajectory.x
        y = trajectory.y

        ax.plot(x, y, color="black", linewidth=4, alpha=0.3)

        ax.scatter(
            x.iloc[0],
            y.iloc[0],
            marker="X",
            color="black",
            s=150,
            alpha=0.5,
        )

        if reward:
            ax.scatter(
                trajectory.iloc[-1].x,
                trajectory.iloc[-1].y,
                marker="*",
                color="green",
                s=150,
            )
        else:
            ax.scatter(
                trajectory.iloc[-1].x,
                trajectory.iloc[-1].y,
                marker="*",
                color="red",
                s=150,
            )

        # Boundaries of the Unity arena
        ax.set_xlim(-9, 9)
        # plt.xticks(np.arange(-9, 10, 2))
        ax.set_ylim(-10, -2)
        # plt.yticks(np.arange(-10, -1, 1))

        # Define the active regions (starting box and report boxes) of the Unity game arena
        screen, start_box, report_r, report_l = generate_zone_patches()

        # Add patches to the plot
        ax.add_patch(screen)
        ax.add_patch(report_r)
        ax.add_patch(report_l)
        ax.add_patch(start_box)
        ax.set_title(f"Episode {ep_num}")
        ax.grid(True, alpha=0.3)

        plt.draw()

    # Function for the "Next" button
    def next_trajectory(event):
        trajectory_index[0] = (trajectory_index[0] + 1) % len(episode_nums)
        update_plot(episode_nums[trajectory_index[0]])

    # Function for the "Previous" button
    def prev_trajectory(event):
        trajectory_index[0] = (trajectory_index[0] - 1) % len(episode_nums)
        update_plot(episode_nums[trajectory_index[0]])

    # Buttons for switching trajectories
    axprev = plt.axes([0.1, 0.05, 0.1, 0.075])  # Button position for 'Previous'
    axnext = plt.axes([0.8, 0.05, 0.1, 0.075])  # Button position for 'Next'

    btn_next = Button(axnext, "Next")
    btn_next.on_clicked(next_trajectory)

    btn_prev = Button(axprev, "Previous")
    btn_prev.on_clicked(prev_trajectory)

    # Initial plot
    update_plot(episode_nums[trajectory_index[0]])
    plt.show()


def compute_trigger_areas_coordinates(
    unity_arena_size,
    cropped_image,
    start_box,
    r_report_box,
    l_report_box,
):
    """
    Compute the coordinates of the trigger areas (start and report boxes) in the cropped image.
    Done by interpolating Unity arena coordinates to pygame window coordinates.
    """
    x_rects_lower = np.interp(
        np.array([start_box[1], r_report_box[1], l_report_box[1]]),
        [unity_arena_size[0], unity_arena_size[1]],
        [
            cropped_image[1],
            cropped_image[0],
        ],  # the y-axis is flipped for ergonomical reasons
    )

    x_rects_upper = np.interp(
        np.array([start_box[0], r_report_box[0], l_report_box[0]]),
        [unity_arena_size[0], unity_arena_size[1]],
        [
            cropped_image[1],
            cropped_image[0],
        ],  # the y-axis is flipped for ergonomical reasons
    )

    y_rects_lower = np.interp(
        np.array([start_box[3], r_report_box[3], l_report_box[3]]),
        [unity_arena_size[2], unity_arena_size[3]],
        [
            cropped_image[3],
            cropped_image[2],
        ],  # the y-axis is flipped for ergonomical reasons
    )

    y_rects_upper = np.interp(
        np.array([start_box[2], r_report_box[2], l_report_box[2]]),
        [unity_arena_size[2], unity_arena_size[3]],
        [
            cropped_image[3],
            cropped_image[2],
        ],  # the y-axis is flipped for ergonomical reasons
    )

    # the y-axis is flipped for ergonomical reasons
    widths = x_rects_upper - x_rects_lower
    heights = y_rects_upper - y_rects_lower
    return x_rects_lower, y_rects_lower, widths, heights


def dict_to_data_frame(data):
    """
    Convert dictionary to pandas dataframe
    """
    states = [
        "x",
        "y",
        "z",
        "mouse_can_report",
        "ITI",
        "spawner_green_on_left",
        "mouse_report_correct",
        "mouseInLeft_box",
        "mouseInRight_box",
        "speed",
        "photodiode_sync_state",
        "photodiode_change_value",
        "start_box_delay",
    ]

    data_df = pd.DataFrame(
        data=data["action"].reshape(
            data["action"].shape[0],
            data["action"].shape[2],
        ),
        columns=["action_x", "action_y", "action_head_angle", "action_photodiode"],
    )
    data_df["episode"] = data["episode"]
    data_df["step"] = data["step"]
    data_df[states] = data["state"]
    data_df["terminal"] = data["terminal"]
    data_df["reward"] = data["reward"]

    return data_df
