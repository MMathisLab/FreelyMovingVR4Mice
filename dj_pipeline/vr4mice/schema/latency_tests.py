import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional

import datajoint as dj
import pandas as pd

from vr4mice.analysis.analysis import get_jshaped_trials
from vr4mice.schema import vr4mice, base_analysis
from vr4mice.utils.logger import Logger
from vr4mice.utils.schema_config import get_schema

schema_name = "latency_tests"
schema = get_schema(schema_name, locals())
logger = Logger.get_logger()


@schema
class SignalPhotodiodeAligned(dj.Computed):
    definition = """
    -> vr4mice.SignalPhotodiode
    """

    def make(self, key):
        

