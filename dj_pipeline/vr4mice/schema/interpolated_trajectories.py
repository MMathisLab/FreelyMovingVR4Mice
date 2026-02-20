"""Interpolated trajectory schema used for downstream analysis tables."""

import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional

import datajoint as dj
import pandas as pd
import numpy as np

from vr4mice.analysis.analysis import get_jshaped_trials
from vr4mice.schema import vr4mice, base_analysis, dlc
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "interpolated_trajectories"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class InterpolatedTrials(dj.Computed):
    definition = """
    -> base_analysis.DataFrame
    ---
    aperture: <blob>          # occlusion aperture size
    trial: <blob>             # trial number
    trial_length: <blob>      # the trial progression points
    trial_duration: <blob>    # trial duration
    trial_tortuosity: <blob>  # trial tortuosity
    trial_left_choice: <blob> # left or right choice for each trial
    trial_rewarded: <blob>    # whether the trial was rewarded
    x: <blob>                 # x-coordinate of each trial progression point
    y: <blob>                 # y-coordinate of each trial progression point
    x_flipped: <blob>         # x-coordinate of each trial progression point flipped
    heading_dir: <blob>       # heading direction of the mouse
    head_angle: <blob>        # head angle of the mouse
    velocity: <blob>          # velocity of each trial progression point
    velocity_x: <blob>        # x-velocity of each trial progression point
    velocity_y: <blob>        # y-velocity of each trial progression point
    flip_one_side: <blob>     # vector to flip trajectories across the mid line to align choices
    distance_to_choice: <blob> # distance to the choice point
    optimal_p: <blob>         # optimal p parameter from LP curve fitting
    local_tortuosity: <blob>  # local tortuosity of the mouse trajectory
    head_angle_sin: <blob>    # sin of the head angle
    head_angle_cos: <blob>    # cos of the head angle
    heading_dir_sin: <blob>   # sin of the heading direction
    heading_dir_cos: <blob>   # cos of the heading direction
    velocity_x_fliped: <blob> # x-velocity of each trial progression point flipped
    """

    def make(self, key):
        """Interpolate trials and store per-trial trajectories."""
        from vr4mice.analysis.utils import interpolate_j_shaped

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            if len(base_analysis.DataFrame & key) > 0:

                logger.info(f"{self.__class__.__name__}: populate key: {key}")
                df = (base_analysis.DataFrame()).get_data(key=key)
                df["trial_rewarded"] = (base_analysis.DataFrame()).get_rewarded(key=key)
                box_df = (base_analysis.BoxDataFrame()).get_data(key=key)
                offline_kinematics_df = (dlc.OfflineKinematics()).get_data(
                    columns=["heading_dir", "head_angle"], key=key
                )
                df = pd.concat([df, offline_kinematics_df], axis=1)
                df = df[df.iti == 0.0]
                interpolated_df = interpolate_j_shaped(df, box_df=box_df)
                interpolated_df = interpolated_df.drop(
                    columns=["time", "dataset", "trial_step"]
                )
                interpolated_df["x_flipped"] = df["x"] * df["flip_one_side"]
                self.insert1(
                    {**key, **interpolated_df.to_dict()}, allow_direct_insert=True
                )

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class MeanXYTrajectory(dj.Computed):
    definition = """
    -> InterpolatedTrials
    ---
    aperture: <blob>          # occlusion aperture size for each trial progression point
    trial_left_choice: <blob> # left or right choice for each trial
    trial_length: <blob>      # the trial progression points
    x: <blob>                 # mean x-coordinate of each trial progression point
    y: <blob>                 # mean y-coordinate of each trial progression point
    sem_x: <blob>             # standard error of the mean x-coordinate of each trial progression point
    sem_y: <blob>             # standard error of the mean y-coordinate of each trial progression point
    std_x: <blob>             # standard deviation of the x-coordinate of each trial progression point
    std_y: <blob>             # standard deviation of the y-coordinate of each trial progression point
    """

    def make(self, key):
        """Compute mean trajectory across trials for each aperture."""
        from vr4mice.analysis.analysis import mean_xy_trajectory

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame(
                    (InterpolatedTrials() & key).fetch(
                        "dataset",
                        "aperture",
                        "trial",
                        "trial_left_choice",
                        "trial_length",
                        "x",
                        "y",
                        as_dict=True,
                    )[0]
                )

                mean_df = mean_xy_trajectory(
                    df,
                    index_columns=[
                        "dataset",
                        "aperture",
                        "trial_left_choice",
                        "trial_length",
                    ],
                )
                mean_df = (mean_df.drop(columns=["dataset"])).to_dict()
                self.insert1({**key, **mean_df})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class YBinnedXYTrajectory(dj.Computed):
    definition = """
    -> InterpolatedTrials
    ---
    aperture: <blob> # occlusion aperture size 
    x_flipped: <blob> # x-coordinate for each y bin center
    bin_centers: <blob> # y bin centers
    y: <blob> # y
    """

    def make(self, key):
        """Compute y-binned mean trajectories for each aperture."""
        from vr4mice.analysis.analysis import mean_xy_trajectory
        from vr4mice.analysis.utils import create_bins

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame(
                    (InterpolatedTrials() & key).fetch(
                        "aperture",
                        "trial",
                        "trial_length",
                        "x",
                        "flip_one_side",
                        "y",
                        as_dict=True,
                    )[0]
                )
                df["x_flipped"] = df.x * df.flip_one_side
                mean_df = mean_xy_trajectory(
                    df,
                    index_columns=["aperture", "trial_length"],
                    values=["x_flipped", "y"],
                )
                binned_df = create_bins(mean_df)
                binned_df = binned_df[["aperture", "bin_centers", "x_flipped", "y"]]
                binned_df = (
                    binned_df.groupby(["aperture", "bin_centers"], as_index=False).mean(
                        numeric_only=True
                    )
                ).to_dict()
                self.insert1({**key, **binned_df})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)


@schema
class MeanVelocities(dj.Computed):
    definition = """
    -> InterpolatedTrials
    ---
    aperture: <blob> # occlusion aperture size 
    trial_length: <blob> # trial length
    velocity: <blob> # mean velocity of each trial progression point
    velocity_x: <blob> # mean x-velocity of each trial progression point
    velocity_y: <blob> # mean y-velocity of each trial progression point
    velocity_x_fliped: <blob> # mean x-velocity of each trial progression point flipped
    """

    def make(self, key):
        """Compute mean velocities across trials for each aperture."""
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            if len(InterpolatedTrials & key) > 0:
                df = pd.DataFrame(
                    (InterpolatedTrials() & key).fetch(
                        "aperture",
                        "trial_length",
                        "velocity",
                        "velocity_x",
                        "velocity_y",
                        "velocity_x_fliped",
                        as_dict=True,
                    )[0]
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
