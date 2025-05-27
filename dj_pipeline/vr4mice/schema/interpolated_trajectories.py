import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional

import datajoint as dj
import pandas as pd
import numpy as np

from vr4mice.analysis.analysis import get_jshaped_trials
from vr4mice.schema import vr4mice, base_analysis
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "interpolated_trajectories"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class InterpolatedTrials(dj.Computed):
    definition = """
    -> base_analysis.DataFrame
    mouse_name: longblob # mouse name
    aperture: longblob # occlusion aperture size
    trial: longblob # trial number
    trial_length: longblob # the trial progression points
    trial_duration: longblob # trial duration
    trial_tortuosity: longblob # trial tortuosity
    trial_left_choice: longblob # left or right choice for each trial
    trial_rewarded: longblob # whether the trial was rewarded
    x: longblob # x-coordinate of each trial progression point
    y: longblob # y-coordinate of each trial progression point
    x_flipped: longblob # x-coordinate of each trial progression point flipped
    heading_dir: longblob # heading direction of the mouse
    head_angle: longblob # head angle of the mouse
    velocity: longblob # velocity of each trial progression point
    velocity_x: longblob # x-velocity of each trial progression point
    velocity_y: longblob # y-velocity of each trial progression point
    flip_one_side: longblob # vector to flip trajectories across the mid line to align choices
    distance_to_choice: longblob # distance to the choice point
    optimal_p: longblob # optimal p parameter from LP curve fitting
    local_tortuosity: longblob # local tortuosity of the mouse trajectory
    head_angle_sin: longblob # sin of the head angle
    head_angle_cos: longblob # cos of the head angle
    heading_dir_sin: longblob # sin of the heading direction
    heading_dir_cos: longblob # cos of the heading direction
    velocity_x_flipped: longblob # x-velocity of each trial progression point flipped
    """

    def make(self, key):
        from vr4mice.analysis.utils import interpolate_j_shaped

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            if len(base_analysis.DataFrame & key) > 0:
                df = (base_analysis.DataFrame()).get_data(key=key)
                df["trial_rewarded"] = (base_analysis.DataFrame()).get_rewarded(key=key)
                box_df = (base_analysis.BoxDataFrame()).get_data(key=key)
                offline_kinematics_df = (vr4mice.dlc.OfflineKinematics()).get_data(
                    columns=["heading_direction", "head_angle"], key=key
                )
                df = pd.concat([df, offline_kinematics_df], axis=1)
                df = df[df.iti == 0.0]
                df["mouse_name"] = key["dataset"].split("_")[0]
                interpolated_df = interpolate_j_shaped(df, box_df=box_df)
                interpolated_df = interpolated_df.drop(
                    columns=["time", "dataset", "trial_step"]
                )
                interpolated_df["x_flipped"] = df["x"] * df["flip_one_side"]
                self.insert1({**key, **interpolated_df.to_dict()})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


class MeanXYTrajectory(dj.Computed):
    definition = """
    -> InterpolatedTrials
    aperture: longblob # occlusion aperture size for each trial progression point
    trial_left_choice: longblob # left or right choice for each trial
    trial_length: longblob # the trial progression points
    x: longblob # mean x-coordinate of each trial progression point
    y: longblob # mean y-coordinate of each trial progression point
    x_sem: longblob # standard error of the mean x-coordinate of each trial progression point
    y_sem: longblob # standard error of the mean y-coordinate of each trial progression point
    x_std: longblob # standard deviation of the x-coordinate of each trial progression point
    y_std: longblob # standard deviation of the y-coordinate of each trial progression point
    """

    def make(self, key):
        from vr4mice.analysis.analysis import mean_xy_trajectory

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame((InterpolatedTrials()).get_data(
                    columns=[
                        "dataset",
                        "aperture",
                        "trial",
                        "trial_left_choice",
                        "trial_length",
                        "x",
                        "y",
                    ],
                    key=key,
                ))

                mean_df = mean_xy_trajectory(
                    df,
                    index_col=[
                        "dataset",
                        "aperture",
                        "trial",
                        "trial_left_choice",
                        "trial_length",
                    ],
                )
                mean_df = mean_df.drop(columns=["dataset"])
                self.insert1({**key, **mean_df.to_dict()})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


class YBinnedXYTrajectory(dj.Computed):
    definition = """
    -> InterpolatedTrials
    aperture: longblob # occlusion aperture size 
    x_flipped: longblob # x-coordinate for each y bin center
    bin_centers: longblob # y bin centers 
    """

    def make(self, key):
        from vr4mice.analysis.analysis import mean_xy_trajectory
        from vr4mice.analysis.utils import create_bins

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame((InterpolatedTrials()).get_data(
                    columns=["aperture", "trial", "trial_length", "x_flipped", "y"],
                    key=key,
                ))
                mean_df = mean_xy_trajectory(
                    df,
                    index_col=["aperture", "trial", "trial_length"],
                    values=["x_flipped", "y"],
                )
                binned_df = create_bins(mean_df)
                binned_df = binned_df[["aperture", "bin_centers", "x_flipped", "y"]]
                binned_df = binned_df.groupby(
                    ["aperture", "bin_centers"], as_index=False
                ).mean(numeric_only=True)
                self.insert1({**key, **binned_df.to_dict()})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


class MeanVelocities(dj.Computed):
    definition = """
    -> InterpolatedTrials
    aperture: longblob # occlusion aperture size 
    trial_length: longblob # trial length
    velocity: longblob # mean velocity of each trial progression point
    velocity_x: longblob # mean x-velocity of each trial progression point
    velocity_y: longblob # mean y-velocity of each trial progression point
    velocity_x_flipped: longblob # mean x-velocity of each trial progression point flipped
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame(InterpolatedTrials()).get_data(
                    columns=[
                        "aperture",
                        "trial",
                        "trial_length",
                        "velocity",
                        "velocity_x",
                        "velocity_y",
                        "velocity_x_flipped",
                    ],
                    key=key,
                )
                mean_df = df.groupby(["aperture", "trial_length"], as_index=False).mean(
                    numeric_only=True
                )
                self.insert1({**key, **mean_df.to_dict()})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
