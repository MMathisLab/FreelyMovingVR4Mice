import copy
from typing import List, Optional, Tuple, Union

import matplotlib as mpl
import matplotlib.axes
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import sklearn
import sklearn.linear_model
from sklearn.metrics import log_loss
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
    label: List[str],
    n_splits: int = 10,
    per_mouse: bool = True,
    max_iter: int = 100,
    scale_data: bool = True,
    random_state: Optional[int] = None,
) -> Tuple[pd.DataFrame, npt.NDArray, List[dict]]:
    """Predict the animal's decision based on the `label` data, through a logistic regression.

    Args:
        df: The dataframe.
        label: A list of column names in the `df` dataframe.
        n_splits: The number of splits fo the cross validation.
        per_mouse: If `True` split the data per session, else split
            randomly across all sessions. If per_mouse, we train on
            all sessions but one, and test on the left out session.
        scale_data: If `True`, standardize the data before fitting the model.
        random_state: Random state for reproducibility.

    Returns:
        The initial dataframe with an extra `pred` column, containing the probability that the
        animal went to the right, the coefficients of the model, and the scalers used for each fold
        (if `scale_data` is `True` else None).

    Example:
        ```
        label = ["norm_x", "y", "heading_dir", "head_angle", "trial_tortuosity", "trial_init_x",
                "trial_length", "trial_init_y", "aperture"]
        df["aperture"] = (df["aperture"] > 7).astype(int)
        df, clf, _ = regression.predict_decision(df, label=label)
        names = ["x", "y", "head", "body",  "tort", "init_x", "length", "init_y", "aperture"]
        plt.figure(figsize=(20,8))
        plt.bar(names, clf.coef_[0,:])
        ```
    """

    data = np.asarray(df[label].values)
    labels = df.trial_left_choice.values

    if data.ndim == 1:
        data = data.reshape(-1, 1)
    n_features = data.shape[1]
    pred = np.empty((data.shape[0], 2))
    scores = np.empty((data.shape[0]))
    model = sklearn.linear_model.LogisticRegression(
        max_iter=max_iter, random_state=random_state
    )

    if per_mouse:
        sessions = df.dataset.values
        coefs = np.empty((len(np.unique(sessions)), n_features + 1))
        scalers = []

        logo = sklearn.model_selection.LeaveOneGroupOut()
        for i, (train_index, test_index) in enumerate(
            logo.split(data, labels, sessions)
        ):
            X_train = data[train_index]
            X_test = data[test_index]

            if scale_data:
                scaler = sklearn.preprocessing.StandardScaler().fit(X_train)
                X_train = scaler.transform(X_train)
                X_test = scaler.transform(X_test)
                scalers.append(
                    {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}
                )
            else:
                scalers.append(None)

            model.fit(X_train, labels[train_index])
            pred[test_index] = model.predict_proba(X_test)
            scores[test_index] = model.predict(X_test) == labels[test_index]

            # Coeffs
            coefs[i] = np.concatenate([[model.intercept_[0]], model.coef_[0]])

    else:
        coefs = np.empty((1, n_features + 1))
        scalers = []
        kf = sklearn.model_selection.KFold(
            n_splits=n_splits, random_state=random_state, shuffle=True
        )
        for i, (train_index, test_index) in enumerate(kf.split(data)):
            X_train = data[train_index]
            X_test = data[test_index]

            if scale_data:
                scaler = sklearn.preprocessing.StandardScaler().fit(X_train)
                X_train = scaler.transform(X_train)
                X_test = scaler.transform(X_test)
                scalers.append(
                    {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}
                )
            else:
                scalers.append(None)

            model.fit(X_train, labels[train_index])
            pred[test_index] = model.predict_proba(X_test)
            scores[test_index] = model.predict(X_test) == labels[test_index]

        # Store final model coefficients
        coefs[0] = np.concatenate([[model.intercept_[0]], model.coef_[0]])

    ret = copy.deepcopy(df)
    ret.loc[:, "accuracy"] = scores
    ret.loc[:, "proba_left"] = pred[:, 1]

    return ret, coefs, scalers


def compute_bic(probs: npt.NDArray, y: npt.NDArray, n_params: int):
    n = len(y)
    k = n_params

    # Calculate Log-Likelihood
    # log_loss in sklearn is the negative log-likelihood divided by n
    # Explicitly specify both labels to handle single-label windows
    log_likelihood = -log_loss(y, probs, normalize=False, labels=[0, 1])

    # BIC Formula: ln(n)k - 2ln(L)
    bic = np.log(n) * k - 2 * log_likelihood
    return bic


