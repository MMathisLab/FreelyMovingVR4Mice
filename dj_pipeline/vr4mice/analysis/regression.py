import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats
import sklearn
from matplotlib.collections import LineCollection
from sklearn.model_selection import LeaveOneGroupOut

import plotting
import seaborn as sns


def predict_decision(df, label="norm_x", n_splits=10, per_mouse=False):
    """Predict the decision of the animal based on the `label` data, through a logistic regression.
    
    Example: 
    ```
    label = ["norm_x", "y", "heading_dir", "head_angle", "trial_tortuosity", "trial_init_x", 
            "trial_length", "trial_init_y", "binary_aperture"]
    df["binary_aperture"] = (df["aperture"] > 7).astype(int)
    
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
    labels = df.trial_R_choice.values

    if not isinstance(label, list):
        data = data.reshape(-1, 1)
        pred = np.empty((data.shape[0], 2))

    model = sklearn.linear_model.LogisticRegression()

    if per_mouse:
        sessions = df.session.values
        logo = LeaveOneGroupOut()
        for i, (train_index,
                test_index) in enumerate(logo.split(data, labels, sessions)):
            model.fit(data[train_index], labels[train_index])
            pred[test_index] = model.predict_proba(data[test_index])
    else:
        kf = sklearn.model_selection.KFold(n_splits=n_splits)
        for i, (train_index, test_index) in enumerate(kf.split(data)):
            model.fit(data[train_index], labels[train_index])
            pred[test_index] = model.predict_proba(data[test_index])

    df.loc[:, "pred"] = pred[:, 1]

    return df, model


def find_decision_point_proba(df, threshold_uncertainty=0.3):
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
        lambda x: find_decision_point_per_trial(x, threshold_uncertainty))
    return decision_point


def find_decision_point_per_trial(trial_data, threshold_uncertainty):
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
    if all(trial_data["trial_R_choice"] > 0.5):
        above_threshold = trial_data[trial_data['pred'] > threshold_right]
    else:
        above_threshold = trial_data[trial_data['pred'] < threshold_left]

    for index in above_threshold.index:
        subsequent_values = trial_data.loc[index:]['pred']
        if all(trial_data["trial_R_choice"] > 0.5) and all(
                subsequent_values >= above_threshold.loc[index, 'pred']):
            # Returning the step of the decision point
            return trial_data.loc[index]
        elif all(trial_data["trial_R_choice"] < 0.5) and all(
                subsequent_values <= above_threshold.loc[index, 'pred']):
            return trial_data.loc[index]


def plot_proba_per_trial(df, trials):
    fig, ax = plt.subplots(5, 3, figsize=(15, 15))
    ax = ax.flatten()
    for session_id, session in enumerate(df.session.unique()):
        for trial_id, trial in df[df["session"] == session].groupby(["trial"]):
            if trial_id[0] in trials:
                # Reset index within each group for a uniform timescale
                trial = trial.reset_index(drop=True)
                sns.lineplot(data=trial,
                             x="bin_centers",
                             y="pred",
                             ax=ax[session_id],
                             errorbar="se")
                #trial["pred"].plot(ax[session_id])
            else:
                continue

    #plt.savefig("seaborn_plot.svg")


def plot_decision_points_on_trajectory(df,
                                       df_box,
                                       decision_point=None,
                                       color="red",
                                       session="30559_2024-02-19_1",
                                       trials=list(range(25, 30)),
                                       ax=None):
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
    if ax is None:
        fig = plt.figure(figsize=(8, 7), constrained_layout=True)
        gs = plt.GridSpec(1, 1, figure=fig)
        ax = fig.add_subplot(gs[0, 0])

    plotting.plot_all_boxes(ax=ax, df_box=df_box)

    mpl.rcParams['lines.markersize'] = 15
    ax.scatter(df_box["right_reward_x"],
               df_box["right_reward_z"],
               color="orange")
    ax.scatter(df_box["left_reward_x"],
               df_box["left_reward_z"],
               color="purple")

    for trial in df[df["session"] == session].trial.unique():
        if trial in trials:

            points = np.array([
                df[(df["session"] == session) & (df["trial"] == trial)]["x"],
                df[(df["session"] == session) & (df["trial"] == trial)]["y"]
            ]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            lc = LineCollection(segments,
                                cmap='PuOr_r',
                                norm=plt.Normalize(0, 1))
            lc.set_array(df[(df["session"] == session)
                            & (df["trial"] == trial)]["pred"])
            lc.set_linewidth(2)

            ax.add_collection(lc)
            ax.autoscale()
            ax.margins(0.1)

            if decision_point is not None:
                mpl.rcParams['lines.markersize'] = 10
                ax.scatter(
                    decision_point[(decision_point["session"] == session)
                                   & (decision_point["trial"] == trial)]["x"],
                    decision_point[(decision_point["session"] == session)
                                   & (decision_point["trial"] == trial)]["y"],
                    color=color)

            ax.legend([], [], frameon=False)
        else:
            continue


def find_decision_point_from_distance(trial_data, df_box):
    #print(trial_data["trial"].values[0], trial_data["session"].values[0])

    if all(trial_data["trial_R_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        #trial_data["dist"] = abs(df_box["right_reward_x"] - trial_data["x"])
        trial_data["dist"] = np.sqrt(
            (df_box["right_reward_x"] - trial_data["x"])**2 +
            (df_box["right_reward_z"] - trial_data["y"])**2)

    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        #trial_data["dist"] = abs(df_box["left_reward_x"] - trial_data["x"])
        trial_data["dist"] = np.sqrt(
            (df_box["left_reward_x"] - trial_data["x"])**2 +
            (df_box["left_reward_z"] - trial_data["y"])**2)

    trial_data = trial_data[trial_data["dist"] > 2]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data['val'] = trial_data.loc[::-1, 'difference'].cummax()[::-1]
    trial_data["next"] = (trial_data["val"] <= 0)
    idx = trial_data[(trial_data["next"])].index[0]
    return trial_data.loc[idx, :]


def find_decision_point_from_value(trial_data,
                                   df_box,
                                   label="heading_dir_velocity"):
    #print(trial_data["trial"].values[0], trial_data["session"].values[0])

    if all(trial_data["trial_R_choice"] > 0.5):
        trial_data = trial_data[trial_data["mouse_in_R"] < 1]
        trial_data["dist"] = abs(df_box["right_reward_x"] - trial_data["x"])
    else:
        trial_data = trial_data[trial_data["mouse_in_L"] < 1]
        trial_data["dist"] = abs(df_box["left_reward_x"] - trial_data["x"])

    trial_data = trial_data[trial_data["dist"] > 3]
    trial_data["difference"] = trial_data["dist"].diff()
    trial_data['next'] = (trial_data.loc[::-1, 'difference'].cummax()[::-1]
                          <= 0)
    good_dir = trial_data  #[(trial_data["next"])]

    if all(trial_data["trial_R_choice"] > 0.5):
        test = ((good_dir["y"] > df_box["right_reward_z"]) &
                (good_dir["dist"] < 2))
        good_dir = good_dir[~test]
        #idx = good_dir.index[0]
        if "dir" in label:
            idx = good_dir[label].argmin()
        elif "angle" in label:
            idx = good_dir[label].argmax()
        else:
            raise NotImplementedError()
    else:
        #idx = good_dir.index[0]
        test = ((good_dir["y"] > df_box["left_reward_z"]) &
                (good_dir["dist"] < 2))
        good_dir = good_dir[~test]
        if "dir" in label:
            idx = good_dir[label].argmax()
        elif "angle" in label:
            idx = good_dir[label].argmin()
        else:
            raise NotImplementedError()
    return trial_data.iloc[idx, :]


def pair_plot(decision_point, ax=None):

    if ax is None:
        fig = plt.figure(figsize=(3, 5))
        gs = plt.GridSpec(1, 1, figure=fig)
        ax = fig.add_subplot(gs[0, 0])

    mean_mice = decision_point.groupby(["session", "aperture"],
                                       as_index=False).mean(numeric_only=True)

    sns.lineplot(ax=ax,
                 data=mean_mice,
                 x="aperture",
                 y=np.abs(mean_mice.y) - 25,
                 estimator=None,
                 units=mean_mice.session,
                 sort=False,
                 color="black",
                 alpha=0.5)
    sns.scatterplot(ax=ax,
                    data=mean_mice,
                    x="aperture",
                    y=np.abs(mean_mice.y) - 25,
                    color="black")
    ax.set_xlim(3, 13)
    #plt.ylim(5,20)
    ax.set_ylim(0, -25)
    ax.set_ylabel("Decision distance to screen (cm)")
    ax.set_xlabel("Occluder")
    print(
        stats.ttest_rel(mean_mice[mean_mice["aperture"] == 4.3]["y"],
                        mean_mice[mean_mice["aperture"] == 12]["y"]))
    #plt.savefig("seaborn_plot.svg")
