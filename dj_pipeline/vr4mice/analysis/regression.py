import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats
import sklearn
import torch
import matplotlib.collections
import sklearn.model_selection
import sklearn.preprocessing

import plotting
import lstm
import seaborn as sns

device = "cuda:0"

def train_lstm(df, 
               label, 
               learning_rate=0.01, 
               weight_decay=0.01,
               num_layers=1, 
               hidden_units=16, 
               output_size=1, 
               num_epochs=1000,
               per_trial=True,
               logger=None):
    """LSTM to predict the decision of the animal.
    
    Sessions and trials are considered independently in the model.
    
    Args:
        df: The dataframe.
        label: The name of the column in the `df` dataframe.
        learning_rate: 
        num_layers: 
        hidden_units: 
        output_size:
        num_epochs:
        per_trial:
        
    Returns:
        The initial dataframe with an extra `pred` column, containing the probability that the 
        animal went to the left.
    """
    
    # Preprocessing
    multi_data = []
    multi_labels = []
    sessions = []
    
    group = "session_trial"

    for session in df[group].unique():
        df_session = df[(df[group]==session)]
        points = df_session[label].values.T
        
        multi_data.append(torch.Tensor(sklearn.preprocessing.StandardScaler().fit_transform(points.T))[:,None,:])
        multi_labels.append(torch.Tensor(np.expand_dims(df_session.trial_L_choice.values, axis=1).astype(int)))
        sessions.append(df_session["session"].values[0])
    
    #logger.info(np.unique(np.array(sessions)).shape)
    
    # Data splitting per trial, so that balanced between sessions
    indices = np.arange(len(sessions))
    
    sss = sklearn.model_selection.StratifiedShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
    train_indices, val_indices = next(sss.split(indices, sessions))
    
    #logger.info(len(train_indices))
    #logger.info(len(val_indices))

    sessions_data = [multi_data[i] for i in train_indices]
    sessions_val_data = [multi_data[i] for i in val_indices]
    
    sessions_labels = [multi_labels[i] for i in train_indices]
    sessions_val_labels = [multi_labels[i] for i in val_indices]

    # Define the model & parameters
    model = lstm.LSTMModel(input_size=sessions_data[0].shape[-1], 
                           hidden_units=hidden_units, 
                           output_size=output_size,
                           num_layers=num_layers, 
                           device=device).to(device)

    criterion = torch.nn.MSELoss()  # For regression tasks; use nn.CrossEntropyLoss() for classification
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    for epoch in range(num_epochs):
        model.train()
        for session_data, session_label in zip(sessions_data, sessions_labels):
            session_data, session_label = session_data.to(device), session_label.to(device)
            model.hidden = model.init_hidden(batch_size=1)#session_data.shape[0])
            
            optimizer.zero_grad()
            
            outputs = model(session_data)
            loss = criterion(outputs, session_label)
            
            loss.backward()
            optimizer.step()
        
        if epoch % 10 == 0:
            model.eval()
            with torch.no_grad():
                test_losses = []
                for test_data, test_label in zip(sessions_val_data, sessions_val_labels):
                    test_data, test_label = test_data.to(device), test_label.to(device)
                    model.hidden = model.init_hidden(batch_size=1)#test_data.shape[0])

                    test_outputs = model(test_data)
                    test_loss = criterion(test_outputs, test_label)
                    test_losses.append(test_loss.item())

                avg_test_loss = sum(test_losses) / len(test_losses)
                if logger is not None: 
                    logger.info(f'Epoch [{epoch}/{num_epochs}], Train Loss: {loss.item():.4f}, Test Loss: {avg_test_loss:.4f}')
                else: 
                    print(f'Epoch [{epoch}/{num_epochs}], Train Loss: {loss.item():.4f}, Test Loss: {avg_test_loss:.4f}')
    
    # Inference for all sessions, using trained model
    model.to(device)
    model.eval()

    outputs = []
    with torch.no_grad():
        for session_data in multi_data:
            model.hidden = model.init_hidden(batch_size=1)#session_data.shape[0])
            
            session_data = session_data.to(device)
            outputs.append(model(session_data).detach().cpu().numpy())
    
    
    df.loc[:, "pred"] = np.concatenate(outputs)
    return df, model, val_indices
    
