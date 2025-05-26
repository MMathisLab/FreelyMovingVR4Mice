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
    """
    # TODO: add all columns from base_analysis.DataFrame + interpolated columns 

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
                offline_kinematics_df = (vr4mice.dlc.OfflineKinematics()).get_data(key=key)
                df = pd.concat([df, offline_kinematics_df], axis=1)
                df = df [df.iti == 0.0]
                interpolated_df = interpolate_j_shaped(df)

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
                df = (InterpolatedTrials()).get_data(key=key)
                mean_df = mean_xy_trajectory(df, index_col=["dataset", "aperture", "trial", "trial_left_choice", "trial_length"])

                self.insert1({**key, **mean_df.to_dict()})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
        
        

class MeanXYTrajectoryAperture(dj.Computed):
    definition = """
    -> InterpolatedTrials
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
                df = (InterpolatedTrials()).get_data(key=key) 
                mean_df = mean_xy_trajectory(df, index_col=["dataset", "aperture", "trial", "trial_length"])

                self.insert1({**key, **mean_df.to_dict(orient="list")})

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
    """

    def make(self, key):
        pass
