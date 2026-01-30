import pathlib
import warnings

from typing import Dict


import matplotlib.pyplot as plt
import seaborn as sns

from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


# Filter out the UserWarning related to the deprecated features
warnings.filterwarnings("ignore", category=UserWarning)


def fetch_data(key: Dict, database: bool):
    """Fetch the data to compute the summary plot on.

    Args:
        key (dict): A dictionary that specifies which dataset to generate a
            summary plot for. Format: `{"dataset": "dataset name"}`
        database (bool): If True, fetches and populates the data, else gets
            the corresponding table direcly. Defaults to True.

    Returns:
        The `pd.DataFrame` containing the session features (first return)
        and the `pd.DataFrame` containing the rig's dimensions (second return).

    """
    if database:
        from vr4mice.schema import base_analysis

        logger.info(f"Trying to get data from database...")

        try:
            df = base_analysis.DataFrame().get_data(key)

            if df is not False or df is not None:
                logger.info(f"Data fetched for {key}")
            else:
                logger.info(f"Populating DataFrame data for {key}")
                df = base_analysis.DataFrame().populate(key)
                df = base_analysis.DataFrame().get_data(key)
                if df is not False or df is not None:
                    logger.info(f"Data populated and fetched for {key}")
                else:
                    logger.warning(f"Data population failed for {key}")

            logger.info(f"Add trial rewarded...")
            df["trial_rewarded"] = base_analysis.DataFrame().get_rewarded(key)

        except Exception as e:
            logger.warning(f"An error occurred: {e}")

        try:
            box_df_output = base_analysis.BoxDataFrame().get_data(key)
            if box_df_output is not False or box_df_output is not None:
                logger.info(f"Box data fetched for {key}")
            else:
                logger.info(f"Populating BoxDataFrame data for {key}")
                box_df_output = base_analysis.BoxDataFrame().populate(key)
                box_df_output = base_analysis.BoxDataFrame().get_data(key)
                if box_df_output is not False or box_df_output is not None:
                    logger.info("Data populated and fetched for " + str(key))
                else:
                    logger.warning(f"Data population failed for {key}")
        except Exception as e:
            logger.warning(f"An error occurred: {e}")
    else:
        from vr4mice.analysis import analysis

        df, unity_to_physical_arena_size = analysis.create_data_frame(key, iti=False)
        df["trial_rewarded"] = analysis.get_rewarded(df)
        box_df_output = analysis.get_box_df(
            key, df, unity_to_physical_arena_size=unity_to_physical_arena_size
        )

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
    from vr4mice.analysis import analysis, plotting, utils
    from vr4mice.schema.vr4mice import GuiParams

    analysis.style()
    df, box_df_output = fetch_data(key, database)

    df = df.infer_objects()
    df["dataset"] = key["dataset"]

    df = df[df.iti == 0].copy()

    # NOTE(tom): so that the head_dir is aligned to the screen
    df["head_dir"] = ((df.head_dir) + 180) % 360 - 180

    # NOTE(tom): ensure that if the occluder is not displayed (as in training data) that there are no
    # multiple apertures (ie multiple occlusion might be defined but not used)
    if (GuiParams() & key).fetch("occlusion_type_param") == 0.0:
        df["aperture"] = 0

    num_apertures = len(df.aperture.unique())

    # Create the summary figure grid
    fig = plt.figure(figsize=(25, 20), constrained_layout=True)
    gs = fig.add_gridspec(6, 10)

    subplot_specs = {
        "all_trials": gs[0:2, 0:3],
        "left_rewarded": gs[0:2, 3:5],
        "right_rewarded": gs[0:2, 5:7],
        "j_mean": gs[0:2, 7:10],
        "target_rate": gs[2, 0:2],
        "trial_count": gs[2, 2:4],
        "time_aperture": gs[2, 4:6],
        "time_reward": gs[2, 6:8],
        "time_choice": gs[2, 8:10],
        "vel_aperture": gs[3, 0:2],
        "vel_reward": gs[3, 2:4],
        "vel_choice": gs[3, 4:6],
        "heading": gs[3, 6:8],
        "j_rate": gs[3, 8:10],
        "rewards": gs[4, 0:2],
        "rolling_reward": gs[4, 2:],
        "choice_rate": gs[5, 0:2],
        "choices_by_trial": gs[5, 2:],
    }

    axes = {name: fig.add_subplot(spec) for name, spec in subplot_specs.items()}

    # Display all trials
    plotting.plot_session(
        df=df,
        box_df=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=axes["all_trials"],
    )
    axes["all_trials"].set_title("All Trials (no ITI)")

    # Display all rewarded trials on left side
    plotting.plot_session(
        df=df[(df.trial_rewarded == 1) & (df.trial_left_choice == 1)],
        box_df=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=axes["left_rewarded"],
    )
    axes["left_rewarded"].set_title("Left Rewarded Trials (no ITI)")

    # Display all rewarded trials on right side
    plotting.plot_session(
        df=df[(df.trial_rewarded == 1) & (df.trial_right_choice == 1)],
        box_df=box_df_output,
        per_aperture=False,
        per_side=True,
        ax=axes["right_rewarded"],
    )
    axes["right_rewarded"].set_title("Right Rewarded Trials (no ITI)")

    # Display mean trajectory for the j-shaped trials
    j_shaped_df = analysis.get_jshaped_trials(df).copy()
    j_shaped_df = utils.create_bins(
        data=j_shaped_df, spatial_ybins=[6.75, 20, 25], label="y"
    )
    plotting.lineplot_flip_axis(
        data=j_shaped_df,
        x="bin_centers",
        y="x",
        hue="trial_right_choice" if num_apertures <= 2 else "aperture",
        palette=plotting.colors_choice if num_apertures <= 2 else "viridis",
        style="aperture" if num_apertures <= 2 else "trial_right_choice",
        errorbar="se",
        ax=axes["j_mean"],
    )
    axes["j_mean"].set_xlim([-15, 15])
    axes["j_mean"].set_ylabel("y position (cm)")
    axes["j_mean"].set_xlabel("x position (cm)")

    # Display the choice rate
    plotting.plot_rate(
        df=df,
        label_x="trial_left_choice",
        per_aperture=True if num_apertures >= 2 else False,
        ax=axes["choice_rate"],
    )
    axes["choice_rate"].set_ylabel("Prob(Left Choice)")
    axes["choice_rate"].set_ylim([0, 1])
    axes["choice_rate"].hlines(
        0.5,
        xmin=axes["choice_rate"].get_xlim()[0],
        xmax=axes["choice_rate"].get_xlim()[1],
        colors="gray",
        linestyles="dashed",
    )

    # Display the target location rate
    plotting.plot_rate(
        df=df,
        label_x="object_on_left",
        per_aperture=True if num_apertures >= 2 else False,
        ax=axes["target_rate"],
    )
    axes["target_rate"].hlines(
        0.5,
        xmin=axes["target_rate"].get_xlim()[0],
        xmax=axes["target_rate"].get_xlim()[1],
        colors="gray",
        linestyles="dashed",
    )
    axes["target_rate"].set_ylabel("Prob(Target on Left)")
    axes["target_rate"].set_ylim([0, 1])

    # Display trial count
    plotting.plot_trial_count(
        df=df,
        per_aperture=True if num_apertures >= 2 else False,
        ax=axes["trial_count"],
    )
    axes["trial_count"].hlines(
        y=125,
        xmin=axes["trial_count"].get_xlim()[0],
        xmax=axes["trial_count"].get_xlim()[1],
        colors="purple",
        linestyles="dashed",
    )

    # Display the reward rate
    plotting.plot_rewards(
        df=df,
        per_aperture=True if num_apertures >= 2 else False,
        ax=axes["rewards"],
    )
    axes["rewards"].hlines(
        0.7,
        xmin=axes["rewards"].get_xlim()[0],
        xmax=axes["rewards"].get_xlim()[1],
        colors="purple",
        linestyles="dashed",
    )

    # Display the time to reward
    # 1: per aperture
    plotting.plot_time_to_reward(
        df,
        label_x="aperture",
        xticks=list(df.aperture.astype(float).sort_values().astype(str).unique()),
        ax=axes["time_aperture"],
    )
    axes["time_aperture"].set_ylabel("Trial Duration / Occl")
    # 2: per trial rewarded
    plotting.plot_time_to_reward(
        df,
        label_x="trial_rewarded",
        xticks=["Incorrect", "Correct"],
        ax=axes["time_reward"],
    )
    axes["time_reward"].set_ylabel("Trial Duration / Reward")
    # 3: per choice
    plotting.plot_time_to_reward(
        df,
        label_x="trial_right_choice",
        xticks=["Left", "Right"],
        ax=axes["time_choice"],
    )
    axes["time_choice"].set_ylabel("Trial Duration / Choice")

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
        value_columns=["trial_right_choice", "trial_rewarded"] + columns,
    )
    interpolated_df["trial_step"] = interpolated_df.groupby(
        ["dataset", "trial"]
    ).trial.cumcount()
    interpolated_df["trial_length"] = interpolated_df["trial_step"] / 200

    # Display the speed
    # 1: per aperture
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=(plotting.colors_aperture[:2] if num_apertures == 2 else "viridis"),
        hue="aperture",
        errorbar="se",
        ax=axes["vel_aperture"],
    )
    axes["vel_aperture"].set_ylabel("Speed / Aperture")
    axes["vel_aperture"].set_xlabel("Trial progression")

    # 2: per trial rewarded
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=plotting.colors_rewarded,
        hue="trial_rewarded",
        errorbar="se",
        ax=axes["vel_reward"],
    )
    axes["vel_reward"].set_ylabel("Speed / Reward")
    axes["vel_reward"].set_xlabel("Trial progression")

    # 3: per choice
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="velocity",
        palette=plotting.colors_choice,
        hue="trial_right_choice",
        errorbar="se",
        ax=axes["vel_choice"],
    )
    axes["vel_choice"].set_ylabel("Speed / Choice")
    axes["vel_choice"].set_xlabel("Trial progression")

    # Display heading direction per choice
    sns.lineplot(
        data=interpolated_df,
        x="trial_length",
        y="head_dir",
        hue="trial_right_choice" if num_apertures <= 2 else "aperture",
        palette=plotting.colors_choice if num_apertures <= 2 else "viridis",
        style="aperture" if num_apertures <= 2 else "trial_right_choice",
        errorbar="se",
        ax=axes["heading"],
    )
    axes["heading"].set_ylabel("Heading direction")
    axes["heading"].set_xlabel("Trial progression")

    # Display J-shaped trials rate
    plotting.plot_rate(
        df=df,
        label_x="is_j_shaped",
        per_aperture=True if num_apertures >= 2 else False,
        ax=axes["j_rate"],
    )
    axes["j_rate"].set_ylabel("J-shaped trials rate")
    axes["j_rate"].set_ylim([0, 1.1])

    # Display rolling reward and choice
    plotting.plot_rolling_reward(
        df,
        ax=axes["rolling_reward"],
        per_aperture=True if num_apertures >= 2 else False,
    )
    plotting.plot_choices_by_trial(df, ax=axes["choices_by_trial"])

    if database:
        from vr4mice.schema import base_analysis

        full_path = base_analysis.SummaryPlots().get_path(
            key=key, base=save_path, ext=".png"
        )
        subtitle = base_analysis.SummaryPlots().get_subtitle(
            key=key, task_name="AR Task"
        )
    else:
        full_path = get_path(key=key, base=save_path, ext=".png")
        subtitle = get_subtitle(key=key, task_name="AR Task")

    # Despine all axes for cleaner aesthetics
    for ax in axes.values():
        sns.despine(ax=ax, offset=10)

    # Set title and adjust layout to prevent overlap
    fig.suptitle(subtitle, fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    plt.savefig(full_path)
    plt.close()

    return full_path