def compute_bic_sliding_window(
    probs: npt.NDArray, y: npt.NDArray, n_params: int, window_size=10
):
    """Compute BIC over a rolling window of timesteps.

    Each window uses exactly window_size samples. For edges:
    - At the beginning: looks forward to get window_size samples
    - At the end: looks backward to get window_size samples
    - In the middle: uses window_size samples centered around current timestep
    """
    n = len(y)
    bic_values = np.full(n, np.nan)

    if n == 0:
        return bic_values

    # For each timestep, create a window of exactly window_size samples
    for i in range(n):
        # Try to center the window around i
        ideal_start = i - window_size // 2
        ideal_end = ideal_start + window_size

        # Clamp to valid bounds
        start = max(0, ideal_start)
        end = min(n, ideal_end)

        # Adjust if we don't have enough samples - shift window to stay within bounds
        if end - start < window_size:
            if start == 0:  # At beginning, extend forward
                end = min(n, window_size)
            else:  # At end, extend backward
                start = max(0, n - window_size)

        window_probs = probs[start:end]
        window_y = y[start:end]

        # Ensure 2D for probabilities
        window_probs = np.asarray(window_probs).reshape(len(window_probs), -1)

        # Only compute if we have exactly window_size samples
        if len(window_y) == window_size:
            bic_values[i] = compute_bic(window_probs, window_y, n_params)

    return bic_values


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

    # Fallback:
    # When nothing crosses the threshold, we take the last step of the trial
    # as the decision point. We need to return something, but for some threshold there
    # is no value above the threshold.
    return trial_data.iloc[-1]


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
    ax.set_xlim(-27, 27)
    ax.set_ylim(-27, 27)

    for idx_trial, trial in df.groupby("trial"):
        if idx_trial in trials:
            trial = trial.reset_index(drop=True)
            plotting._plot_parameter_on_trial_traj(
                trial, (0, 1), "proba_left", "x", "y", cmap, 1, ax
            )

            if decision_point is not None:
                mpl.rcParams["lines.markersize"] = 5
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


def _build_trial_cache(
    interpolated_df: pd.DataFrame,
    index_cols: List[str],
    keys: set,
) -> dict:
    """Cache per-trial dataframes for fast lookups."""
    cache = {}
    grouped = interpolated_df.groupby(index_cols, sort=False)
    for key, group in grouped:
        if key in keys:
            cache[key] = group.sort_values("trial_length").reset_index(drop=True)
    return cache


def _metrics_for_window(
    trial_data: pd.DataFrame,
    metric_cols: List[str],
    decision_window: int,
    start: int,
    end: int,
    meta: dict,
    period: str,
    random_id: Optional[int] = None,
) -> Optional[pd.Series]:
    """Compute window means for selected metrics with attached metadata."""
    if start < 0 or end > len(trial_data) or end - start != decision_window:
        return None
    metrics = trial_data.iloc[start:end][metric_cols].mean()
    metrics["dataset"] = meta["dataset"]
    metrics["aperture"] = meta["aperture"]
    metrics["trial"] = meta["trial"]
    metrics["decision_trial_length"] = meta["decision_trial_length"]
    metrics["period"] = period
    if random_id is not None:
        metrics["random_id"] = random_id
    return metrics


def _paired_diff(
    metrics_df: pd.DataFrame,
    index_cols: List[str],
    metric_cols: List[str],
    extra_index_cols: List[str],
) -> Optional[pd.DataFrame]:
    """Compute paired after-before deltas for each index key."""
    paired = metrics_df.pivot_table(
        index=index_cols + extra_index_cols,
        columns="period",
        values=metric_cols,
    ).dropna()
    if paired.empty:
        return None
    return paired.xs("after", level=-1, axis=1) - paired.xs("before", level=-1, axis=1)


def _jump_score_components(
    df: pd.DataFrame,
    metric_cols: List[str],
    rand_mean: pd.Series,
    rand_std: pd.Series,
    rand_mean_abs: dict,
    rand_std_abs: dict,
) -> Tuple[dict, dict]:
    """Compute per-row deltas and z-scores for metrics, handling abs metrics."""
    abs_metric_cols = {"head_angle_flipped", "heading_dir_flipped"}
    deltas = {}
    z_scores = {}
    for col in metric_cols:
        if col in abs_metric_cols:
            deltas[col] = df[col].abs()
            z_scores[col] = (deltas[col] - rand_mean_abs[col]) / rand_std_abs[col]
        else:
            deltas[col] = df[col]
            z_scores[col] = (deltas[col] - rand_mean[col]) / rand_std[col]
    return deltas, z_scores


