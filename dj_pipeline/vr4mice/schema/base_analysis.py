from pathlib import Path
from typing import List
import subprocess

import datajoint as dj
import pandas as pd
from vr4mice.schema import vr4mice
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "base_analysis"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class DataFrame(dj.Computed):
    """
    Host main dataframe for analysis.
    """

    # TODO: This used to point to vr4mice.VR4Mice
    #       will probably point this to the next version when it's available

    # TODO: Alert!
    # "step", "reward", "step_time", "mouse_can_report", "head_dir" has to be deprecated: can be always fetched from Raw

    definition = """
    -> vr4mice.Dataset
    ---
    step: longblob                      # TO DEPRECATE
    step_time: longblob                 # TO DEPRECATE 
    trial: longblob 
    reward: longblob                    # TO DEPRECATE
   
    x: longblob
    y: longblob

    bins_y=NULL: longblob               # NEW, do we need to 'store' too?
    norm_y=NULL: longblob               # NEW, do we need to store 'trial' too?

    mouse_can_report=NULL: longblob     # TO DEPRECATE
    iti: longblob
    iti_duration=NULL: longblob
    mouse_correct: longblob             # TO DEPRECATE
    object_on_left: longblob
    mouse_in_left: longblob
    mouse_in_right: longblob
    
    velocity: longblob
    velocity_x=NULL: longblob           # NEW --> to think about separate table
    velocity_y=NULL: longblob           # NEW

    acceleration_x=NULL: longblob      # NEW
    acceleration_y=NULL: longblob      # NEW

    head_dir=NULL: longblob             # TO DEPRECATE

    trial_duration=NULL: longblob          # NEW
    distance=NULL: longblob                # NEW
    trial_traj_path_length=NULL: longblob  # NEW

    trial_init_x=NULL: longblob             # NEW --> to method maybe
    trial_init_y=NULL: longblob             # NEW
    trial_end_x=NULL: longblob              # NEW
    trial_end_y=NULL: longblob              # NEW

    trial_direct_path=NULL: longblob        # NEW
    trial_tortuosity=NULL: longblob         # NEW
    trial_step: longblob

    trial_step_time=NULL: longblob          # OLD TO DEPRECATE? (same as time?)
    trial_step_fraction=NULL: longblob
    
    choice=NULL: longblob                   # NEW --> to method?
    flip_one_side=NULL: longblob            # NEW
    
    trial_right_choice: longblob
    trial_left_choice: longblob

    trial_step_fraction=NULL: longblob      # OLD: TO DEPRECATE (same as trial_step?)
   
    aperture=NULL: longblob                 # NEW
    time=NULL: longblob                     # NEW
    time_elapsed=NULL: longblob             # NEW

    interpolation: longblob
    """

    def make(self, key):
        from vr4mice.analysis.analysis import create_data_frame

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        try:
            data, interp = create_data_frame(key)
            data = data.to_dict(orient="list")
            data = {**key, **data, **{"interpolation": interp}}

            # TODO: add test that data keys are the same with columns names
            # if not in... alert

            self.insert1(data, allow_direct_insert=True)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_data(self, key, columns=None):
        try:
            if self & key:
                if columns:
                    data = (self & key).fetch(*columns, as_dict=True)[0]
                else:
                    data = (self & key).fetch(as_dict=True)[0]
                    # interp = data["interpolation"]
                    data.pop("interpolation")
                df = pd.DataFrame(data)
                return df  # , interp  # TODO: externalize interpolation maybe
            else:
                return False
        except Exception as err:
            logger.warning(f"Error {self.__class__.__name__}, key: {key}; {err}")
            return None

    def get_interp(self, key):
        try:
            if self & key:
                interp = (self & key).fetch("interpolation")[0]
                # df = pd.DataFrame(interp)
                return interp
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

        df = self.get_data(key, ["dataset", "trial", "reward", "aperture"])
        if df is not False and df is not None:
            df["trial_rewarded"] = get_rewarded(df)
            return df
        return False

    def get_all_rewarded(self):
        from vr4mice.analysis.analysis import get_rewarded

        df = self.get_all_data(["dataset", "trial", "reward", "aperture"])
        if df is not False and df is not None:
            df["trial_rewarded"] = get_rewarded(df)
            return df
        return False

    def get_choices(self, key):  # TODO: implement

        pass

        from vr4mice.analysis.analysis import get_choices

        df, interp = self.get_data(key)
        if df is not False:
            return get_choices(df)
        return df


