import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional

import datajoint as dj
import pandas as pd
from base_actions.send_email import email

from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "base_analysis"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class DataFrame(dj.Computed):
    """Host main dataframe for analysis."""

    # TODO: This used to point to vr4mice.VR4Mice
    #       will probably point this to the next version when it's available

    # TODO: Alert!
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
        from vr4mice.analysis.analysis import create_data_frame

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            data, unity_to_physical_arena_size = create_data_frame(key)
            data = data.to_dict(orient="list")
            data = {**key, **data, **{"interpolation": unity_to_physical_arena_size}}

            # TODO: add test that data keys are the same with columns names
            # if not in... alert

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

    def get_data(
        self, key: dict, columns: Optional[List[str]] = None
    ) -> Optional[pd.DataFrame]:
        try:
            if self & key:
                if columns:
                    data = (self & key).proj(*columns).to_dicts()[0]
                else:
                    data = (self & key).to_dicts()[0]
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

    def get_all_data(self, columns=None):
        """
        columns: list containing the names of required columns
        return pd.Dataframe
        """

        try:
            dfs = []
            keys = self.fetch("dataset")
            for key in keys:
                key = f"dataset='{key}'"
                data = self.get_data(key, columns)
                dfs.append(data)

            df = pd.concat(dfs).reset_index(drop=True)
            return df

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}: {err}")
            return None

    def get_rewarded(self, key):
        from vr4mice.analysis.analysis import get_rewarded

        # values needed for get_rewarded function
        df = self.get_data(key, ["dataset", "trial", "reward", "aperture"])
        if df is not False and df is not None:
            df["trial_rewarded"] = get_rewarded(df)
            return df["trial_rewarded"]
        return False

    def get_all_rewarded(self):
        from vr4mice.analysis.analysis import get_rewarded

        df = self.get_all_data(["dataset", "trial", "reward", "aperture"])
        if df is not False and df is not None:
            df["trial_rewarded"] = get_rewarded(df)
            return df["trial_rewarded"]
        return False

    def get_choices(self, key):  # TODO: implement

        pass  # TODO: implement as rewarded

        from vr4mice.analysis.analysis import get_choices

        df = self.get_data(key)
        if df is not False:
            return get_choices(df)
        return df


@schema
class BoxDataFrame(dj.Computed):
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
        from vr4mice.analysis.analysis import get_box_df

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
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
                    data = (self & key).proj(*columns).to_dicts()
                else:
                    data = (self & key).to_dicts()
                df = pd.DataFrame(data)
                return df
            return False

        except Exception as err:
            logger.warning(
                f"Can't fetch {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_all_data(self, columns):
        try:

            dfs = []
            keys = self.fetch("dataset")
            for key in keys:
                key = f"dataset='{key}'"
                data = self.get_data(key, columns)
                dfs.append(data)

            df = pd.concat(dfs).reset_index(drop=True)
            return df

        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}: {err}")
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

        from vr4mice.analysis.summary_dj import vr4mice_summary_plots
        from vr4mice.schema import base

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if (DataFrame & key) and (BoxDataFrame & key):
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

        if send:
            data = {**key, **{"filename": full_path}}
            if base.Base() & key:
                key = (base.Base() & key).to_dicts()[0]
            else:
                key = self.parse_dataset(key["dataset"])
                insert_send_email(key, data, SummaryPlots(), full_path, send=send)

    def parse_dataset(self, dataset):
        pattern = r"(\d+)?_?(\d{4}-\d{2}-\d{2})_?(\d+)?(?:\.pickle)?"
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

        from vr4mice.schema import base

        name = key["dataset"]
        if base.Base() & key:
            session_info = (base.Base() & key).to_dicts()[0]
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


def insert_send_email(key, tuple_, table, filename, send=False):

    from base_schemas.schemas import exp, mice

    toaddr = []
    try:
        for name in ["thomas", "mathislab", "yang"]:
            user_email = (exp.Experimenter & {"experimenter_name": name}).fetch("mail")[
                0
            ]
            if user_email:
                toaddr.append(user_email)

        if len(exp.Session() & key) > 0:
            user = (exp.Session() & key).proj("experimenter_name").to_dicts()[0]
            if len(user) > 0:
                addr = (exp.Experimenter & user).fetch("mail")[0]
                if addr and addr not in toaddr:
                    toaddr.append(addr)

    except dj.DataJointError as e:
        logger.warning(f"Error fetching experimenter email: {e}")
        addr = None

    try:
        table.insert1(tuple_, allow_direct_insert=True)
        logger.info(f"Summary plots populated successfully for {key}")
        if send:
            logger.info(f"Sending email now for {key}")
            email(key, toaddr, filename, error=False, message=None)
        else:
            logger.info(f"Send flag is false for {key}. No email.")

    except Exception as err:
        dataset = key["dataset"]
        vr4mice.FailedSession().add_entry(
            f"{dataset}", f"{self.__class__.__name__}", str(err)
        )
        err = f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
        logger.warning(err)
        if send:
            email(key, toaddr, None, error=True, message=err)


@schema
class GitCommit(dj.Computed):

    definition = """
    -> DataFrame
    ---
    commit_hash: varchar(256)
    changed_files: <blob>
    """

    def make(self, key):

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
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


def parse_git_commit_file(filename="git_commit"):  # TODO(mary): move to helpers
    commit_hash = None
    modified_files = []

    try:
        with open(filename, "r") as file:
            lines = file.readlines()

            for line in lines:
                line = line.strip()
                if line.startswith("commit "):
                    commit_hash = line.split()[1]
                elif line.startswith("M "):
                    modified_files.append(line)

        return {"commit_hash": commit_hash, "changed_files": modified_files}

    except FileNotFoundError:
        logger.warning(f"Error: File '{filename}' not found.")
        return None, []


@schema
class TrackingSummaryPlots(dj.Computed):
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

        from vr4mice.analysis.tracking_summary_dj import plot_keypoints_summary
        from vr4mice.schema import base, dlc

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if dlc.DLCKptsDf & key:
            full_path = plot_keypoints_summary(key, save_path="/data/summary_plots")
        else:
            logger.warning(
                "Populate first DLC DLCKptsDf for "
                + str(key)
                + "; call DLCKptsDf.populate();"
            )
            return False

        if send:
            data = {**key, **{"filename": full_path}}
            if base.Base() & key:
                key = (base.Base() & key).to_dicts()[0]
            else:
                key = self.parse_dataset(key["dataset"])
                insert_send_email(key, data, SummaryPlots(), full_path, send=send)

    def parse_dataset(self, dataset):
        pattern = r"(\d+)?_?(\d{4}-\d{2}-\d{2})_?(\d+)?(?:\.pickle)?"
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
