from typing import List

import datajoint as dj
from pathlib import Path
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

from base_schemas.schemas import exp
from base_schemas.schemas import mice
from vr4mice.schema import vr4mice
from vr4mice.analysis.analysis import create_data_frame

schema_name = "base_analysis"
schema = get_schema(schema_name, locals())

logger = Logger.get_logger()


@schema
class DataFrame(dj.Computed):
    """
        Host main dataframe for analysis.
    """

    definition = """
        -> vr4mice.VR4Mice
        ---
        velocity: blob
        head_dir: blob
        
        x: blob
        y: blob
        box_df: blob
        
        trial_rewarded: blob
        trial_step: blob
        trial_step_time: blob
        trial_step_fraction: blob
        trial_R_choice: blob
        trial_L_choice: blob
        trial_step_fraction: blob
        
        rewarded: blob
        choices: blob
        box_entries: blob
    """

    def make(self, key):
        # (todo: re-think, externalize fetch)
        df = create_data_frame(key)
        self.insert1(key, df)
        return df


@schema
class BoxDataFrame(dj.Computed):
    definition = """
       -> vr4mice.VR4Mice
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
       
    """


@schema
class OutputPlots(dj.Computed):
    definition = """
    -> DataFrame
    filename: varchar(255)
    ---
    """

    def make(self, key, full_path):
        """
            key: Dataset
        """
        filename = full_path  # start analysis function
        self.insert1(key, filename)
        # send mail

    def get_path(self, base, key, ext=".png"):
        """
            key: Dataset
        """
        # (todo) check if exists

        name = key["mouse_name"] + "_day" + \
               str(key["day"]) + "_attempt" + \
               str(key["attempt"]) + "_summary_plot" + \
               ext

        return Path(base).joinpath(name)
