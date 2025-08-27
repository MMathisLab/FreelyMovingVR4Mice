import copy
from typing import List, Optional, Tuple, Union

import matplotlib as mpl
import matplotlib.axes
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import sklearn
import sklearn.model_selection
import sklearn.preprocessing

from vr4mice.analysis import plotting


model_labels = [
    "x",
    "y",
    "velocity_x",
    "velocity_y",
    "heading_dir_sin",
    "heading_dir_cos",
    "head_angle_sin",
    "head_angle_cos",
    "trial_tortuosity",
    # "trial_duration",
    # "aperture",
    "trial_rewarded",
    "trial_length",
]

clean_model_labels = [
    "x position",
    "y position",
    "x velocity",
    "y velocity",
    "sin(running direction)",
    "cos(running direction)",
    "sin(head-body angle)",
    "cos(head-body angle)",
    "Trial tortuosity",
    "Trial rewarded",
    "Trial progression",
]


def predict_decision(
    df,
    label: Union[List[str]] = "norm_x",
    n_splits: int = 10,
    per_mouse: bool = True,
    max_iter: int = 100,
    scale_data: bool = True,
) -> Tuple[pd.DataFrame, npt.NDArray]:
    """Predict the animal's decision based on the `label` data, through a logistic regression.

    Args:
        df: The dataframe.
        label: The name of the column in the `df` dataframe.
        n_splits: The number of splits fo the cross validation.
        per_mouse: If `True` split the data per session, else split
            randomly across all sessions. If per_mouse, we train on
            all sessions but one, and test on the left out session.
        scale_data: If `True`, standardize the data before fitting the model.

    Returns:
        The initial dataframe with an extra `pred` column, containing the probability that the
        animal went to the right.

    Example:
        ```
        label = ["norm_x", "y", "heading_dir", "head_angle", "trial_tortuosity", "trial_init_x",
                "trial_length", "trial_init_y", "aperture"]
        df["aperture"] = (df["aperture"] > 7).astype(int)
        df, clf = regression.predict_decision(df, label=label)
        names = ["x", "y", "head", "body",  "tort", "init_x", "length", "init_y", "aperture"]
        plt.figure(figsize=(20,8))
        plt.bar(names, clf.coef_[0,:])
        ```
    """

    data = df[label].values
    labels = df.trial_left_choice.values

    if not isinstance(label, list):
        data = data.reshape(-1, 1)
    pred = np.empty((data.shape[0], 2))
    scores = np.empty((data.shape[0]))
    model = sklearn.linear_model.LogisticRegression(max_iter=max_iter)

    if scale_data:
        data = sklearn.preprocessing.StandardScaler().fit_transform(data)

    if per_mouse:
        sessions = df.dataset.values
        coefs = np.empty((len(np.unique(sessions)), len(label) + 1))

        logo = sklearn.model_selection.LeaveOneGroupOut()
        for i, (train_index, test_index) in enumerate(
            logo.split(data, labels, sessions)
        ):
            model.fit(data[train_index], labels[train_index])
            pred[test_index] = model.predict_proba(data[test_index])
            scores[test_index] = model.predict(data[test_index]) == labels[test_index]

            # Coeffs
            coefs[i] = np.concatenate([[model.intercept_[0]], model.coef_[0]])

    else:
        kf = sklearn.model_selection.KFold(n_splits=n_splits)
        for i, (train_index, test_index) in enumerate(kf.split(data)):
            model.fit(data[train_index], labels[train_index])
            pred[test_index] = model.predict_proba(data[test_index])
            scores[test_index] = model.predict(data[test_index]) == labels[test_index]

    ret = copy.deepcopy(df)
    ret.loc[:, "accuracy"] = scores
    ret.loc[:, "proba_left"] = pred[:, 1]

    return ret, coefs


def _find_decision_point_per_trial(
    trial_data: pd.DataFrame, threshold_uncertainty: float
) -> pd.DataFrame:
    """Find the threshold-based decision point for a single trial.

    Args:
        trial_data: Single trial data.
        threshold_uncertainty: Distance of the threshold to respectively 1 or 0.

    Returns:
        The row of the decision point sample.
    """
    threshold_right = 1 - threshold_uncertainty
    threshold_left = threshold_uncertainty

    # Filter values above the threshold
    if all(trial_data["trial_left_choice"] > 0.5):
        above_threshold = trial_data[trial_data["proba_left"] > threshold_right]
    else:
        above_threshold = trial_data[trial_data["proba_left"] < threshold_left]

    for index in above_threshold.index:
        subsequent_values = trial_data.loc[index:]["proba_left"]
        if all(trial_data["trial_left_choice"] > 0.5) and all(
            subsequent_values >= above_threshold.loc[index, "proba_left"]
        ):
            # Returning the step of the decision point
            return trial_data.loc[index]
        elif all(trial_data["trial_left_choice"] < 0.5) and all(
            subsequent_values <= above_threshold.loc[index, "proba_left"]
        ):
            return trial_data.loc[index]


def find_decision_point(
    df: pd.DataFrame, threshold_uncertainty: float = 0.3
) -> pd.DataFrame:
    """Find the threshold-based decision point for all trials.

    Args:
        df: Data for all trials, all sessions.
        threshold_uncertainty: Distance of the threshold to respectively 1 or 0.

    Returns:
        The rows of all the decision points for each trial.

    Example:
        ```
        decision_point = regression.find_decision_point_proba(df, threshold_uncertainty=0.3)
        ```

    """
    decision_point = df.groupby(["dataset", "trial"], as_index=False).apply(
        lambda x: _find_decision_point_per_trial(x, threshold_uncertainty)
    )
    return decision_point


