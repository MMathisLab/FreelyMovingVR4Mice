import uuid
import numpy as np
import pandas as pd
import tkinter as tk
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Button

from uuid import UUID
from tkinter import filedialog
from mlagents_envs.side_channel.side_channel import SideChannel
from mlagents_envs.side_channel.side_channel import IncomingMessage


class DebugLogSideChannel(SideChannel):
    def __init__(self, verbose: bool = False):
        # Use the same UUID as the one in the Unity code
        super().__init__(UUID("6146928a-ea90-4477-b497-c2f10400de1b"))
        self.verbose = verbose

    def on_message_received(self, msg: IncomingMessage) -> None:
        if self.verbose:
            log_message = msg.read_string()
            print(f"Unity Debug Log: {log_message}")


def generate_uuid():
    return uuid.uuid4()


def generate_patch(x_start, x_end, y_start, y_end):
    w = abs(x_end - x_start)
    h = abs(y_end - y_start)
    return patches.Rectangle(
        xy=(x_start, y_start),
        width=w,
        height=h,
        linewidth=2,
        edgecolor="g",
        facecolor="none",
    )


def generate_active_regions(arena, Lbox, Rbox, Sbox):
    """Define the active regions (starting box and report boxes) of the Unity game arena"""

    arena_start_x, arena_end_x, _, arena_end_y = arena

    width_screen = abs(arena_end_x - arena_start_x)
    screen = patches.Rectangle(
        (arena_start_x, arena_end_y),
        width=width_screen,
        height=1,
        linewidth=4,
        edgecolor="r",
        facecolor="none",
    )

    start_box, report_l, report_r = [
        generate_patch(x_start, x_end, y_start, y_end)
        for x_start, x_end, y_start, y_end in [Sbox[:4], Lbox[:4], Rbox[:4]]
    ]

    return screen, start_box, report_r, report_l


def plot_trajectories(data, arena, Lbox, Rbox, Sbox):
    """
    Helper function that plots the trajectories of the mouse within the Unity game arena
    """

    episodes_df = data[data.ITI == 0].copy(deep=True)
    episode_nums = episodes_df.episode.unique()

    # Create a figure and axis
    _, ax = plt.subplots(figsize=(7, 5))
    plt.subplots_adjust(bottom=0.2)  # Make space for the button
    trajectory_index = [0]

    def update_plot(ep_num):
        ax.clear()
        trajectory = episodes_df[episodes_df.episode == ep_num]
        # reward = (
        #     True if ITIs_df[ITIs_df.episode == ep_num].reward.values[0] == 1 else False
        # )

        x = trajectory.x
        y = trajectory.y

        ax.plot(x, y, color="black", linewidth=4, alpha=0.3)

        [
            ax.scatter(
                x,
                y,
                marker=marker,
                color="black",
                s=100,
                alpha=0.5,
            )
            for x, y, marker in [
                [x.iloc[0], y.iloc[0], "o"],  # Start
                [trajectory.iloc[-1].x, trajectory.iloc[-1].y, "X"],  # End
            ]
        ]

        x_start_arena, x_end_arena, y_start_arena, y_end_arena = arena

        # Boundaries of the Unity arena
        ax.set_xlim(x_start_arena, x_end_arena)
        ax.set_ylim(y_start_arena, y_end_arena)

        # Generate and add active regions to the plot
        [
            ax.add_patch(patch)
            for patch in generate_active_regions(arena, Lbox, Rbox, Sbox)
        ]

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

    x_unity = [unity_arena_size[0], unity_arena_size[1]]
    x_image = [
        cropped_image[1],
        cropped_image[0],
    ]  # the y-axis is flipped for ergonomical reasons

    y_unity = [unity_arena_size[2], unity_arena_size[3]]
    y_image = [
        cropped_image[3],
        cropped_image[2],
    ]  # the y-axis is flipped for ergonomical reasons

    x_rects_upper, x_rects_lower = [
        np.interp(
            np.array([start_box[i], r_report_box[i], l_report_box[i]]), x_unity, x_image
        )
        for i in range(0, 2)
    ]

    y_rects_upper, y_rects_lower = [
        np.interp(
            np.array([start_box[i], r_report_box[i], l_report_box[i]]), y_unity, y_image
        )
        for i in range(2, 4)
    ]

    widths = x_rects_upper - x_rects_lower
    heights = y_rects_upper - y_rects_lower
    return x_rects_lower, y_rects_lower, widths, heights


def dict_to_data_frame(data: dict) -> pd.DataFrame:
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

    df = pd.DataFrame(
        data=data["action"].reshape(
            data["action"].shape[0],
            data["action"].shape[2],
        ),
        columns=["action_x", "action_y", "action_head_angle", "action_photodiode"],
    )
    df["episode"] = data["episode"]
    df["step"] = data["step"]
    df["step_time"] = data["step_time"]
    df[states] = data["state"]
    df["terminal"] = data["terminal"]
    df["reward"] = data["reward"]

    return df


def save_visual_observation(i, dec_steps, obs_specs, out_path):
    """
    Save visual observation as an image
    """
    for index, obs_spec in enumerate(obs_specs):
        if len(obs_spec.shape) == 3:
            # Check visual observation(s)
            for index, obs_spec in enumerate(obs_specs):
                if len(obs_spec.shape) == 3:
                    plt.imshow(np.moveaxis(dec_steps.obs[index][0, :, :, :], 0, -1))
                    plt.savefig(out_path)
                    plt.close()

                    # 1 stack | 3 channels | 256x256 pixels (=> specified in Unity)
                    vis_obs_shape = dec_steps.obs[index].shape

            # Check vector observation(s)
            for index, obs_spec in enumerate(obs_specs):
                if len(obs_spec.shape) == 1:
                    # Check that the vector observation has 13 elements (=> specified in Unity)
                    vec_obs_size = len(dec_steps.obs[index][0, :])

    return vis_obs_shape, vec_obs_size


def select_executable():
    # Open file dialog window to let user choose unity executable path
    root = tk.Tk()
    root.withdraw()
    game_path = filedialog.askopenfilename(title="Select game executable")
    root.destroy()
    return game_path
