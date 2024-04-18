import numpy as np
import argparse
import pandas as pd

import logging

logger = logging.getLogger(__name__)

import lstm
import regression

parser = argparse.ArgumentParser()
parser.add_argument(
    "--datapath",
    type=str,
    default="/home/celia/FreelyMovingVR4Mice/dj_pipeline/vr4mice/analysis/")
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

ARGS = parser.parse_args()


def get_features(features_set):

    if features_set == "all_norm":
        features = [
            "norm_x", "y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_init_x", "trial_length", "trial_init_y", "binary_aperture",
            "velocity", "acceleration_x", "heading_dir_velocity",
            "heading_dir_acceleration"
        ]
        names = [
            "x", "y", "head", "body", "tort", "init_x", "length", "init_y",
            "aperture", "velocity", "acceleration", "heading_dir_velocity",
            "heading_dir_acceleration"
        ]
    elif features_set == "all":
        features = [
            "x", "y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_init_x", "trial_length", "trial_init_y", "binary_aperture",
            "velocity", "acceleration_x", "heading_dir_velocity",
            "heading_dir_acceleration"
        ]
        names = [
            "x", "y", "head", "body", "tort", "init_x", "length", "init_y",
            "aperture", "velocity", "acceleration", "heading_dir_velocity",
            "heading_dir_acceleration"
        ]
    elif features_set == "pos_norm":
        features = [
            "x", "y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_init_x", "trial_length", "trial_init_y", "binary_aperture"
        ]
        names = [
            "x", "y", "head", "body", "tort", "init_x", "length", "init_y",
            "aperture"
        ]
    elif features_set == "pos":
        features = [
            "x", "y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_init_x", "trial_length", "trial_init_y", "binary_aperture"
        ]
        names = [
            "x", "y", "head", "body", "tort", "init_x", "length", "init_y",
            "aperture"
        ]
    elif features_set == "pos_no_aperture":
        features = [
            "x", "y", "heading_dir", "head_angle", "trial_tortuosity",
            "trial_init_x", "trial_length", "trial_init_y"
        ]
        names = [
            "x", "y", "head", "body", "tort", "init_x", "length", "init_y"
        ]

    else:
        raise NotImplementedError()

    return features, names


if __name__ == "__main__":

    save_path = f"{ARGS.num_epochs}_{ARGS.hidden_units}_{ARGS.learning_rate}_{ARGS.features}"

    logging.basicConfig(filename=ARGS.logdir + f'{save_path}_logging.log',
                        level=logging.INFO)
    logger.info('Started')

    df = pd.read_pickle(ARGS.datapath + "df.pickle")
    df_box = pd.read_pickle(ARGS.datapath + "df_box.pickle")

    df["binary_aperture"] = (df["aperture"] > 7).astype(int)

    features, names = get_features(ARGS.features)

    df["session_trial"] = df['session'].astype(str) + '_' + df['trial'].astype(
        str)

    # Train model
    df, model, val_index = regression.train_lstm(df,
                                      label=features,
                                      learning_rate=ARGS.learning_rate,
                                      num_layers=ARGS.num_layers,
                                      hidden_units=ARGS.hidden_units,
                                      output_size=ARGS.output_size,
                                      num_epochs=ARGS.num_epochs,
                                      per_trial=ARGS.per_trial,
                                      logger=logger)


    # Save plots of interest
    regression.plot_proba_per_trial(df,
                                    trials=df["session_trial"].unique()[val_index],
                                    logdir=ARGS.logdir,
                                    save=save_path)
    
    regression.plot_proba_per_trial(df,
                                    trials=df["session_trial"].unique()[val_index],
                                    logdir=ARGS.logdir,
                                    time=True,
                                    save=save_path + "time_")


    regression.plot_decision_points_on_trajectory(df,
                                                  df_box,
                                                  trials=df["session_trial"].unique()[val_index],
                                                  logdir=ARGS.logdir,
                                                  save=save_path)