def _sample_random_metrics(
    base_points: pd.DataFrame,
    trial_cache: dict,
    metric_cols: List[str],
    decision_window: int,
    n_random_points: int,
    rng: np.random.Generator,
    index_cols: List[str],
) -> pd.DataFrame:
    """Sample random before/after windows for a null distribution."""
    random_metrics = []
    for _, row in base_points.iterrows():
        key = (row[index_cols[0]], row[index_cols[1]], row[index_cols[2]])
        trial_data = trial_cache.get(key)
        if trial_data is None:
            continue

        n_available = len(trial_data) - 2 * decision_window
        if n_available <= 0:
            continue

        sample_size = min(n_random_points, n_available)
        rand_indices = rng.choice(
            np.arange(decision_window, len(trial_data) - decision_window),
            size=sample_size,
            replace=False,
        )

        for rand_id, rand_idx in enumerate(rand_indices):
            meta = {
                "dataset": row[index_cols[0]],
                "aperture": row[index_cols[1]],
                "trial": row[index_cols[2]],
                "decision_trial_length": trial_data.loc[rand_idx, "trial_length"],
            }
            before = _metrics_for_window(
                trial_data,
                metric_cols,
                decision_window,
                rand_idx - decision_window,
                rand_idx,
                meta,
                "before",
                random_id=rand_id,
            )
            after = _metrics_for_window(
                trial_data,
                metric_cols,
                decision_window,
                rand_idx + 1,
                rand_idx + 1 + decision_window,
                meta,
                "after",
                random_id=rand_id,
            )
            if before is None or after is None:
                continue
            random_metrics.extend([before, after])

    return pd.DataFrame(random_metrics)


def _compute_random_stats(random_diff_df: pd.DataFrame) -> dict:
    """Compute per-session stats to normalize deltas (z-score)."""
    random_stats_by_session = {}
    for dataset, df in random_diff_df.groupby(level="dataset"):
        rand_mean = df.mean(numeric_only=True)
        rand_std = df.std(numeric_only=True)
        rand_ang = df["head_angle_flipped"].abs()
        rand_dir = df["heading_dir_flipped"].abs()
        random_stats_by_session[dataset] = {
            "rand_mean": rand_mean,
            "rand_std": rand_std,
            "rand_mean_ang": rand_ang.mean(),
            "rand_std_ang": rand_ang.std(),
            "rand_mean_dir": rand_dir.mean(),
            "rand_std_dir": rand_dir.std(),
        }
    return random_stats_by_session


def _compute_random_jump_scores(
    random_diff_df: pd.DataFrame,
    random_stats_by_session: dict,
    metric_cols: List[str],
) -> dict:
    """Compute per-session arrays of random jump scores."""
    random_jump_scores_by_session = {}
    for dataset, df in random_diff_df.groupby(level="dataset"):
        session_stats = random_stats_by_session.get(dataset)
        if session_stats is None:
            continue
        rand_mean = session_stats["rand_mean"]
        rand_std = session_stats["rand_std"]
        rand_mean_abs = {
            "head_angle_flipped": session_stats["rand_mean_ang"],
            "heading_dir_flipped": session_stats["rand_mean_dir"],
        }
        rand_std_abs = {
            "head_angle_flipped": session_stats["rand_std_ang"],
            "heading_dir_flipped": session_stats["rand_std_dir"],
        }
        _, z_scores = _jump_score_components(
            df,
            metric_cols,
            rand_mean,
            rand_std,
            rand_mean_abs,
            rand_std_abs,
        )
        random_jump_scores_by_session[dataset] = (
            (
                z_scores["velocity_x_fliped"]
                - z_scores["velocity_y"]
                + z_scores["head_angle_flipped"]
                + z_scores["heading_dir_flipped"]
            )
            .dropna()
            .to_numpy()
        )
    return random_jump_scores_by_session


