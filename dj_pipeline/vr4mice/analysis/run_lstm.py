import numpy as np
import argparse
import pandas as pd

import logging

logger = logging.getLogger(__name__)

import regression
import visual_discrim_functions

import matplotlib.pyplot as plt
import seaborn as sns

import torch

parser = argparse.ArgumentParser()
parser.add_argument(
    "--datapath",
    type=str,
    default="/home/celia/FreelyMovingVR4Mice/dj_pipeline/vr4mice/analysis/"
)
parser.add_argument(
    "--logdir",
    type=str,
    default="/home/celia/FreelyMovingVR4Mice/dj_pipeline/vr4mice/analysis/logs/"
)
parser.add_argument("--learning_rate", type=float, default=0.01)
parser.add_argument("--num_layers", type=int, default=1)
parser.add_argument("--hidden_units", type=int, default=16)
parser.add_argument("--output_size", type=int, default=1)
parser.add_argument("--num_epochs", type=int, default=100)
parser.add_argument("--per_trial", action="store_true")
parser.add_argument("--features", type=str, default="all_norm")
parser.add_argument("--interpolation", action="store_true")
parser.add_argument("--simple", action="store_true")

ARGS = parser.parse_args()


colors_choice = ["#5C0A72", '#FD672C']
colors_aperture = ['#E41A1C', '#437FB5']
colors_aperture_pale = ['#EC8788', '#96B9D6']


ALL_FEATURES = ["x", "y", "heading_dir", "head_angle", 
          "trial_tortuosity", "trial_init_x", 
          "trial_duration", "norm_y", "norm_x", 
          "trial_init_y", "binary_aperture", "velocity", 
          "acceleration_x", "heading_dir_velocity", 
          "trial_traj_path_length", "trial_rewarded",
          "heading_dir_acceleration"]


def get_features(features_set):

    if features_set == "all_norm":
        features = [
            "norm_x", "norm_y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_duration", "trial_init_x", "trial_init_y", "binary_aperture",
            "trial_traj_path_length", "trial_rewarded",
        ]
        names = [
            "x", "y", "head", "body", "tort", "duration", "init_x", "init_y",
            "aperture", "trial_length", "trial_rewarded"
        ]
    elif features_set == "norm": 
        features = [
            "norm_x", "norm_y"
        ]
        names = ["norm_x", "norm_y"]
    else:
        raise NotImplementedError()

    return features, names


def add_params(df):
    df["choice"] = df.trial_L_choice.replace([0, 1], ["right", "left"])
    df["flip_one_side"] = df["trial_L_choice"].replace([0, 1], [1, -1])
    df['distance_to_reward'] = np.sqrt((df_box["right_box_x_center"]-(df['x']*df["flip_one_side"]))**2 + (df_box['right_box_z_center']  - df['y'])**2)
    df["flip_one_side"] = df["trial_L_choice"].replace([0, 1], [1, -1])
    df["fliped_x"] = df.x * df.flip_one_side
    df["fliped_norm_x"] = df.norm_x * df.flip_one_side
    bins = [-20.25, 24, 70]
    df = visual_discrim_functions.create_bins(data=df, spatial_ybins=bins)
    df["binary_aperture"] = (df["aperture"] > 7).astype(int)
    df['distance_to_reward'] = np.sqrt((df_box["right_box_x_center"]-(df['x']*df["flip_one_side"]))**2 + (df_box['right_box_z_center']  - df['y'])**2)
    return df

if __name__ == "__main__":

    save_path = f"{ARGS.num_epochs}_{ARGS.hidden_units}_{ARGS.learning_rate}_{ARGS.features}"

    logging.basicConfig(filename=ARGS.logdir + f'{save_path}_logging.log',
                        level=logging.INFO)
    logger.info('Started')

    df = pd.read_pickle(ARGS.datapath + "df.pickle")
    df_box = pd.read_pickle(ARGS.datapath + "df_box.pickle")
    
    df_simple = df[(df.trial_duration<=5) & (df.trial_rewarded > 0.5) & (df.trial_tortuosity <= 5)]

    df = add_params(df)
    df_simple = add_params(df_simple)
    
    if ARGS.simple:
        df = df_simple
        
    features, names = get_features(ARGS.features)

    # INTERPOLATION
    res = visual_discrim_functions.interpolate(df, n_points=200, value_columns=["trial_L_choice"]+ALL_FEATURES)
    res["trial_step"] = res.groupby(["session", "trial"]).trial.cumcount()
    res["trial_length"] = res["trial_step"]/200
    res["flip_one_side"] = res["trial_L_choice"].replace([0, 1], [1, -1])
    res["session_trial"] = res['session'].astype(str) + '_' + res['trial'].astype(str)
    df = res

    # Train model
    pred_tot, model, val_index = regression.train_lstm(df=res,
                                      label=features,
                                      learning_rate=ARGS.learning_rate,
                                      num_layers=ARGS.num_layers,
                                      hidden_units=ARGS.hidden_units,
                                      output_size=ARGS.output_size,
                                      num_epochs=ARGS.num_epochs,
                                      per_trial=ARGS.per_trial,
                                      logger=logger)
    
    pred_tot["pred_binary"] = pred_tot['pred'].apply(lambda x: 1 if x >= 0.5 else 0)
    pred_tot["accuracy"] = (pred_tot["trial_L_choice"] == pred_tot["pred_binary"]).astype(int)
    
    pred_tot_val = pred_tot[pred_tot.trial.isin(val_index)]
    pred_tot_train = pred_tot[~pred_tot.trial.isin(val_index)]
    
    fig, ax = plt.subplots(3, 2, figsize=(17, 12))

    for i, df in enumerate([pred_tot, pred_tot_train, pred_tot_val]):
        mean_mouse = df.groupby(["session", "trial_L_choice", "binary_aperture", "trial_length"]).mean(numeric_only=True)
        sns.lineplot(ax=ax[i][1], data=mean_mouse, y="pred", x="trial_length", 
                                    hue="trial_L_choice", style="binary_aperture", palette=colors_choice)

        mean_mouse = df.groupby(["session", "binary_aperture", "trial_length"]).sum(numeric_only=True) / df.groupby(["session", "binary_aperture", "trial_length"]).count()
        sns.lineplot(ax=ax[i][0], data=mean_mouse, y="accuracy", x="trial_length", 
                                hue="binary_aperture", palette=colors_aperture, errorbar='se')

    #ax[i][0].set_ylim(0.4, 1)
    plt.tight_layout(pad=1.0)
    fig.savefig(ARGS.logdir + f"{save_path}_plot.png")
    torch.save(model, ARGS.logdir + f"{save_path}_model.pt")

    
    # regression.plot_proba_per_trial(df,
    #                                 trials=df["session_trial"].unique()[val_index],
    #                                 logdir=ARGS.logdir,
    #                                 save=save_path)
    
    # regression.plot_proba_per_trial(df,
    #                                 trials=df["session_trial"].unique()[val_index],
    #                                 logdir=ARGS.logdir,
    #                                 time=True,
    #                                 save=save_path + "time_")


    # regression.plot_decision_points_on_trajectory(df,
    #                                               df_box,
    #                                               trials=df["session_trial"].unique()[val_index],
    #                                               logdir=ARGS.logdir,
    #                                               save=save_path)