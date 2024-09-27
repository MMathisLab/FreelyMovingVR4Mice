from IPython.display import HTML

import matplotlib.pyplot as plt
import numpy as np
from analysis.dlc_helpers import dlc_interpolate, dlc_savgol_filter, filter_dlc
from matplotlib.animation import FuncAnimation


def plot_frame_keypoints(dlc_dict, frame_number=1, heading_direction=None):
    body_parts = dlc_dict.columns.get_level_values(0).unique()[:-2]
    mean_x, mean_y = 0, 0
    total_likelihood = 0

    for b in body_parts:
        key_point = dlc_dict[b].iloc[frame_number]
        plt.scatter(key_point.x, key_point.y, alpha=key_point.likelihood)

        # Calculate the weighted mean based on the likelihood
        # mean_x += key_point.x * key_point.likelihood
    # mean_y += key_point.y * key_point.likelihood
    # total_likelihood += key_point.likelihood

    """if total_likelihood > 0:
        mean_x /= total_likelihood
        mean_y /= total_likelihood
        
        if heading_direction is not None:
            # Assuming heading_direction is a tuple (dx, dy) for the arrow direction
            plt.arrow(mean_x, mean_y, heading_direction[0], heading_direction[1],
                      width=0.5, color='r', length_includes_head=True)"""

    plt.xlim(0, 700)
    plt.ylim(0, 700)
    plt.show()


# Assuming the structure of dlc_dict and orig allows indexing like dlc_dict[body_part]['x'][frame_number]


def plot_on_subplot(ax, data_dict, frame_number, heading_direction):
    # Assuming body_parts and their properties (x, y, likelihood) can be accessed like this
    body_parts = data_dict.columns.get_level_values(0).unique()[
        :-2
    ]  # Example body parts
    for b in body_parts:
        # Example of accessing the x, y, likelihood for a body part at a given frame
        # Adjust this to match how your data is structured
        x = data_dict[b]["x"][frame_number]
        y = data_dict[b]["y"][frame_number]
        likelihood = data_dict[b]["likelihood"][
            frame_number
        ]  # Example of accessing likelihood
        ax.scatter(
            x, y, alpha=likelihood, c=likelihood, vmin=0, vmax=1
        )  # Plot with alpha based on likelihood

    # Example of adding an arrow for heading direction
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


def update_plots(frame_number, dlc_dict, orig, axs, heading_direction=(10, 5)):
    axs[0].clear()  # Clear previous plots
    axs[1].clear()
    print(frame_number)

    # Update plots for current frame
    plot_on_subplot(axs[0], dlc_dict, frame_number, heading_direction)
    axs[0].set_title("Modified Data")
    plot_on_subplot(axs[1], orig, frame_number, heading_direction)
    axs[1].set_title("Original Data")


def make_animated_movie(
    dlc_data,
    frames=[1, 500, 10],
    cutoff=0.3,
    window_length=9,
    polyorder=3,
    path="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_animation.mp4",
):
    # Initialize figure and axes
    fig, axs = plt.subplots(1, 2, figsize=(10, 5))

    orig = dlc_data.copy()
    filt_dlc = filter_dlc(
        dlc_data.copy(), cutoff=cutoff, window_length=window_length, polyorder=polyorder
    )
    # Setup animation
    ani = FuncAnimation(
        fig,
        update_plots,
        frames=range(frames[0], frames[1], frames[2]),
        fargs=(filt_dlc, orig, axs),
        interval=10,
    )

    # Display in Jupyter notebook
    # HTML(ani.to_jshtml())
    # To display the animation in a Jupyter notebook
    # HTML(ani.to_jshtml())
    # Or to save the animation as a file
    ani.save(path, fps=10, extra_args=["-vcodec", "libx264"])


# Your existing function, slightly modified to fit into the animation framework
def plot_dlc_heading_direction(ax, df, computed_dlc, frame):
    # plot_dlc_heading_direction(ax, dlc_s.iloc[:,:].copy(), dlc_var, frame=6000)
    # plt.xlim(0,700)
    # plt.ylim(0,700)
    # Clear previous frame
    ax.clear()

    # Set axis properties
    ax.set_xlabel("X coordinate")
    ax.set_ylabel("Y coordinate")
    ax.set_xlim(0, 700)
    ax.set_ylim(0, 700)
    ax.axis("equal")

    # Compute the heading direction for the current frame
    row = df.iloc[frame]
    computed_row = computed_dlc.iloc[frame]

    # Ensure heading direction is in radians
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


# Function to animate each frame
def update(frame, ax, df, computed_dlc):
    print(frame)
    plot_dlc_heading_direction(ax, df, computed_dlc, frame)


def create_animation_dlc_w_heading_angle(df, computed_dlc, frames):
    # df is the dlc key points, computed dlc is the head angle table and frames is a range of frames
    # ani = create_animation(dlc_s.iloc[:,:].copy(), dlc_var, frames=range(0,5000))
    # ani.save(save_path + 'dlc_heading_animation.mp4', writer='ffmpeg', fps=50)
    fig, ax = plt.subplots(figsize=(10, 6))
    ani = FuncAnimation(
        fig, update, frames=frames, fargs=(ax, df, computed_dlc), interval=50
    )
    plt.close(fig)  # Prevents the final static plot from showing up
    return ani
