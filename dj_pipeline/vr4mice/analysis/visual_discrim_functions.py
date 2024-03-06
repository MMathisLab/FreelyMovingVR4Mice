
import pandas as pd
import numpy as np
import sklearn.linear_model
import sklearn.model_selection
import scipy.interpolate
import matplotlib.pyplot as plt
import seaborn as sns



def load_data(path: str="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/", 
              mouse_name: str="Anchovy", 
              date: str="2023-02-23", 
              attempt: str="2", 
              no_iti: bool=True, 
              first_n_samples: int=5):
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
        first_n_sample (int): The first n samples to average to normalize trajectories.
    
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
    df["norm_head_dir"] = df.groupby("trial", as_index=False)["head_dir"].transform(lambda x: x - np.mean(x.iloc[:first_n_samples]))

    df = df [df.trial != 1] #NOTE(celia): drop first trial which is DLC-live initialization trial
    
    df["x"] = np.interp(df.x,  [-9,9], [-27, 27])
    df["norm_x"] = df.groupby("trial", as_index=False)["x"].transform(lambda x: x - x.iloc[0])

    df["y"] = np.interp(df.y, [-10,-2], [-27, 27])
    df["norm_y"] = df.groupby("trial", as_index=False)["y"].transform(lambda x: x - x.iloc[0])

    
    df ["trial_rewarded"] = df.groupby("trial", as_index=False)["reward"].transform(lambda x: x.max())
    df [["trial_step", "trial_step_time"]] = df.groupby("trial", as_index = True, group_keys=False)[["step", "step_time"]].apply(lambda x: x.iloc[:] - x.iloc[0])

    if no_iti == True:
        df = df [df.iti == 0.0]
        df ["trial_step_fraction"] = df.groupby("trial", as_index = True, group_keys=False)["trial_step"].apply(lambda x: x.iloc[:]/x.iloc [-1])
        df ["trial_R_choice"] = df.groupby("trial", as_index=False)["mouse_in_R"].transform(lambda x: x.iloc [-1])
        df ["trial_L_choice"] = df.groupby("trial", as_index=False)["mouse_in_L"].transform(lambda x: x.iloc [-1])
    else: 
        df ["trial_step_fraction"] = df.groupby("trial", as_index = True, group_keys=False)["trial_step"].apply(lambda x: x.iloc[:]/x.iloc [-1])

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
    
    df["trial_length"] = df.groupby("trial", as_index=False)["time_elapsed"].transform(lambda x: x.iloc[-1]-np.mean(x.iloc[:5]))
    df["trial_traj_path_length"] = df.groupby("trial", as_index=False)["velocity"].transform("sum")
    df ["trial_init_x"] = df.groupby("trial", as_index=False)["x"].transform(lambda x: x.iloc[0])
    df ["trial_init_y"] = df.groupby("trial", as_index=False)["y"].transform(lambda y: y.iloc[0])
    df ["trial_end_x"] = df.groupby("trial", as_index=False)["x"].transform(lambda x: x.iloc[-1])
    df ["trial_end_y"] = df.groupby("trial", as_index=False)["y"].transform(lambda y: y.iloc[-1])
    df ["trial_direct_path"] = np.sqrt((((df.trial_init_x - df.trial_end_x)**2) + (df.trial_init_y - df.trial_end_y)**2))
    df ["trial_tortuosity"] = df.trial_traj_path_length / df.trial_direct_path
    
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

    mouse_list =  [
               {"mouse_name": "30559", "date":"2024-02-26", "attempt":"1"}, #0
               {"mouse_name": "30559", "date":"2024-02-20", "attempt":"1"}, #1
               {"mouse_name": "30559", "date":"2024-02-19", "attempt":"1"}, #2
               {"mouse_name": "30559", "date":"2024-02-16", "attempt":"1"}, #3
               {"mouse_name": "30559", "date":"2024-02-15", "attempt":"1"}, #4
               {"mouse_name": "30559", "date":"2024-02-14", "attempt":"1"}, #5
               {"mouse_name": "30559", "date":"2024-02-13", "attempt":"1"}, #6
               {"mouse_name": "30561", "date":"2024-02-16", "attempt":"1"}, #7
               {"mouse_name": "30561", "date":"2024-02-19", "attempt":"1"}, #8
               {"mouse_name": "30561", "date":"2024-02-20", "attempt":"1"}, #9
               {"mouse_name": "30561", "date":"2024-02-21", "attempt":"1"}, #10
               {"mouse_name": "30561", "date":"2024-02-22", "attempt":"1"}, #11
               {"mouse_name": "30561", "date":"2024-02-23", "attempt":"1"}, #12
               #{"mouse_name": "30561", "date":"2024-02-26", "attempt":"1"}, # more aperture sizes
            ]
    return mouse_list


def get_all_tolias_mice(mouse_list, path):
    """ Grab tolias lab mice and make a big dataframe out of them. """
    big_df = []
    for m in mouse_list:
        df, box_df = load_data(path=path, mouse_name=m["mouse_name"], date=m ["date"], attempt=m ["attempt"])
        big_df.append(df)
    return pd.concat(big_df).reset_index(), box_df



