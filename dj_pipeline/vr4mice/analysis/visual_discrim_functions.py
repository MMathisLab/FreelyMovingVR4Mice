import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sklearn.linear_model
import sklearn.model_selection


def load_data(path="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/", mouse_name = "Anchovy", date = "2023-02-23", attempt = "2", no_iti = True):
    """
    Load and preprocess behavioral data and box coordinates.

    This function loads behavioral data from a specified file and performs data preprocessing to create a
    pandas DataFrame containing relevant information. It also extracts box coordinates and dimensions
    into a separate DataFrame.

    Note: 
        Currently this function loads from the pickle file - this is tempory and we should use the Datajoint function once everybody is set up

    Parameters:
        path (str): The directory path where the data file is located.
        mouse_name (str): The name of the mouse or subject for which the data is being loaded.
        date (str): The date of the data in the format 'YYYY-MM-DD'.
        attempt (str): The attempt or session number for the data.
        no_iti (bool): A flag indicating whether to exclude inter-trial intervals (ITIs) from the data.

    Returns:
        df (pandas DataFrame): A DataFrame containing the preprocessed behavioral data.
        box_df (pandas DataFrame): A DataFrame containing the coordinates and dimensions of left, right, and target boxes.
    
    """
    
    state_dict = pd.read_pickle(path + mouse_name + "_" + date + "_" + attempt + ".pickle")
    
    df = pd.DataFrame({"step": state_dict ["step"],
                       "step_time": state_dict ["step_time"],
                       "trial": state_dict ["episode"], 
                       "reward": state_dict ["reward"], 
                       "x": state_dict ["state"] [:,0], 
                       "y": state_dict ["state"] [:,1],
                       "aperture":state_dict['slit_size'][state_dict['episode']-1],
                       "head_dir":  state_dict ["state"] [:,2],
                       "mouse_can_report": state_dict ["state"] [:,3],
                       "iti": state_dict ["state"] [:,4], 
                       "object_on_left": state_dict ["state"] [:,5],
                       "mouse_correct": state_dict ["state"] [:,6],
                       "mouse_in_L":  state_dict ["state"] [:,7], 
                       "mouse_in_R":  state_dict ["state"] [:,8]})
    
    df ["head_dir"] = _convert_head_angle(df)
    df = df [df.trial != 1] #NOTE(celia): drop first trial which is DLC-live initialization trial
    
    df.x = np.interp(df.x,  [-9,9], [-27, 27])
    df.y = np.interp(df.y, [-10,-2], [-27, 27])
    
    df ["trial_rewarded"] = df.groupby(["trial"], as_index=False)["reward"].transform(lambda x: x.max())
    df [["trial_step", "trial_step_time"]] = df.groupby(["trial"], as_index = True, group_keys=False)[["step", "step_time"]].apply(lambda x: x.iloc[:] - x.iloc[0])

    if no_iti == True:
        df = df [df.iti == 0.0]
        df ["trial_step_fraction"] = df.groupby(["trial"], as_index = True, group_keys=False)["trial_step"].apply(lambda x: x.iloc[:]/x.iloc [-1])
        df ["trial_R_choice"] = df.groupby(["trial"], as_index=False)["mouse_in_R"].transform(lambda x: x.iloc [-1])
        df ["trial_L_choice"] = df.groupby(["trial"], as_index=False)["mouse_in_L"].transform(lambda x: x.iloc [-1])
    else: 
        df ["trial_step_fraction"] = df.groupby(["trial"], as_index = True, group_keys=False)["trial_step"].apply(lambda x: x.iloc[:]/x.iloc [-1])

    # resampling to 50Hz
    df['time'] = pd.to_datetime(df['step_time'], unit='s')
    df = df.set_index("time").groupby("trial", as_index=False).resample('0.02s').mean().interpolate().reset_index()
    
    reference_datetime = df['time'].iloc[0]
    df['time_elapsed'] = (df['time'] - reference_datetime).dt.total_seconds()
    
    # velocity and acceleration computed from time_elapsed difference (fixed interval)
    df["velocity"] = np.sqrt((np.gradient(df.x, df.time_elapsed)**2) + (np.gradient(df.y, df.time_elapsed) **2))  

    df ["velocity_x"] = np.gradient(df.x, df.time_elapsed)
    df['acceleration_x'] = np.gradient(df['velocity_x'], df.time_elapsed)
    
    df ["velocity_y"] = np.gradient(df.y, df.time_elapsed)
    df['acceleration_y'] = np.gradient(df['velocity_y'], df.time_elapsed)
    
    df ["mouse_name"] = mouse_name
    df ["attempt"] = attempt
    df ["date"] = date 
    
    # Create the box dataframe
    box_df = pd.DataFrame()
    box_df = _define_box(box_df, state_dict, which="left")
    box_df = _define_box(box_df, state_dict, which="right")
    box_df = _define_box(box_df, state_dict, which="tt")
    box_df = box_df.iloc[1]
    
    # Group the trials per x-position at trial initialization
    start, end = box_df["tt_box_x_min"], box_df["tt_box_x_max"]
    x_start_n_bins = 3
    bin_edges = np.linspace(start, end, x_start_n_bins+1)
    bin_midpoints = (bin_edges[:-1] + bin_edges[1:]) / 2

    starting_positions = df.groupby('trial')['x'].first().reset_index()
    starting_positions['bin_idx'] = np.digitize(starting_positions['x'], bin_edges, right=False) - 1  # Adjust bin index to be 0-based
    starting_positions['x_init_bin_center'] = starting_positions['bin_idx'].apply(lambda x: bin_midpoints[x] if x < len(bin_midpoints) else np.nan)

    df = pd.merge(df, starting_positions[['trial', 'x_init_bin_center']], on='trial', how='left')

    return(df, box_df)


