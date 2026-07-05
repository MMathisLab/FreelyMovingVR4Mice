"""Analysis schema tables built on top of core VR4Mice datasets."""

import os
import re
from pathlib import Path
from typing import List, Optional

import datajoint as dj
import numpy as np
import pandas as pd

from vr4mice.schema import base, vr4mice
from vr4mice.analysis.summary_dj import vr4mice_summary_plots
from vr4mice.utils.git_helpers import parse_git_commit_file
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "base_analysis"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


def _behavior_trials_remain(key: dict) -> bool:
    """False when only initialization trial 1 exists (excluded from DataFrame)."""
    episodes = np.unique(
        np.asarray((vr4mice.State & key).fetch("episode"), dtype=np.int32)
    )
    return bool(np.any(episodes != 1))


@schema
class DataFrame(dj.Computed):
    """
    DataFrame definition table:
    hosts the main per-step analysis dataframe for a dataset
    """

    # NOTE(mary): This used to point to vr4mice.VR4Mice
    #       will probably point this to the next version when it's available

    # TODO:
    # "step", "reward", "step_time", "mouse_can_report", "head_dir" has to be deprecated: can be always fetched from Raw

    definition = """
    -> vr4mice.Dataset
    ---
    step: <blob>                      # TO DEPRECATE
    step_time: <blob>                 # TO DEPRECATE 
    trial: <blob> 
    reward: <blob>                    # TO DEPRECATE
   
    x: <blob>
    y: <blob>

    bins_y=NULL: <blob>               # NEW, do we need to 'store' too?
    norm_y=NULL: <blob>               # NEW, do we need to store 'trial' too?

    mouse_can_report=NULL: <blob>     # TO DEPRECATE
    iti: <blob>
    iti_duration=NULL: <blob>
    mouse_correct: <blob>             # TO DEPRECATE
    object_on_left: <blob>
    mouse_in_left: <blob>
    mouse_in_right: <blob>
    
    velocity: <blob>
    velocity_x=NULL: <blob>           # NEW --> to think about separate table
    velocity_y=NULL: <blob>           # NEW

    acceleration_x=NULL: <blob>      # NEW
    acceleration_y=NULL: <blob>      # NEW

    head_dir=NULL: <blob>             # TO DEPRECATE

    trial_duration=NULL: <blob>          # NEW
    distance=NULL: <blob>                # NEW
    trial_traj_path_length=NULL: <blob>  # NEW

    trial_init_x=NULL: <blob>             # NEW --> to method maybe
    trial_init_y=NULL: <blob>             # NEW
    trial_end_x=NULL: <blob>              # NEW
    trial_end_y=NULL: <blob>              # NEW

    trial_direct_path=NULL: <blob>        # NEW
    trial_tortuosity=NULL: <blob>         # NEW
    trial_step: <blob>

    trial_step_time=NULL: <blob>          # OLD TO DEPRECATE? (same as time?)
    trial_step_fraction=NULL: <blob>
    
    choice=NULL: <blob>                   # NEW --> to method?
    flip_one_side=NULL: <blob>            # NEW
    
    trial_right_choice: <blob>
    trial_left_choice: <blob>

    trial_step_fraction=NULL: <blob>      # OLD: TO DEPRECATE (same as trial_step?)
   
    aperture=NULL: <blob>                 # NEW
    time=NULL: <blob>                     # NEW
    time_elapsed=NULL: <blob>             # NEW

    interpolation: <blob>
    """

    def make(self, key):
        """Build and insert the analysis DataFrame for a dataset."""
        from vr4mice.analysis.analysis import create_data_frame

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        dataset = key["dataset"]
        if dataset.startswith("Latencytest"):
            logger.debug("Skipping DataFrame for latency test session %s", dataset)
            return

        if not _behavior_trials_remain(key):
            vr4mice.FailedSession().add_entry(
                dataset,
                self.__class__.__name__,
                "No trials after excluding initialization trial 1",
            )
            logger.debug("Skipping DataFrame for %s: no behavior trials", dataset)
            return

        try:
            data, unity_to_physical_arena_size = create_data_frame(key)
            data = data.to_dict(orient="list")
            data = {**key, **data, **{"interpolation": unity_to_physical_arena_size}}

            self.insert1(data, allow_direct_insert=True, skip_duplicates=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            if "already exists" in str(err):
                logger.debug(
                    "%s already populated for %s",
                    self.__class__.__name__,
                    key["dataset"],
                )
                return
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch(*columns, as_dict=True)[0]
                else:
                    data = (self & key).fetch(as_dict=True)[0]
                if "interpolation" in data.keys():
                    data.pop("interpolation")
                df = pd.DataFrame(data)
                return df
            else:
                return False
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_unity_arena_size(self, key: dict) -> dict:
        try:
            if self & key:
                return (self & key).fetch("interpolation")[0]
            else:
                return False
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_rewarded(self, key):
        from vr4mice.analysis.analysis import get_rewarded

        # values needed for get_rewarded function
        df = self.get_data(key, ["dataset", "trial", "reward", "aperture"])
        if df is not False and df is not None:
            df["trial_rewarded"] = get_rewarded(df)
            return df["trial_rewarded"]
        return False


@schema
class BoxDataFrame(dj.Computed):
    """
    BoxDataFrame definition table:
    stores per-trial report and target box coordinates derived from DataFrame
    """

    definition = """
    -> DataFrame
    ---
    l_box_x_min: <blob>
    l_box_x_max: <blob>
    l_box_z_min: <blob>
    l_box_z_max: <blob>
    
    r_box_x_min: <blob>
    r_box_x_max: <blob>
    r_box_z_min: <blob>
    r_box_z_max: <blob>

    tt_box_x_min: <blob>
    tt_box_x_max: <blob>
    tt_box_z_min: <blob>
    tt_box_z_max: <blob>

    tt_box_angle: <blob>
    
    l_reward_x=NULL: <blob>    # NEW  
    l_reward_z=NULL: <blob>    # NEW  
    r_reward_x= NULL: <blob>  # NEW
    r_reward_z=NULL: <blob>    # NEW  
    
    """

    def make(self, key):
        """Compute and store per-dataset box geometry derived from trials."""
        from vr4mice.analysis.analysis import get_box_df

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            if len(DataFrame & key) > 0:
                df = DataFrame().get_data(key)
                unity_to_physical_arena_size = DataFrame().get_unity_arena_size(key)
                box_df = get_box_df(
                    key, df, unity_to_physical_arena_size=unity_to_physical_arena_size
                )
                box_df = {
                    k: v[0] if isinstance(v, list) and len(v) == 1 else v
                    for k, v in box_df.to_dict(orient="list").items()
                }
                data = {**key, **box_df}
                self.insert1(data, allow_direct_insert=True)
                logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)

            return None

    def get_data(self, key, columns=None):
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch(*columns, as_dict=True)
                else:
                    data = (self & key).fetch(as_dict=True)
                df = pd.DataFrame(data)
                return df
            return False

        except Exception as err:
            logger.warning(
                f"Can't fetch {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def calculate_distance_to_reward(self, key):

        from vr4mice.analysis.analysis import calculate_distance_to_reward

        df = DataFrame().get_data(key)
        box_df = self.get_data(key)

        if df is not False and box_df is not False:
            return calculate_distance_to_reward(df, box_df)

        return False


@schema
class SummaryPlots(dj.Computed):
    """
    SummaryPlots definition table:
    stores paths to generated per-session summary plot figures
    """

    definition = """
    -> vr4mice.Dataset
    ---
    filename:  varchar(255)
    """

    def make(self, key, send=os.environ["EMAIL"]):
        """
        key: Dataset
        """
        send = os.environ.get("EMAIL", "false").lower() in ["true", "1", "yes"]

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        if (DataFrame & key) and (BoxDataFrame & key):
            full_path = None
            try:
                full_path = vr4mice_summary_plots(
                    key, save_path="/data/summary_plots", database=True
                )
            except Exception as err:
                dataset = key["dataset"]
                vr4mice.FailedSession().add_entry(
                    f"{dataset}", f"{self.__class__.__name__}", str(err)
                )
                err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
                logger.warning(err)
                return None
        else:
            logger.warning(
                f"Populate first DataFrame and BoxDataFrame for {key}; \
                        call DataFrame.populate(); BoxDataFrame.populate(); (...) or data_fetch(key, database=True)"
            )
            return False

        data = {**key, **{"filename": full_path}}
        dataset = key["dataset"]

        err_msg = None
        try:
            self.insert1(data, allow_direct_insert=True, skip_duplicates=True)
            logger.info(f"Summary plots populated successfully for {dataset}")
        except Exception as err:
            table_name = self.__class__.__name__
            vr4mice.FailedSession().add_entry(f"{dataset}", f"{table_name}", str(err))
            err_msg = f"Can't populate {table_name}, dataset: {dataset}. Error: {err}."
            logger.warning(err_msg)

        if send:
            from vr4mice.schema import summary_emails

            email_key = summary_emails.build_summary_email_key(dataset)
            if email_key:
                summary_emails.send_and_record_summary_email(
                    dataset, email_key, str(full_path), err_msg=err_msg, logger=logger
                )
            else:
                logger.warning(
                    "Could not parse session metadata for %s; summary email skipped",
                    dataset,
                )
        else:
            logger.info(f"Send flag is false for {dataset}. No email.")

    def parse_dataset(self, dataset):
        pattern = r"(?:(?P<mouse_name>[^_]+)_)?(?P<day>\d{4}-\d{2}-\d{2})(?:_(?P<attempt>\d+))?(?:\.pickle)?$"
        match = re.match(pattern, dataset)

        if match:
            mouse_name, date, attempt = match.groups()
            return {
                "mouse_name": mouse_name if mouse_name else None,
                "day": date,
                "attempt": int(attempt) if attempt else None,
            }
        else:
            return None

    def get_name(self, key):
        name = key["dataset"]
        if base.Base() & key:
            session_info = (base.Base() & key).fetch(as_dict=True)[0]
            if len(session_info) > 0:
                name = f'{session_info["mouse_name"]}_day{session_info["day"]}_attempt{session_info["attempt"]}'

        return name

    def get_path(self, key, base="/data/summary_plots", ext=".png"):
        """
        key: Dataset
        Note: used in vr4mice_summary_plots
        """
        name = self.get_name(key)
        name = f"{name}_summary_plot{ext}"
        return Path(base).joinpath(name)

    def get_subtitle(self, key, task_name="AR Task: test plot"):
        """
        key: Dataset
        Used in vr4mice_summary_plots
        """
        name = self.get_name(key)

        subtitle = task_name + ": " + name
        return subtitle


@schema
class GitCommit(dj.Computed):
    """
    GitCommit definition table:
    stores git commit hash and changed files for analysis reproducibility
    """

    definition = """
    -> DataFrame
    ---
    commit_hash: varchar(256)
    changed_files: <blob>
    """

    def make(self, key):
        """Store git commit metadata for the current analysis run."""

        if self & key:
            logger.debug(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if vr4mice.FailedSession.should_skip(key, self.__class__.__name__, logger):
            return

        try:
            ret = parse_git_commit_file()
            data = {**key, **ret}
            self.insert1(data, allow_direct_insert=True)

        except Exception as err:
            dataset = key["dataset"]
            vr4mice.FailedSession().add_entry(
                f"{dataset}", f"{self.__class__.__name__}", str(err)
            )
            err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            logger.warning(err)