def _evaluate_thresholds(
    all_decision_points: pd.DataFrame,
    trial_cache: dict,
    random_stats_by_session: dict,
    random_jump_scores_by_session: dict,
    metric_cols: List[str],
    decision_window: int,
    thresholds: np.ndarray,
    index_cols: List[str],
) -> List[dict]:
    """Evaluate thresholds with session-specific baselines."""
    threshold_evals_norm = []
    for threshold in thresholds:
        print(
            f"Analyzing decision points with threshold_uncertainty {threshold} (normalized)..."
        )
        decision_points_threshold = all_decision_points[
            all_decision_points.threshold_uncertainty == threshold
        ]
        decision_metrics = []

        for _, row in decision_points_threshold.iterrows():
            key = (row[index_cols[0]], row[index_cols[1]], row[index_cols[2]])
            trial_data = trial_cache.get(key)
            if trial_data is None:
                continue

            decision_length = row["trial_length"]
            decision_index_candidates = trial_data[
                np.isclose(trial_data.trial_length, decision_length)
            ].index
            if len(decision_index_candidates) == 0:
                continue
            decision_index = decision_index_candidates[0]

            meta = {
                "dataset": row[index_cols[0]],
                "aperture": row[index_cols[1]],
                "trial": row[index_cols[2]],
                "decision_trial_length": decision_length,
            }
            before = _metrics_for_window(
                trial_data,
                metric_cols,
                decision_window,
                decision_index - decision_window,
                decision_index,
                meta,
                "before",
            )
            after = _metrics_for_window(
                trial_data,
                metric_cols,
                decision_window,
                decision_index + 1,
                decision_index + 1 + decision_window,
                meta,
                "after",
            )
            if before is None or after is None:
                continue
            decision_metrics.extend([before, after])

        decision_metrics_df = pd.DataFrame(decision_metrics)
        if decision_metrics_df.empty:
            continue

        true_diff_df = _paired_diff(decision_metrics_df, index_cols, metric_cols, [])
        if true_diff_df is None:
            continue

        for dataset, df in true_diff_df.groupby(level="dataset"):
            session_stats = random_stats_by_session.get(dataset)
            if session_stats is None:
                continue
            rand_mean = session_stats["rand_mean"]
            rand_std = session_stats["rand_std"]
            rand_mean_abs = {
                "head_angle_flipped": session_stats["rand_mean_ang"],
                "heading_dir_flipped": session_stats["rand_mean_dir"],
            }
            rand_std_abs = {
                "head_angle_flipped": session_stats["rand_std_ang"],
                "heading_dir_flipped": session_stats["rand_std_dir"],
            }

            deltas, z_scores = _jump_score_components(
                df,
                metric_cols,
                rand_mean,
                rand_std,
                rand_mean_abs,
                rand_std_abs,
            )
            true_scores = (
                (
                    z_scores["velocity_x_fliped"]
                    - z_scores["velocity_y"]
                    + z_scores["head_angle_flipped"]
                    + z_scores["heading_dir_flipped"]
                )
                .dropna()
                .to_numpy()
            )
            random_scores = random_jump_scores_by_session.get(dataset, np.array([]))
            t_stat = np.nan
            p_value = np.nan
            if len(true_scores) > 1 and len(random_scores) > 1:
                try:
                    from scipy.stats import ttest_ind

                    t_stat, p_value = ttest_ind(
                        true_scores,
                        random_scores,
                        equal_var=False,
                    )
                except ImportError as exc:
                    raise ImportError(
                        "scipy is required for per-threshold statistical tests."
                    ) from exc

            jump_score_norm = (
                z_scores["velocity_x_fliped"].mean()
                - z_scores["velocity_y"].mean()
                + z_scores["head_angle_flipped"].mean()
                + z_scores["heading_dir_flipped"].mean()
            )
            jump_score = (
                deltas["velocity_x_fliped"].mean()
                - deltas["velocity_y"].mean()
                + deltas["head_angle_flipped"].mean()
                + deltas["heading_dir_flipped"].mean()
            )

            threshold_evals_norm.append(
                {
                    "dataset": dataset,
                    "threshold": threshold,
                    "jump_score_norm": jump_score_norm,
                    "jump_score": jump_score,
                    "n_trials": len(df),
                    "z_vx": z_scores["velocity_x_fliped"].mean(),
                    "z_vy": z_scores["velocity_y"].mean(),
                    "z_ang": z_scores["head_angle_flipped"].mean(),
                    "z_dir": z_scores["heading_dir_flipped"].mean(),
                    "vx_delta": deltas["velocity_x_fliped"].mean(),
                    "vy_delta": deltas["velocity_y"].mean(),
                    "ang_delta": deltas["head_angle_flipped"].mean(),
                    "dir_delta": deltas["heading_dir_flipped"].mean(),
                    "t_stat": t_stat,
                    "p_value": p_value,
                }
            )

    return threshold_evals_norm


def _fisher_combine(p_values: Union[pd.Series, np.ndarray]) -> float:
    p_values = np.asarray(p_values)
    p_values = p_values[np.isfinite(p_values) & (p_values > 0)]
    if p_values.size == 0:
        return np.nan
    try:
        from scipy.stats import chi2

        stat = -2.0 * np.sum(np.log(p_values))
        return chi2.sf(stat, 2 * p_values.size)
    except ImportError as exc:
        raise ImportError(
            "scipy is required for per-threshold statistical tests."
        ) from exc


