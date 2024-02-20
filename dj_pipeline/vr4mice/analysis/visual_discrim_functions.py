import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os 
from scipy.interpolate import CubicSpline
from scipy import stats
from scipy.signal import savgol_filter, hilbert, find_peaks


def load_data(path="/Users/thomassainsbury/Documents/Mathis_lab/Aug_Reg/AR_example_data/", mouse_name = "Anchovy", date = "2023-02-23", attempt = "2", no_iti = True):
    """
    Load and preprocess behavioral data and box coordinates.

    This function loads behavioral data from a specified file and performs data preprocessing to create a
    pandas DataFrame containing relevant information. It also extracts box coordinates and dimensions
    into a separate DataFrame.

    currently this function loads from the pickle file - this is tempory and we should use the Datajoint function once everybody is set up

    Parameters:
    - path (str): The directory path where the data file is located.
    - mouse_name (str): The name of the mouse or subject for which the data is being loaded.
    - date (str): The date of the data in the format 'YYYY-MM-DD'.
    - attempt (str): The attempt or session number for the data.
    - no_iti (bool): A flag indicating whether to exclude inter-trial intervals (ITIs) from the data.

    Returns:
    - df (pandas DataFrame): A DataFrame containing the preprocessed behavioral data.
    - box_df (pandas DataFrame): A DataFrame containing the coordinates and dimensions of left, right,
      and target boxes.
    
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
    
    df ["velocity"] = np.sqrt((np.gradient(df.x)**2) + (np.gradient(df.y) **2)) * (1/np.mean(df.step_time.diff()))
    df ["head_dir"] = convert_angles(df)
    df = df [df.trial != 1]
    df.x = np.interp(df.x,  [-9,9], [-27, 27])
    df.y = np.interp(df.y, [-10,-2], [-27, 27])

   
    box_df = pd.DataFrame()
    box_df ["left_box_x_min"] = np.interp(state_dict ["L_box_x_min"],  [-9,9], [-27, 27])
    box_df ["left_box_x_max"] = np.interp(state_dict ["L_box_x_max"],  [-9,9], [-27, 27])
    box_df ["left_box_z_min"] = np.interp(state_dict ["L_box_z_min"],  [-10,-2], [-27, 27])
    box_df ["left_box_z_max"] = np.interp(state_dict ["L_box_z_max"],  [-10,-2], [-27, 27])
    
    box_df["right_box_x_min"] = np.interp(state_dict ["R_box_x_min"],  [-9,9], [-27, 27])
    box_df["right_box_x_max"] = np.interp(state_dict ["R_box_x_max"],  [-9,9], [-27, 27])
    box_df["right_box_z_min"] = np.interp(state_dict ["R_box_z_min"],  [-10,-2], [-27, 27])
    box_df["right_box_z_max"] = np.interp(state_dict ["R_box_z_max"],  [-10,-2], [-27, 27])
    
    box_df["tt_box_x_min"] = np.interp(state_dict ["TT_box_x_min"],  [-9,9], [-27, 27])
    box_df["tt_box_x_max"] = np.interp(state_dict ["TT_box_x_max"],  [-9,9], [-27, 27])
    box_df["tt_box_z_min"] = np.interp(state_dict ["TT_box_z_min"],  [-10,-2], [-27, 27])
    box_df["tt_box_z_max"] = np.interp(state_dict ["TT_box_z_max"],  [-10,-2], [-27, 27])
    
    df ["trial_rewarded"] = df.groupby(["trial"], as_index=False)["reward"].transform(lambda x: x.max())
   
    df [["trial_step", "trial_step_time"]] = df.groupby(["trial"], as_index = True, group_keys=False).apply(lambda x: x.iloc[:] - x.iloc [0])[["step", "step_time"]]
    

    box_df = box_df.iloc [1]
    
    if no_iti == True:
        df = df [df.iti == 0.0]
        df ["trial_step_fraction"] = df.groupby(["trial"], as_index = True, group_keys=False).apply(lambda x: x.iloc[:]/x.iloc [-1])["trial_step"]
        df ["trial_R_choice"] = df.groupby(["trial"], as_index=False)["mouse_in_R"].transform(lambda x: x.iloc [-1])
        df ["trial_L_choice"] = df.groupby(["trial"], as_index=False)["mouse_in_L"].transform(lambda x: x.iloc [-1])
    else: 
        df ["trial_step_fraction"] = df.groupby(["trial"], as_index = True, group_keys=False).apply(lambda x: x.iloc[:]/x.iloc [-1])["trial_step"]
    
    df ["mouse_name"] = mouse_name
    df ["attempt"] = attempt
    df ["date"] = date 
    return(df, box_df)

def convert_angles(df):
    # this function converts the animals heading direction relative to the screen
    clean_angles = np.rad2deg(np.sin(np.deg2rad(df['head_dir'])))
    return clean_angles


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
    # this is a temporay function just to keep track of the tolias lab data sets that we have 
    # and so that we can easily import into notebooks
    mouse_list =  [{"mouse_name": "30559", "date":"2024-02-16", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-15", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-14", "attempt":"1"},
               {"mouse_name": "30559", "date":"2024-02-13", "attempt":"1"},
               {"mouse_name": "30561", "date":"2024-02-16", "attempt":"1"}]
    return(mouse_list)


def get_all_tolias_mice(mouse_list, path):
    # function to grab tolias lab mice and make a big dataframe out of them
    big_df = []
    for m in mouse_list:
        big_df.append(load_data(path=path, mouse_name=m["mouse_name"], date=m ["date"], attempt=m ["attempt"])[0])
    return(pd.concat(big_df).reset_index())


def get_spatial_normalisation_params(data, spatial_ybins = [-10, 24, 50]):
    data["norm_head_dir"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["head_dir"].transform(lambda x: x - x.iloc[0])
    data["trial_length"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["step_time"].transform(lambda x: x.iloc[-1]-x.iloc[0])["step_time"]
    data["bins"] = pd.cut(data["y"], bins = np.linspace(spatial_ybins[0],spatial_ybins[1],spatial_ybins[2])) 
    data["norm_y"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["y"].transform(lambda x: x - x.iloc[0])
    data["norm_x"] = data.groupby(["mouse_name", "date", "attempt", "trial"], as_index=False)["x"].transform(lambda x: x - x.iloc[0])
    data["bin_centres"] = data["bins"].apply(lambda x: x.mid).astype("float") - 25
    return(data)