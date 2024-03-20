from typing import List

import datajoint as dj
from pathlib import Path
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

from vr4mice.schema import vr4mice
import pandas as pd

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
    definition = """
    -> vr4mice.Dataset
    ---
    step: longblob
    step_time: longblob
    trial: longblob
    reward: longblob
   
    x: longblob
    y: longblob
    
    mouse_can_report: longblob
    iti: longblob
    mouse_correct: longblob
    object_on_left: longblob
    mouse_in_left: longblob
    mouse_in_right: longblob
    
    velocity: longblob
    head_dir: longblob

    trial_rewarded: longblob
    trial_step: longblob
    trial_step_time: longblob
    trial_step_fraction: longblob
    
    trial_right_choice: longblob
    trial_left_choice: longblob
    trial_step_fraction: longblob
    
    interpolation: longblob
    """
    # box_df: blob

    def make(self, key):
        from vr4mice.analysis.analysis import create_data_frame

        data, interp = create_data_frame(key)
        # data["interpolation"] = interp
        # logger.info("Details: " + str(data))
        data = data.to_dict(orient="list")
        data = {**key, **data, **{"interpolation": interp}}
        self.insert1(data)
        logger.info(f"{self.__class__.__name__} populated for {key}.")

    def get_data(self, key):
        if self & key:
            data = (self & key).fetch1()
            interp = data["interpolation"]
            data.pop("interpolation")
            data = pd.DataFrame(data)
            return data, interp
        else:
            return False, None

    def get_rewarded(self, key):
        from vr4mice.analysis.analysis import get_rewarded

        df, interp = self.get_data(key)
        if df is not False:
            return get_rewarded(df)
        return df

    def get_choices(self, key):
        from vr4mice.analysis.analysis import get_choices

        df, interp = self.get_data(key)
        if df is not False:
            return get_choices(df)
        return df


@schema
class BoxDataFrame(dj.Computed):
    # TODO: This used to point to vr4mice.VR4Mice
    #       will probably point this to the next version when it's available
    definition = """
    -> DataFrame
    ---
    left_box_x_min: blob
    left_box_x_max: blob
    left_box_z_min: blob
    left_box_z_max: blob
    
    right_box_x_min: blob
    right_box_x_max: blob
    right_box_z_min: blob
    right_box_z_max: blob

    tt_box_x_min: blob
    tt_box_x_max: blob
    tt_box_z_min: blob
    tt_box_z_max: blob

    tt_box_angle: blob
    """

    def make(self, key):
        from vr4mice.analysis.analysis import get_box_df

        if DataFrame & key:
            interp = (DataFrame & key).fetch1("interpolation")
            box_df = get_box_df(key, interp=interp)
            # data = box_df.to_dict(orient='list')
            data = {**key, **box_df}  # **data}
            self.insert1(data)
            logger.info(f"{self.__class__.__name__} populated for {key}.")

    def get_data(self, key):
        if self & key:
            data = (self & key).fetch1()
            data = pd.Series(data)
            return data
        else:
            return False


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

        if (DataFrame & key) and (BoxDataFrame & key):
            full_path = vr4mice_summary_plots(
                key, save_path="/data/summary_plots", database=True
            )
        else:
            logger.warning(
                "Populate first DataFrame and BoxDataFrame for "
                + str(key)
                + "; call DataFrame.populate() or BoxDataFrame.populate() or data_fetch(key, database=True)"
            )
            return False

        data = {**key, **{"filename": full_path}}
        self.insert1(data)

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
        err = "Error while populating the Sumamry table\n" + str(err)
        logger.warning(err)
        if send:
            send_email.email(email, None, error=True, message=err)