def train_logistic_regression(df, label="norm_x", n_splits=10, per_mouse=False):
    """Logistic regression to predict th decision of the animal.
    
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
        animal went to the left.
    """

    data = df[label].values
    labels = df.trial_L_choice.values

    if not isinstance(label, list):
        data = data.reshape(-1, 1)
    pred = np.empty((data.shape[0], 2))

    model = sklearn.linear_model.LogisticRegression()

    if per_mouse:
        sessions = df.session.values
        logo = sklearn.model_selection.LeaveOneGroupOut()
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



def predict_decision(df, label, model, model_args): 
    if model == "logistic_regression": 
        df, model = train_logistic_regression(df, label, 
                                    n_splits=model_args["n_splits"], 
                                    per_mouse=model_args["per_mouse"])
    elif model == "lstm": 
        df, model, _ = train_lstm(df, label,
                                 learning_rate=model_args["lr"],
                                 num_layers=model_args["num_layers"], 
                                 hidden_units=model_args["hidden_units"],
                                 num_classes=model_args["num_classes"],
                                 num_epochs=model_args["num_epochs"])
        
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
    if all(trial_data["trial_L_choice"] > 0.5):
        above_threshold = trial_data[trial_data['pred'] > threshold_right]
    else:
        above_threshold = trial_data[trial_data['pred'] < threshold_left]

    for index in above_threshold.index:
        subsequent_values = trial_data.loc[index:]['pred']
        if all(trial_data["trial_L_choice"] > 0.5) and all(
                subsequent_values >= above_threshold.loc[index, 'pred']):
            # Returning the step of the decision point
            return trial_data.loc[index]
        elif all(trial_data["trial_L_choice"] < 0.5) and all(
                subsequent_values <= above_threshold.loc[index, 'pred']):
            return trial_data.loc[index]


def plot_proba_per_trial(df, trials, time=False, logdir=None, save=None):
    fig, ax = plt.subplots(5, 3, figsize=(15, 15))
    ax = ax.flatten()
    for session_id, session in enumerate(df.session.unique()):
        for trial_id, trial in df[df["session"] == session].groupby(["session_trial"]):
            if trial_id[0] in trials:
                
                # Reset index within each group for a uniform timescale
                trial = trial.reset_index(drop=True)
                if time: 
                    trial["pred"].plot(ax=ax[session_id])
                else:
                    sns.lineplot(data=trial,
                                x="bin_centers",
                                y="pred",
                                ax=ax[session_id],
                                errorbar="se")
            else:
                continue

    if save is not None:
        plt.savefig(logdir + f"{save}_proba_plot.png")


def plot_decision_points_on_trajectory(df,
                                       df_box,
                                       decision_point=None,
                                       color="red",
                                       trials=list(range(25, 30)),
                                       ax=None,
                                       logdir=None,
                                       save=None):
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

    for trial in df.session_trial.unique():
        if trial in trials:

            points = np.array([
                df[df["session_trial"] == trial]["x"],
                df[df["session_trial"] == trial]["y"]
            ]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)

            lc = matplotlib.collections.LineCollection(segments,
                                cmap='PuOr_r',
                                norm=plt.Normalize(0, 1))
            lc.set_array(df[df["session_trial"] == trial]["pred"])
            lc.set_linewidth(2)

            ax.add_collection(lc)
            ax.autoscale()
            ax.margins(0.1)

            if decision_point is not None:
                mpl.rcParams['lines.markersize'] = 10
                ax.scatter(
                    decision_point[df["session_trial"] == trial]["x"],
                    decision_point[df["session_trial"] == trial]["y"],
                    color=color)

            ax.legend([], [], frameon=False)
        else:
            continue
        
    if save is not None:
        plt.savefig(logdir + f"{save}_trajectories_plot.png")


def find_decision_point_from_distance(trial_data, df_box):
    #print(trial_data["trial"].values[0], trial_data["session"].values[0])

    if all(trial_data["trial_L_choice"] > 0.5):
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

    if all(trial_data["trial_L_choice"] > 0.5):
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

    if all(trial_data["trial_L_choice"] > 0.5):
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


def pair_plot(decision_point, ax=None, save=False):

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
    
    if save:
        plt.savefig("pair_plot.svg")