def _minmax_scale_series(series: pd.Series) -> pd.Series:
    """Min-max scale a numeric series to [0, 1], preserving NaNs."""
    min_val = series.min(skipna=True)
    max_val = series.max(skipna=True)
    if pd.isna(min_val) or pd.isna(max_val):
        return series * np.nan
    if np.isclose(max_val, min_val):
        return series.where(series.isna(), 0.0)
    return (series - min_val) / (max_val - min_val)


def select_threshold(
    all_decision_points: pd.DataFrame,
    interpolated_df: pd.DataFrame,
    decision_window: int = 10,
    n_random_points: int = 2,
    random_state: int = 42,
):
    """Evaluate decision thresholds using session-wise random baselines.

    For each threshold, the function computes before/after window deltas around
    decision points, z-scores them against random window deltas sampled per
    session, and returns a per-session/per-threshold evaluation DataFrame. It
    does not select a single best threshold.

    Args:
        all_decision_points: DataFrame containing the decision points for all trials and sessions.
        interpolated_df: DataFrame containing the interpolated trajectory data for all trials and sessions.
        decision_window: Number of timesteps to consider before and after the decision point for computing metrics.
        n_random_points: Number of random windows to sample per trial for building the null distribution.
        random_state: Seed for the random number generator for reproducibility.

    Returns:
        A DataFrame with one row per dataset and threshold containing jump-score
        metrics and optional per-threshold p-values (when scipy is available).
    """
    metric_cols = [
        "velocity_x_fliped",
        "velocity_y",
        "heading_dir_flipped",
        "head_angle_flipped",
    ]
    index_cols = ["dataset", "aperture", "trial"]
    rng = np.random.default_rng(random_state)

    # Use all trials as candidates for random sampling.
    base_points = all_decision_points.drop_duplicates(index_cols)
    all_keys = set(
        zip(
            all_decision_points["dataset"],
            all_decision_points["aperture"],
            all_decision_points["trial"],
        )
    )
    trial_cache = _build_trial_cache(interpolated_df, index_cols, all_keys)

    # Sample random windows per trial to build a null distribution per session.
    random_metrics_df = _sample_random_metrics(
        base_points,
        trial_cache,
        metric_cols,
        decision_window,
        n_random_points,
        rng,
        index_cols,
    )
    if random_metrics_df.empty:
        raise ValueError(
            "No random samples available. Check threshold filter and decision_window."
        )

    random_diff_df = _paired_diff(
        random_metrics_df, index_cols, metric_cols, ["random_id"]
    )
    if random_diff_df is None:
        raise ValueError(
            "No paired random samples available. Check threshold filter and decision_window."
        )

    # Cache per-session stats to normalize deltas (z-score).
    random_stats_by_session = _compute_random_stats(random_diff_df)
    random_jump_scores_by_session = _compute_random_jump_scores(
        random_diff_df,
        random_stats_by_session,
        metric_cols,
    )

    # Evaluate all thresholds using the same per-session random baselines.
    thresholds = all_decision_points.sort_values(
        "threshold_uncertainty", ascending=False
    )["threshold_uncertainty"].unique()

    threshold_evals_norm = _evaluate_thresholds(
        all_decision_points,
        trial_cache,
        random_stats_by_session,
        random_jump_scores_by_session,
        metric_cols,
        decision_window,
        thresholds,
        index_cols,
    )

    eval_df_norm = pd.DataFrame(threshold_evals_norm)
    if eval_df_norm.empty:
        raise ValueError("No threshold evaluations were computed.")

    if "p_value" in eval_df_norm.columns:
        combined_p = eval_df_norm.groupby("threshold")["p_value"].apply(_fisher_combine)
        eval_df_norm["p_value_fisher"] = eval_df_norm["threshold"].map(combined_p)

    # Add min-max standardized versions of all z-score columns.
    z_cols = [col for col in eval_df_norm.columns if col.startswith("z_")]
    for col in z_cols:
        eval_df_norm[f"{col}_minmax"] = _minmax_scale_series(eval_df_norm[col])

    # Compute a resulting score from min-max standardized z-score columns.
    required_cols = [
        "z_vx_minmax",
        "z_vy_minmax",
        "z_ang_minmax",
        "z_dir_minmax",
    ]
    if all(col in eval_df_norm.columns for col in required_cols):
        eval_df_norm["jump_score_norm_minmax"] = (
            eval_df_norm["z_vx_minmax"]
            - eval_df_norm["z_vy_minmax"]
            + eval_df_norm["z_ang_minmax"]
            + eval_df_norm["z_dir_minmax"]
        )

    return eval_df_norm
