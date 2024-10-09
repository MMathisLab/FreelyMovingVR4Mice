import pathlib
import warnings
from typing import Dict

import matplotlib.pyplot as plt
import seaborn as sns
import vr4mice.analysis.analysis as analysis
import vr4mice.analysis.plotting as plotting
import vr4mice.analysis.utils as utils
from vr4mice.schema import base_analysis, vr4mice
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


# Filter out the UserWarning related to the deprecated features
warnings.filterwarnings("ignore", category=UserWarning)


def fetch_data(key: Dict, database: bool):
    """Fetch the data to compute the summary plot on.

    Args:
        key (dict): A dictionary that specifies which dataset to generate a
            summary plot for.
        database (bool): If True, fetches and populates the data, else gets
            the corresponding table direcly. Defaults to True.

    Returns:
        The `pd.DataFrame` containing the session features (first return)
        and the `pd.DataFrame` containing the rig's dimensions (second return).

    """
    # Fetch or populate to get df (externalize)
    if database:
        from vr4mice.schema import base_analysis

        try:
            df = base_analysis.DataFrame().get_data(key)
            
            flag = df is False
            if not flag:
                logger.info("Data fetched for " + str(key))
            else:
                logger.info("Populating DataFrame data for " + str(key))
                df = base_analysis.DataFrame().populate(key)
                df = base_analysis.DataFrame().get_data(key)
                flag = df is False
                if not flag:
                    logger.info("Data populated and fetched for " + str(key))

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
        df, interp = analysis.create_data_frame(key, iti=False)
        box_df_output = analysis.get_box_df(key, df, interp=interp)

    return df, box_df_output


def get_path(key: Dict, base: str, ext: str = ".png") -> pathlib.Path:
    """Create the name of the summary plot file.

    Format is {dataset_name}_summary_plot.{ext}

    Args:
        key (Dict): A dictionnary containing the key of the session.
        base (str): Save folder to save the summary plot to.
        ext (str): Extension of the file to save the summary plot to.
            Default to '.png'.

    Returns:
        The path to save the summary plot to.

    """
    name = str(key["dataset"]) + "_summary_plot" + ext
    return pathlib.Path(base) / name


def get_subtitle(key: Dict, task_name: str = "AR Task"):
    """Create the title of the summary plot.

    Args:
        key (Dict): A dictionnary containing the key of the session.
        task_name (str): Name of the task for which the summary plot is generated.

    Returns:
        The title of the summary plot.
    """
    # TODO: add parcing of filename
    return task_name + ": Dataset: " + str(key["dataset"])


