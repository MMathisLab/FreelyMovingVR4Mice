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

schema_name = "session_metrics"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class SessionMetrics(dj.Computed):
    definition = """
    -> base_analysis.DataFrame
    ---
    session_reward:             float # proportion of rewarded trials
    session_trial_duration:     float # mean trial duration in seconds
    session_jshaped:            float # proportion of trials that are j_shaped
    session_max_trial_number:   int # max trial number
    session_duration:           float # total length of session in seconds
    session_bias:               float # proportion of trials that mouse chose the left port 
    session_tortuosity:         float # session mean tortuosity
    """

    def make(self, key):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        try:
            if len(base_analysis.DataFrame & key) > 0:
                df = (base_analysis.DataFrame()).get_data(
                    key=key,
                    columns=[
                        "dataset",
                        "step_time",
                        "trial",
                        "trial_left_choice",
                        "trial_duration",
                        "trial_tortuosity",
                    ],
                )

                df["trial_rewarded"] = (base_analysis.DataFrame()).get_rewarded(key=key)
                trial_number = df.trial.nunique()

                j_shaped = get_jshaped_trials(df)
                n_j_shaped = j_shaped.trial.nunique() / trial_number
                mean_df = df.groupby(["dataset", "trial"], as_index=False).mean(
                    numeric_only=True
                )
                mean_df = df.groupby(["dataset"], as_index=False).mean(
                    numeric_only=True
                )
                mean_df["max_trial_number"] = trial_number
                mean_df["session_duration"] = df.groupby(["dataset"], as_index=False)[
                    "step_time"
                ].max(numeric_only=True)["step_time"]
                mean_df["session_jshaped"] = n_j_shaped

                insert_dict = {
                    "session_reward": mean_df.trial_rewarded.values[0],
                    "session_trial_duration": mean_df.trial_duration.values[0],
                    "session_jshaped": mean_df.session_jshaped.values[0],
                    "session_max_trial_number": mean_df.max_trial_number.values[0],
                    "session_duration": mean_df.session_duration.values[0],
                    "session_bias": mean_df.trial_left_choice.values[0],
                    "session_tortuosity": mean_df.trial_tortuosity.values[0],
                }

                self.insert1({**key, **insert_dict})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None


@schema
class TrialMetrics(dj.Computed):
    definition = """
    -> base_analysis.DataFrame
    ---
    trial_rewarded: float # proportion of rewarded trials
    """
    definition = """
    -> base_analysis.DataFrame
    ---
    aperture:             longblob # occlusion slit aperture in game units
    trial:                longblob # trial number
    trial_left_choice:    longblob # mouse chose left port 0.0 or 1
    trial_rewarded:       longblob # trial duration in seconds
    trial_tortuosity:     longblob # trial tortuosity
    trial_duration:       longblob # trial duration in seconds
    trial_jshaped:        longblob # trial jshaped
    """

    def make(self, key):
        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            if len(base_analysis.DataFrame & key) > 0:
                df = (base_analysis.DataFrame()).get_data(key=key)
                df["trial_rewarded"] = (base_analysis.DataFrame()).get_rewarded(key=key)
                df["trial_jshaped"] = get_jshaped_trials(df)
                df.loc[:, "trial_jshaped"] = np.where(
                    (df.trial_duration <= 5) & (df.trial_tortuosity <= 5), 1, 0
                )

                mean_df = df.groupby(["dataset", "trial"], as_index=False).mean(
                    numeric_only=True
                )
                insert_dict = {
                    "aperture": mean_df.aperture.values,
                    "trial": mean_df.trial.values,
                    "trial_left_choice": mean_df.trial_left_choice.values,
                    "trial_rewarded": mean_df.trial_rewarded.values,
                    "trial_tortuosity": mean_df.trial_tortuosity.values,
                    "trial_duration": mean_df.trial_duration.values,
                    "trial_jshaped": mean_df.trial_jshaped.values,
                }
                self.insert1({**key, **insert_dict})

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None