def create_bins(data, spatial_ybins = [-13, 24, 50]): 
    """Create bins on the y axis of the data.

    Args:
        data: A dataframe.
        spatial_ybins (List[int]): 3 values list, respectively first and last values to consider and number of bins to consider.

    Returns:
        The dataframe with 2 extra columns, the bin corresponding to each sample, and the center of that interval.
    
    """
    data["bins"] = pd.cut(data["y"], bins = np.linspace(spatial_ybins[0],spatial_ybins[1],spatial_ybins[2])) 
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


def interpolate_group(group, n_points, interpolation_columns, value_columns):
    """Interpolate for the provided group of data.

    Args:
        group: A dataframe containing the data to interpolate.
        num_points (int): the number of points to interpolate.
        interpolation_columns (List[str]): List of the names of the columns to group the data by.
        value_columns (List[str]): List of the names of the columns containing the values to interpolate.

    Returns:
        pandas DataFrame of length `n_points`, containing the interpolated data and the interpolation 
        columns data for all groups.

    """
    # Generate new evenly spaced x values within the original range for interpolation
    x_new = np.linspace(group.index.min(), group.index.max(), n_points)
    
    # Retrieve groupby identifiers (they are uniform within the group)
    ids = {}
    for group_column in interpolation_columns:
        ids[group_column] = group[group_column].iloc[0]
    
    # Dictionary to collect new interpolated values
    interpolated_data = {'time': x_new}
    
    for column in value_columns:
        x = group.index
        y = group[column]
        
        # Fit Cubic Spline
        cs = scipy.interpolate.CubicSpline(x, y)
        
        # Interpolate y values at the new x positions
        y_new = cs(x_new)
        
        # Store the interpolated values
        interpolated_data[column] = y_new
    
    interpolated_df = pd.DataFrame(interpolated_data)
    
    for group_column in interpolation_columns:
        interpolated_df[group_column] = ids[group_column]
    
    return interpolated_df



def interpolate(df, n_points=100, interpolation_columns=["mouse_name", "date", "attempt", "trial"], value_columns=["x", "norm_x", "velocity", "head_dir"]):
    """
    Interpolates the variables in the value columns provided for each group formed by the interpolation columns.
    
    Note: Check keys of the output for interpolated_df attributes.
    Note: By default group the data frame by ["mouse_name", "date", "attempt", "trial"].

    The dataframe is grouped by `interpolation_columns` and the values contained in the columns 
    `value_columns` are interpolated so that each group is `n_points` samples.
    
    Args:
        df: pandas DataFrame containing the data to be interpolated.
        num_points (int): the number of points to interpolate.
        interpolation_columns (List[str]): List of the names of the columns to group the data by.
        value_columns (List[str]): List of the names of the columns containing the values to interpolate.

    Returns:
        pandas DataFrame containing the interpolated data and the interpolation columns data for all groups.
    """
    interpolated_dfs = []

    # Compute the interpolation for each trial
    interpolated_dfs = [interpolate_group(group, n_points, interpolation_columns, value_columns) for _, group in df.groupby(interpolation_columns)]
    final_interpolated_df = pd.concat(interpolated_dfs).reset_index(drop=True)
    
    return final_interpolated_df





def calculate_choice_bin(df, trial_rewarded = 0.5, trial_tortuosity_thresh = 100):
    mean_mice = df.groupby(["mouse_name", "date", "attempt", "aperture", "trial_L_choice", "bin_centres"], as_index=False).mean(numeric_only=True)
    mean_mice ["over_bound"] = (abs(mean_mice.norm_x) > 5).diff() > 0
    mean_mice ["y_over_bound"] = mean_mice ["bin_centres"] [mean_mice ["over_bound"]]
    mean_mice = mean_mice [(mean_mice ["bin_centres"] > -20) & (mean_mice ["bin_centres"] < -5)]
    mean_mice = mean_mice.dropna().copy()
    mean_mice = mean_mice.groupby(["mouse_name", "date", "attempt", "aperture"], as_index=False).last()
    plt.figure(figsize=(3,6))
    sns.lineplot(data=mean_mice, x="aperture", y="y_over_bound", estimator =None, units=zip(mean_mice.mouse_name, mean_mice.date), sort=False, color="black", alpha=0.5)
    sns.scatterplot(data=mean_mice, x="aperture", y="y_over_bound", color="black")
    plt.xlim(0,15)
    plt.ylim(-15,0)
    plt.xlabel("aperture")
    plt.ylabel("Distance from screen (cm)")
    return(mean_mice)


def plot_choice_per_mouse(df, mouse_list):
    fig, ax = plt.subplots(4,3, figsize=(20,20), sharex=True, sharey=True)
    ax = ax.ravel()
    for i in range(len(mouse_list)):
        m = mouse_list [i]
        mouse = df [(df.mouse_name == m["mouse_name"]) &  (df.date == m["date"])]

        
        mouse = mouse [mouse.trial_rewarded > 0.5]
        mouse = mouse [mouse.trial_tortuosity < 100]
        sns.lineplot(data = mouse,x= "bin_centres", 
                             y="norm_x", style="aperture", hue="trial_L_choice",
                             errorbar="se", palette= ['#FD672C', "#5C0A72"], ax= ax[i])
        ax[i].set_ylabel("x (normalised)")
        ax[i].set_xlabel("Distance to screen (cm)")
        ax[i].set_title(str(mouse.mouse_name.iloc [0]) + "_"  + str(mouse.date.iloc [0]))

