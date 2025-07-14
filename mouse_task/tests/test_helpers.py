# Description: Helper functions for the mouse task tests

import os
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from tkinter import filedialog
from matplotlib.widgets import Button


def generate_patch(x_start, x_end, y_start, y_end):
    """Creates a patch (i.e. rectangle) to be displayed on pygame interface"""

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
    """Defines the active regions (starting box and report boxes)
    of the Unity game arena
    """

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
    """Plots the trajectories of the mouse within the Unity game arena."""

    # Create mask for episodes with ITI == 0
    mask = data["ITI"] == 0
    episodes_data = {k: v[mask] for k, v in data.items()}
    episode_nums = np.unique(episodes_data["episode"])

    # Create a figure and axis
    _, ax = plt.subplots(figsize=(7, 5))
    plt.subplots_adjust(bottom=0.2)
    trajectory_index = [0]

    def update_plot(ep_num):
        ax.clear()
        ep_mask = episodes_data["episode"] == ep_num
        x = episodes_data["x"][ep_mask]
        y = episodes_data["y"][ep_mask]

        ax.plot(x, y, color="black", linewidth=4, alpha=0.3)

        # Start and end markers
        ax.scatter(x[0], y[0], marker="o", color="black", s=100, alpha=0.5)
        ax.scatter(x[-1], y[-1], marker="X", color="black", s=100, alpha=0.5)

        x_start_arena, x_end_arena, y_start_arena, y_end_arena = arena
        ax.set_xlim(x_start_arena, x_end_arena)
        ax.set_ylim(y_start_arena, y_end_arena)

        # Add active regions
        for patch in generate_active_regions(arena, Lbox, Rbox, Sbox):
            ax.add_patch(patch)

        ax.set_title(f"Episode {ep_num}")
        ax.grid(True, alpha=0.3)
        plt.draw()

    # Function for the "Next" button
    def next_trajectory(_):
        trajectory_index[0] = (trajectory_index[0] + 1) % len(episode_nums)
        update_plot(episode_nums[trajectory_index[0]])

    # Function for the "Previous" button
    def prev_trajectory(_):
        trajectory_index[0] = (trajectory_index[0] - 1) % len(episode_nums)
        update_plot(episode_nums[trajectory_index[0]])

    # Buttons for switching trajectories
    axprev = plt.axes([0.1, 0.05, 0.1, 0.075])  # 'Previous' position
    axnext = plt.axes([0.8, 0.05, 0.1, 0.075])  # 'Next' position

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
    """Computes the coordinates of the trigger areas (start and report boxes)
    in the cropped image. Done by interpolating Unity arena coordinates
    to pygame window coordinates.
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

    # Reverse-interpolation to compute trigger areas on pygame
    # window from values specified in the ActiveSensingTask() class
    x_rects_upper, x_rects_lower = [
        np.interp(
            np.array([start_box[i], r_report_box[i], l_report_box[i]]),
            x_unity,
            x_image,
        )
        for i in range(0, 2)
    ]

    y_rects_upper, y_rects_lower = [
        np.interp(
            np.array([start_box[i], r_report_box[i], l_report_box[i]]),
            y_unity,
            y_image,
        )
        for i in range(2, 4)
    ]

    widths = x_rects_upper - x_rects_lower
    heights = y_rects_upper - y_rects_lower
    return x_rects_lower, y_rects_lower, widths, heights


def format_data(data: dict) -> dict:
    """Re-arranges data dictionary for easier downstream analysis"""

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

    # Initialize result dictionary
    result = {}

    # Handle action data - reshape and assign to columns
    action_reshaped = (
        data["action"]
        .reshape(
            data["action"].shape[0],
            data["action"].shape[2],
        )
        .astype(np.float64)
    )

    result["action_x"] = action_reshaped[:, 0]
    result["action_y"] = action_reshaped[:, 1]
    result["action_head_angle"] = action_reshaped[:, 2]
    result["action_photodiode"] = action_reshaped[:, 3]

    # Add other single columns as numpy arrays
    result["episode"] = np.array(data["episode"], dtype=np.int64)
    result["step"] = np.array(data["step"], dtype=np.int64)
    result["step_time"] = np.array(data["step_time"], dtype=np.float64)
    result["terminal"] = np.array(data["terminal"], dtype=bool)
    result["reward"] = np.array(data["reward"], dtype=np.int64)

    # Add state columns as numpy arrays
    for i, state_name in enumerate(states):
        # Convert boolean states to bool dtype
        if state_name in [
            "mouse_can_report",
            "ITI",
            "spawner_green_on_left",
            "mouse_report_correct",
            "mouseInLeft_box",
            "mouseInRight_box",
            "photodiode_sync_state",
            "photodiode_change_value",
        ]:
            result[state_name] = data["state"][:, i].astype(np.int64)
        else:
            result[state_name] = data["state"][:, i].astype(np.float64)

    return result


def save_visual_observation(i, dec_steps, obs_specs, out_path):
    """Saves visual observation as an image"""

    for index, obs_spec in enumerate(obs_specs):
        if len(obs_spec.shape) == 3:
            # Check visual observation(s)
            for index, obs_spec in enumerate(obs_specs):
                if len(obs_spec.shape) == 3:
                    plt.imshow(
                        np.moveaxis(dec_steps.obs[index][0, :, :, :], 0, -1),
                    )
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


def select_executable(msg: str = "Select executable") -> str:
    """Opens tkinter file dialog window to allow user to select Unity executable"""

    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=msg)
    root.destroy()
    return path


def prompt_save_trajectories(parent_dir, default_name="test_trajectories.npy"):
    """Prompts user to choose the name for the trajectories' .npy file"""

    root = tk.Tk()
    root.withdraw()

    out_path = filedialog.asksaveasfilename(
        initialdir=parent_dir,
        title="Save trajectory file as...",
        defaultextension=".npy",
        filetypes=[("NumPy files", "*.npy")],
        initialfile=default_name.split(".")[0],
    )

    # Ensure .npy extension
    if out_path and not out_path.endswith(".npy"):
        out_path += ".npy"

    # If user cancels, keep default name and append index
    if not out_path:
        base, ext = os.path.splitext(default_name)
        i = 1
        while True:
            candidate = os.path.join(parent_dir, f"{base}_{i}{ext}")
            if not os.path.exists(candidate):
                out_path = candidate
                break
            i += 1

    return out_path