def plot_decision_points_on_trajectory(
    df: pd.DataFrame,
    box_df: pd.DataFrame,
    decision_point: Optional[pd.DataFrame] = None,
    color: str = "deeppink",
    trials: List[int] = list(range(25, 30)),
    ax: Optional[matplotlib.axes.Axes] = None,
    cmap: str = "PuOr",
):
    """Plots decision points on the trial trajectories.

    Args:
        df (pd.DataFrame): DataFrame containing trajectory data. Note that it should only
            contain data from one session.
        box_df (pd.DataFrame): DataFrame containing the position of the reward, and start
            boxes to be displayed on the plot.
        decision_point (Optional[pd.DataFrame]): DataFrame containing the decision points
            per trial. Defaults to None if decision points are not to be plotted.
        color (str): Color for plotting the decision points. Default is "deeppink".
        trials (List[int]): List of trial numbers to plot. Defaults to a range from 25 to 30.
        ax (Optional[matplotlib.axes.Axes]): Matplotlib axis to plot on. If not provided, a
            new figure and axis are created. Defaults to None.
        cmap (str): Colormap to be used for displaying trial trajectories considering a
            given parameter (fixed to "proba_left"). Default is "PuOr".

    Example:
        ```
        fig = plt.figure(figsize=(15, 15), constrained_layout=True)
        gs = plt.GridSpec(3, 5, figure=fig)
        ax = fig.add_subplot(gs[:2, :])

        colors = ["red", "blue", "green", "purple", "orange"]

        for i, thr in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
            print("-->", thr)
            ax2 = fig.add_subplot(gs[2, i])
            decision_point = df.groupby(["dataset", "trial"], as_index=False).apply(
                lambda x: regression._find_decision_point_per_trial(x, thr)
            )
            regression.plot_decision_points_on_trajectory(
                df, box_df, decision_point, color=colors[i], ax=ax, trials=list(range(10, 20))
            )
            regression.pair_plot(decision_point, ax=ax2)

        ```
    """

    if len(df.dataset.unique()) > 1:
        raise ValueError(
            f"Only one session should be provided, {len(df.dataset.unique())} were provided."
        )

    if ax is None:
        fig = plt.figure(figsize=(8, 7), constrained_layout=True)
        gs = plt.GridSpec(1, 1, figure=fig)
        ax = fig.add_subplot(gs[0, 0])

    plotting.plot_all_boxes(ax=ax, box_df=box_df)
    ax.set_xlim(-26, 26)
    ax.set_ylim(-26, 26)

    for idx_trial, trial in df.groupby("trial"):
        if idx_trial in trials:
            trial = trial.reset_index(drop=True)
            plotting._plot_parameter_on_trial_traj(
                trial, (0, 1), "proba_left", "x", "y", cmap, 1, ax
            )

            if decision_point is not None:
                mpl.rcParams["lines.markersize"] = 8
                ax.scatter(
                    decision_point[decision_point["trial"] == idx_trial]["x"],
                    decision_point[decision_point["trial"] == idx_trial]["y"],
                    color=color,
                    zorder=100,
                )

            ax.legend([], [], frameon=False)
        else:
            continue


# NOT USING THE MODEL, DECISION POINT BASED ON VALUE OF A GIVEN VARIABLE -- NOT USED


def find_decision_point_from_distance(trial_data: pd.DataFrame, box_df: pd.DataFrame):
    """from distance to reward."""
    # NOTE(celia): not used for now.
    if all(trial_data["trial_left_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        trial_data["dist"] = np.sqrt(
            (box_df["right_reward_x"] - trial_data["x"]) ** 2
            + (box_df["right_reward_z"] - trial_data["y"]) ** 2
        )

    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        trial_data["dist"] = np.sqrt(
            (box_df["left_reward_x"] - trial_data["x"]) ** 2
            + (box_df["left_reward_z"] - trial_data["y"]) ** 2
        )

    trial_data = trial_data[trial_data["dist"] > 2]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data["val"] = trial_data.loc[::-1, "difference"].cummax()[::-1]
    trial_data["next"] = trial_data["val"] <= 0
    idx = trial_data[(trial_data["next"])].index[0]

    return trial_data.loc[idx, :]


def find_decision_point_from_value(
    trial_data: pd.DataFrame, box_df: pd.DataFrame, label: str = "heading_dir_velocity"
):
    # NOTE(celia): not used for now.
    if all(trial_data["trial_left_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        trial_data["dist"] = abs(box_df["right_reward_x"] - trial_data["x"])
    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        trial_data["dist"] = abs(box_df["left_reward_x"] - trial_data["x"])

    trial_data = trial_data[trial_data["dist"] > 3]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data["next"] = trial_data.loc[::-1, "difference"].cummax()[::-1] <= 0
    good_dir = trial_data

    if all(trial_data["trial_left_choice"] > 0.5):
        test = (good_dir["y"] > box_df["right_reward_z"]) & (good_dir["dist"] < 2)
        good_dir = good_dir[~test]
        if "dir" in label:
            idx = good_dir[label].argmin()
        elif "angle" in label:
            idx = good_dir[label].argmax()
        else:
            raise NotImplementedError()
    else:
        test = (good_dir["y"] > box_df["left_reward_z"]) & (good_dir["dist"] < 2)
        good_dir = good_dir[~test]
        if "dir" in label:
            idx = good_dir[label].argmax()
        elif "angle" in label:
            idx = good_dir[label].argmin()
        else:
            raise NotImplementedError()
    return trial_data.iloc[idx, :]