def _convert_head_angle(df):
    # this function converts the animals heading direction relative to the screen
    clean_angles = np.rad2deg(np.sin(np.deg2rad(df['head_dir'])))
    return clean_angles


def _define_box(box_df, state_dict, which):
    
    if which == "left":
        l_which = "L"
    elif which == "right":
        l_which = "R"
    elif which == "tt":
        l_which = "TT"
    else:
        raise NotImplementedError()
    
    box_df[f"{which}_box_x_min"] = np.interp(state_dict[f"{l_which}_box_x_min"], [-9, 9], [-27, 27])
    box_df[f"{which}_box_x_max"] = np.interp(state_dict[f"{l_which}_box_x_max"], [-9, 9], [-27, 27])
    box_df[f"{which}_box_z_min"] = np.interp(state_dict[f"{l_which}_box_z_min"], [-10, -2], [-27, 27])
    box_df[f"{which}_box_z_max"] = np.interp(state_dict[f"{l_which}_box_z_max"], [-10, -2], [-27, 27])

    return box_df


def get_rc_params():
    # a function to keep the plot styles similar in the notebooks
    font_color='black'
    font_size=18
    plt.rcParams.update({'text.color' : font_color,
                                'axes.labelcolor' : font_color,
                                'axes.labelsize':font_size,
                                'axes.titleweight': 'bold',
                                'axes.titlesize': font_size,
                                'xtick.labelcolor': font_color,
                                'xtick.labelsize':font_size,
                                'ytick.labelcolor': font_color,
                                'ytick.labelsize': font_size,
                                'font.weight':'bold'
                               })

    plt.rc('axes.spines',top=False,bottom=True,left=True,right=False)
    plt.rc('axes',edgecolor=font_color)


def get_mouse_list():
    #NOTE(tom): This is a temporay function just to keep track of the tolias lab data sets that we have 
    # and so that we can easily import into notebooks
    mouse_list =  [{"mouse_name": "30559", "date":"2024-02-16", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-15", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-14", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-13", "attempt":"1"},
               {"mouse_name": "30561", "date":"2024-02-16", "attempt":"1"}]
    return mouse_list


def get_all_tolias_mice(mouse_list, path):
    """ Grab tolias lab mice and make a big dataframe out of them. """
    big_df = []
    for m in mouse_list:
        df, box_df = load_data(path=path, mouse_name=m["mouse_name"], date=m ["date"], attempt=m ["attempt"])
        big_df.append(df)
    return pd.concat(big_df).reset_index(), box_df


def get_spatial_normalisation_params(data, spatial_ybins = [-13, 24, 50]):
    data["norm_head_dir"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["head_dir"].transform(lambda x: x - np.mean(x.iloc[:5]))
    data["trial_length"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["time_elapsed"].transform(lambda x: x.iloc[-1]-np.mean(x.iloc[:5]))
    data["trial_traj_path_length"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["velocity"].transform("sum")
    data ["trial_init_x"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["x"].transform(lambda x: x.iloc[0])
    data ["trial_init_y"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["y"].transform(lambda y: y.iloc[0])
    data ["trial_end_x"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["x"].transform(lambda x: x.iloc[-1])
    data ["trial_end_y"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["y"].transform(lambda y: y.iloc[-1])
    data ["trial_direct_path"] = np.sqrt((((data.trial_init_x - data.trial_end_x)**2) + (data.trial_init_y - data.trial_end_y)**2))
    data ["trial_tortuosity"] = data.trial_traj_path_length / data.trial_direct_path
    data["bins"] = pd.cut(data["y"], bins = np.linspace(spatial_ybins[0],spatial_ybins[1],spatial_ybins[2])) 
    data["norm_y"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["y"].transform(lambda x: x - x.iloc[0])
    data["norm_x"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["x"].transform(lambda x: x - x.iloc[0])
    data["bin_centers"] = data["bins"].apply(lambda x: x.mid).astype("float") - 25
    return data


def predict_decision(df, label="norm_x", n_splits=10):
    """Predict the decision of the animal based on the `label` data, through a logistic regression.

    Args:
        df: The dataframe.
        label: The name of the column in the `df` dataframe.
        n_splits: The number of splits fo the cross validation.

    Returns:
        The initial dataframe with an extra `pred` column, containing the probability that the 
        animal went to the right.
    """
    
    data = df[label].values
    labels = df.trial_R_choice.values
    
    data = data.reshape(-1,1)
    pred = np.empty((data.shape[0], 2))
    
    kf = sklearn.model_selection.KFold(n_splits=n_splits)
    for i, (train_index, test_index) in enumerate(kf.split(data)):
        clf = sklearn.linear_model.LogisticRegression().fit(data[train_index], labels[train_index])
        pred[test_index] = clf.predict_proba(data[test_index])
        
    df.loc[:,"pred"] = pred[:,1]
    
    return df