@schema
class BoxDataFrame(dj.Computed):
    definition = """
    -> DataFrame
    ---
    l_box_x_min: blob
    l_box_x_max: blob
    l_box_z_min: blob
    l_box_z_max: blob
    
    r_box_x_min: blob
    r_box_x_max: blob
    r_box_z_min: blob
    r_box_z_max: blob

    tt_box_x_min: blob
    tt_box_x_max: blob
    tt_box_z_min: blob
    tt_box_z_max: blob

    tt_box_angle: blob
    
    l_reward_x=NULL: blob    # NEW  
    l_reward_z=NULL: blob    # NEW  
    r_reward_x= NULL: blob  # NEW
    r_reward_z=NULL: blob    # NEW  
    
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
                interp = DataFrame().get_interp(key)
                box_df = get_box_df(key, df, interp=interp)
                box_df = {
                    k: v[0] if isinstance(v, list) and len(v) == 1 else v
                    for k, v in box_df.to_dict(orient="list").items()
                }
                data = {**key, **box_df}  # **data}
                self.insert1(data, allow_direct_insert=True)
                logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
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

    def get_dist2reward(self, key):

        from vr4mice.analysis.analysis import get_dist2reward

        df, interp = DataFrame().get_data(key)
        df_box = self.get_data(key)

        if df is not False and df_box is not False:
            return get_dist2reward(df, box_df)

        return False


@schema
class JShaped(dj.Computed):
    definition = """
    -> DataFrame
    ---
    j_shaped=NULL: longblob     # NEW
    headers=NULL: longblob      # NEW
    """
    # TODO: store headers once, or separately, since always the same

    def make(self, key):

        from vr4mice.analysis.analysis import get_jshaped_trials

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return
        try:
            if DataFrame & key:
                df = DataFrame().get_data(key, ["trial_duration", "trial_tortuosity"])
                j = get_jshaped_trials(df)
                j_np = j.to_numpy()
                headers = j.columns.to_numpy()
                data = {"j_shaped": j_np, "headers": headers}
                data = {**data, **key}
                self.insert1(data, allow_direct_insert=True)
                logger.info(f"{self.__class__.__name__} populated for {key}.")

        except Exception as err:
            logger.warning(
                f"Can't populate {self.__class__.__name__}, key: {key}. Error: {err}."
            )
            return None

    def get_jshaped(self, key):  # TODO: fetch_all

        data = (self & key).fetch1()
        headers = data["headers"]
        j = pd.DataFrame(data["j_shaped"], columns=headers)
        return j

    def get_jshaped_all(self):
        data = self.fetch()
        datasets = data["dataset"]
        headers = data["headers"]
        j_shaped = data["j_shaped"]
        dfs = []

        for header, j, dataset in zip(headers, j_shaped, datasets):
            df = pd.DataFrame(j, columns=header)
            df["dataset"] = dataset
            dfs.append(df)

        final_df = pd.concat(dfs, ignore_index=True)
        return final_df


@schema
class OutputPlots(dj.Computed):
    definition = """
    -> vr4mice.Dataset
    ---
    filename:  varchar(255)
    """

    def make(self, key):
        """
        key: Dataset
        """
        # generate

        from vr4mice.analysis.analysis import vr4mice_summary_plots

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if (DataFrame & key) and (BoxDataFrame & key):
            full_path = vr4mice_summary_plots(
                key, save_path="/data/summary_plots", database=True
            )
        else:
            logger.warning(
                "Populate first DataFrame and BoxDataFrame for "
                + str(key)
                + "; call DataFrame.populate(); BoxDataFrame.populate(); (...) or data_fetch(key, database=True)"
            )
            return False

        data = {**key, **{"filename": full_path}}
        self.insert1(data, allow_direct_insert=True)

        logger.info(f"{self.__class__.__name__} populated for {key}.")

        # todo: send mail (needs base_schemas), have a config file

    def get_path(self, key, base, ext=".png"):
        """
        key: Dataset
        Note: not used now, needs base_schemas
        """
        # todo: check if exists, fetch from base schemas
        from vr4mice.schema import federated_db

        session_info = (federated_db.VR4Mice() & key).fetch(as_dict=True)

        if session_info:
            name = (
                session_info["mouse_name"]
                + "_day"
                + str(session_info["day"])
                + "_attempt"
                + str(session_info["attempt"])
            )
        else:
            name = key["dataset"]

        name = str(name) + "_summary_plot" + ext
        return Path(base).joinpath(name)

    def get_subtitle(self, key, task_name="AR Task"):

        from vr4mice.schema import federated_db

        session_info = (federated_db.VR4Mice() & key).fetch(as_dict=True)

        if session_info:
            info = (
                session_info["mouse_name"]
                + ", day "
                + str(session_info["day"])
                + ", attempt "
                + str(session_info["attempt"])
            )  # todo add other info if needed
        else:
            info = "dataset: " + key["dataset"]

        subtitle = task_name + ": " + info
        return subtitle


# todo: add to base_actions
def insert_send_mail(key, tuple_, table, filename, send=False):

    user = (exp.Session() & key).fetch1("experimenter_name")
    try:
        email = (exp.Experimenter & {"experimenter_name": user}).fetch1("mail")

    except dj.DataJointError as e:
        logger.warning(f"Error fetching experimenter email: {e}")
        email = None

    try:
        table.insert1(tuple_)
        logger.info(
            "Behavior populated successfully. Sending email now!"
            "mouse = %s // day = %d // attempt = %d"
            % (key["mouse_name"], key["day"], key["attempt"])
        )
        if send:
            send_email.email(email, filename, error=False, message=None)

    except Exception as err:
        err = f"Error while populating the Summary table: key {key}\n{err}"
        logger.warning(err)
        if send:
            send_email.email(email, None, error=True, message=err)


@schema
class GitCommit(dj.Computed):

    definition = """
    -> DataFrame
    ---
    commit_hash: varchar(256)
    changed_files: blob
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
            err = f"Error while populating the GitCommit table: key {key}\n{err}"
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

    def make(self, key, send=False):
        """
        key: Dataset
        """
        # generate

        from vr4mice.analysis.tracking_summary_dj import plot_keypoints_summary
        from vr4mice.schema import base
        from vr4mice.schema import dlc

        if self & key:
            logger.info(
                f"{self.__class__.__name__}: to ignore duplicate entries in insert, set skip_duplicates=True; key: {key}"
            )
            return

        if (DataFrame & key) and (BoxDataFrame & key):
            full_path = plot_keypoints_summary(
                key, save_path="/data/summary_plots"
            )
        else:
            logger.warning(
                "Populate first DLC DLCKptsDf for "
                + str(key)
                + "; call DLCKptsDf.populate(); (...) or data_fetch(key, database=True)"
            )
            return False

        data = {**key, **{"filename": full_path}}
        key = (base.Base() & key).fetch(as_dict=True)[0]
        insert_send_email(key, data, TrackingSummaryPlots(), full_path, send=send)


def insert_send_email(key, tuple_, table, filename, send=False):
    from base_schemas.schemas import exp, mice
    
    try:
        user = (exp.Session() & key).fetch("experimenter_name", as_dict=True)[0]
        if len(user) > 0:
            addr = (exp.Experimenter & user).fetch("mail")[0]
            if len(addr) == 0:
                addr == "default"
        else:
            addr = "default"

    except dj.DataJointError as e:
        logger.warning(f"Error fetching experimenter email: {e}")
        addr = None

    try:
        table.insert1(tuple_, allow_direct_insert=True)
        logger.info(f"Summary plots populated successfully for {key}")
        if send:
            logger.info(f"Sending email now for {key}")
            email(key, addr, filename, error=False, message=None)
        else:
            logger.info(f"Send flag is false for {key}. No email.")

    except Exception as err:
        err = f"Error while populating the Summary table: key {key}: err: {err}"
        logger.warning(err)
        if send:
            email(key, addr, None, error=True, message=err)
