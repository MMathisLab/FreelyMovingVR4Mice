import copy
from typing import List, Optional, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import plotting
import sklearn
from matplotlib.collections import LineCollection
from sklearn.model_selection import LeaveOneGroupOut

colors_choice = ["#5C0A72", "#FD672C"]
colors_aperture = ["#E41A1C", "#437FB5"]
colors_aperture_pale = ["#EC8788", "#96B9D6"]


def predict_decision(
    df, label: str = "norm_x", n_splits: int = 10, per_mouse: bool = False
) -> Tuple[pd.DataFrame, npt.NDArray]:
    """Predict the decision of the animal based on the `label` data, through a logistic regression.

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

    Args:
        df: The dataframe.
        label: The name of the column in the `df` dataframe.
        n_splits: The number of splits fo the cross validation.
        per_mouse: If `True` split the data per session, else split
            randomly across all sessions.

    Returns:
        The initial dataframe with an extra `pred` column, containing the probability that the
        animal went to the right.
    """

    data = df[label].values
    labels = df.trial_L_choice.values

    if not isinstance(label, list):
        data = data.reshape(-1, 1)
    pred = np.empty((data.shape[0], 2))
    scores = np.empty((data.shape[0]))
    model = sklearn.linear_model.LogisticRegression()

    if per_mouse:
        sessions = df.session.values
        coefs = np.empty((len(np.unique(sessions)), len(label) + 1))

        logo = LeaveOneGroupOut()
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


def find_decision_point_per_trial(
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
    if all(trial_data["trial_L_choice"] > 0.5):
        above_threshold = trial_data[trial_data["proba_left"] > threshold_right]
    else:
        above_threshold = trial_data[trial_data["proba_left"] < threshold_left]

    for index in above_threshold.index:
        subsequent_values = trial_data.loc[index:]["proba_left"]
        if all(trial_data["trial_L_choice"] > 0.5) and all(
            subsequent_values >= above_threshold.loc[index, "proba_left"]
        ):
            # Returning the step of the decision point
            return trial_data.loc[index]
        elif all(trial_data["trial_L_choice"] < 0.5) and all(
            subsequent_values <= above_threshold.loc[index, "proba_left"]
        ):
            return trial_data.loc[index]


def find_decision_point(
    df: pd.DataFrame, threshold_uncertainty: float = 0.3
) -> pd.DataFrame:
    """Find the threshold-based decision point for all trials.

    Example:
    ```
    decision_point = regression.find_decision_point_proba(df, threshold_uncertainty=0.3)

    ```

    Args:
        df: Data for all trials, all sessions.
        threshold_uncertainty: Distance of the threshold to respectively 1 or 0.

    Returns:
        The rows of all the decision points for each trial.

    """
    decision_point = df.groupby(["session", "trial"], as_index=False).apply(
        lambda x: find_decision_point_per_trial(x, threshold_uncertainty)
    )
    return decision_point


def plot_decision_points_on_trajectory(
    df: pd.DataFrame,
    df_box: pd.DataFrame,
    decision_point: Optional[pd.DataFrame] = None,
    color: str = "red",
    trials: List[int] = list(range(25, 30)),
    ax=None,
):
    """

    Example:
    ```
    fig = plt.figure(figsize = (15,15), constrained_layout=True)
    gs = plt.GridSpec(3, 5, figure=fig)
    ax = fig.add_subplot(gs[:2, :])

    colors=["red", "blue", "green", "purple", "orange"]

    for i, thr in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
        print("-->", thr)
        ax2 = fig.add_subplot(gs[2, i])
        decision_point = df.groupby(["session", "trial"], as_index=False).apply(lambda x: regression.find_decision_point_per_trial(x, thr))
        regression.plot_decision_points_on_trajectory(df, df_box, decision_point, color=colors[i], ax=ax, trials=list(range(10, 20)))
        regression.pair_plot(decision_point, ax=ax2)

    plt.savefig("figure.svg")
    ```

    """

    if len(df.session.unique()) > 1:
        raise ValueError(
            f"Only one session should be provided, {len(df.session.unique())} were provided."
        )

    if ax is None:
        fig = plt.figure(figsize=(8, 7), constrained_layout=True)
        gs = plt.GridSpec(1, 1, figure=fig)
        ax = fig.add_subplot(gs[0, 0])

    plotting.plot_all_boxes(ax=ax, df_box=df_box)
    ax.set_xlim(-27, 27)
    ax.set_ylim(-27, 27)

    for trial in df.trial.unique():
        if trial in trials:

            points = np.array(
                [
                    df[df["trial"] == trial]["x"],
                    df[df["trial"] == trial]["y"],
                ]
            ).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            lc = LineCollection(segments, cmap="PuOr", norm=plt.Normalize(0, 1))
            lc.set_array(df[df["trial"] == trial]["proba_left"])
            lc.set_linewidth(2)

            ax.add_collection(lc)
            ax.autoscale()
            ax.margins(0.1)

            if decision_point is not None:
                mpl.rcParams["lines.markersize"] = 10
                ax.scatter(
                    decision_point[decision_point["trial"] == trial]["x"],
                    decision_point[decision_point["trial"] == trial]["y"],
                    color=color,
                )

            ax.legend([], [], frameon=False)
        else:
            continue


def find_decision_point_from_distance(trial_data: pd.DataFrame, df_box: pd.DataFrame):
    # NOTE(celia): not used for now.
    if all(trial_data["trial_L_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        trial_data["dist"] = np.sqrt(
            (df_box["right_reward_x"] - trial_data["x"]) ** 2
            + (df_box["right_reward_z"] - trial_data["y"]) ** 2
        )

    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        trial_data["dist"] = np.sqrt(
            (df_box["left_reward_x"] - trial_data["x"]) ** 2
            + (df_box["left_reward_z"] - trial_data["y"]) ** 2
        )

    trial_data = trial_data[trial_data["dist"] > 2]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data["val"] = trial_data.loc[::-1, "difference"].cummax()[::-1]
    trial_data["next"] = trial_data["val"] <= 0
    idx = trial_data[(trial_data["next"])].index[0]

    return trial_data.loc[idx, :]


def find_decision_point_from_value(
    trial_data: pd.DataFrame, df_box: pd.DataFrame, label: str = "heading_dir_velocity"
):
    # NOTE(celia): not used for now.
    if all(trial_data["trial_L_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        trial_data["dist"] = abs(df_box["right_reward_x"] - trial_data["x"])
    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        trial_data["dist"] = abs(df_box["left_reward_x"] - trial_data["x"])

    trial_data = trial_data[trial_data["dist"] > 3]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data["next"] = trial_data.loc[::-1, "difference"].cummax()[::-1] <= 0
    good_dir = trial_data

    if all(trial_data["trial_L_choice"] > 0.5):
        test = (good_dir["y"] > df_box["right_reward_z"]) & (good_dir["dist"] < 2)
        good_dir = good_dir[~test]
        if "dir" in label:
            idx = good_dir[label].argmin()
        elif "angle" in label:
            idx = good_dir[label].argmax()
        else:
            raise NotImplementedError()
    else:
        test = (good_dir["y"] > df_box["left_reward_z"]) & (good_dir["dist"] < 2)
        good_dir = good_dir[~test]
        if "dir" in label:
            idx = good_dir[label].argmax()
        elif "angle" in label:
            idx = good_dir[label].argmin()
        else:
            raise NotImplementedError()
    return trial_data.iloc[idx, :]