def vr4mice_summary_plots(
    key: Dict, save_path: str = "/data/summary_plots", database: bool = True
):
    """
    Generate a summary plot for a given dataset.

    final results to email
    [DJ SummaryPlot table: path?]

    Args:
        key (dict): A dictionary that specifies which dataset to generate a
            summary plot for.
        save_path (str, optional): The directory path where the summary plot
            should be saved. Defaults to "/data/summary_plots".
        database (bool): If True, fetches and populates the data, else gets
            the corresponding table directly. Defaults to True.

    Returns:
        str: The full path of the saved summary plot.
    """
    
    plotting.get_rc_params()
    df, box_df_output = fetch_data(key, database)
    
    df = df.infer_objects()
    df["dataset"] = key["dataset"]
    df ["trial_rewarded"] = analysis.get_rewarded(df)
    
    df = df[df.iti == 0].copy()

    print(df.columns)

    # NOTE: so that the head_dir is align to the screen
    df["head_dir"] = ((df.head_dir) + 180) % 360 - 180

    num_apertures = len(df.aperture.unique())

    # Create the summary figure grid
    fig = plt.figure(figsize=(25, 20), constrained_layout=True)
    gs = plt.GridSpec(6, 10, figure=fig)

    ax1 = fig.add_subplot(gs[0:2, 0:3])
    ax2 = fig.add_subplot(gs[0:2, 3:5])
    ax3 = fig.add_subplot(gs[0:2, 5:7])
    ax10 = fig.add_subplot(gs[0:2, 7:10])

    ax5 = fig.add_subplot(gs[2, 0:2])
    ax6 = fig.add_subplot(gs[2, 2:4])
    time_plots_aperture = fig.add_subplot(gs[2, 4:6])
    time_plots_reward = fig.add_subplot(gs[2, 6:8])
    time_plots_choice = fig.add_subplot(gs[2, 8:10])

    velocity_plot_aperture = fig.add_subplot(gs[3, 0:2])
    velocity_plot_reward = fig.add_subplot(gs[3, 2:4])
    velocity_plot_choice = fig.add_subplot(gs[3, 4:6])
    heading_angle_plot = fig.add_subplot(gs[3, 6:8])
    j_shaped_plot = fig.add_subplot(gs[3, 8:10])

    ax7 = fig.add_subplot(gs[4, 0:2])
    ax8 = fig.add_subplot(gs[4, 2:])
    ax4 = fig.add_subplot(gs[5, 0:2])
    ax9 = fig.add_subplot(gs[5, 2:])

    ## Display all trials
    plotting.plot_session(
        df=df,
        df_box=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=ax1,
    )

    ## Display all rewarded trials on left side
    plotting.plot_session(
        df=df[(df.trial_rewarded == 1) & (df.trial_left_choice == 1)],
        df_box=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=ax2,
    )

    ## Display all rewarded trials on right side
    plotting.plot_session(
        df=df[(df.trial_rewarded == 1) & (df.trial_right_choice == 1)],
        df_box=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=ax3,
    )

    ## Display mean trajectory for the j-shaped trials
    j_shaped_df = analysis.get_jshaped_trials(df).copy()
    j_shaped_df = utils.create_bins(
        data=j_shaped_df, spatial_ybins=[6.75, 20, 25], label="y"
    )
    plotting.lineplot_flip_axis(
        data=j_shaped_df,
        x="bin_centers",
        y="x",
        hue="choice" if num_apertures <= 2 else "aperture",
        palette=plotting.colors_choice if num_apertures <= 2 else "viridis",
        style="aperture" if num_apertures <= 2 else "choice",
        errorbar="se",
        ax=ax10,
    )
    ax10.set_xlim([-15, 15])
    ax10.set_ylabel("y position (cm)")
    ax10.set_xlabel("x position (cm)")

    ## Display the choice rate
    plotting.plot_rate(
        df=df,
        label_x="trial_left_choice",
        per_aperture=True if num_apertures >= 2 else False,
        ax=ax4,
    )
    ax4.set_ylabel("Prob(Left Choice)")
    ax4.set_ylim([0, 1])

    ## Display the target location rate
    plotting.plot_rate(
        df=df,
        label_x="object_on_left",
        per_aperture=True if num_apertures >= 2 else False,
        ax=ax5,
    )
    ax5.set_ylabel("Prob(Target on Left)")
    ax5.set_ylim([0, 1])

    ## Display trial count
    plotting.plot_trial_count(
        df=df,
        per_aperture=True if num_apertures >= 2 else False,
        ax=ax6,
    )

    ## Display the reward rate
    plotting.plot_rewards(
        df=df, per_aperture=True if num_apertures >= 2 else False, ax=ax7
    )

    ## Display the time to reward
    # per aperture
    plotting.plot_time_to_reward(
        df,
        label_x="aperture",
        xticks=list(df.aperture.unique()),
        ax=time_plots_aperture,
    )
    # per trial rewarded
    plotting.plot_time_to_reward(
        df,
        label_x="trial_rewarded",
        xticks=["Uncorrect", "Correct"],
        ax=time_plots_reward,
    )
    # per choice
    plotting.plot_time_to_reward(
        df, label_x="trial_right_choice", xticks=["Left", "Right"], ax=time_plots_choice
    )

    # Interpolation on variable of interest
    columns = [
        "y",
        "head_dir",
        "trial_tortuosity",
        "trial_duration",
        "x",
        "aperture",
        "velocity",
        "velocity_x",
        "velocity_y",
        "trial_traj_path_length",
        "flip_one_side",
    ]

    interpolated_df = utils.interpolate(
        df,
        n_points=200,
        value_columns=["trial_left_choice", "trial_right_choice", "trial_rewarded"]
        + columns,
    )
    interpolated_df["trial_step"] = interpolated_df.groupby(
        ["dataset", "trial"]
    ).trial.cumcount()
    interpolated_df["trial_length"] = interpolated_df["trial_step"] / 200

    ## Display the speed
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=(plotting.colors_aperture[:2] if num_apertures == 2 else "viridis"),
        hue="aperture",
        errorbar="se",
        ax=velocity_plot_aperture,
    )
    velocity_plot_aperture.legend([], [], frameon=False)
    velocity_plot_aperture.set_ylabel("Speed / Aperture")
    velocity_plot_aperture.set_xlabel("Trial progression")
    # per trial rewarded
    
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=plotting.colors_rewarded,
        hue="trial_rewarded",
        errorbar="se",
        ax=velocity_plot_reward,
    )
    velocity_plot_reward.legend([], [], frameon=False)
    velocity_plot_reward.set_ylabel("Speed / Reward")
    velocity_plot_reward.set_xlabel("Trial progression")
    
    # per choice
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=plotting.colors_choice,
        hue="trial_left_choice",
        errorbar="se",
        ax=velocity_plot_choice,
    )
    velocity_plot_choice.legend([], [], frameon=False)
    velocity_plot_choice.set_ylabel("Speed / Choice")
    velocity_plot_choice.set_xlabel("Trial progression")

    ## Display heading direction per choice
    
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="head_dir",
        hue="trial_right_choice" if num_apertures <= 2 else "aperture",
        palette=plotting.colors_choice if num_apertures <= 2 else "viridis",
        style="aperture" if num_apertures <= 2 else "trial_right_choice",
        errorbar="se",
        ax=heading_angle_plot,
    )
    heading_angle_plot.legend([], [], frameon=False)
    heading_angle_plot.set_ylabel("Heading direction")
    heading_angle_plot.set_xlabel("Trial progression")

    ## Display J-shaped trials rate
    plotting.plot_rate(
        df=df,
        label_x="is_j_shaped",
        per_aperture=True if num_apertures >= 2 else False,
        ax=j_shaped_plot,
    )
    j_shaped_plot.set_ylabel("J-shaped trials rate")
    j_shaped_plot.set_ylim([0, 1])

    ## Display rolling reward and choice
    plotting.plot_rolling_reward(df, ax=ax8)
    plotting.plot_choices_by_trial(df, ax=ax9)

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
    plt.tight_layout()
    plt.savefig(full_path)
    plt.close()

    return full_path
