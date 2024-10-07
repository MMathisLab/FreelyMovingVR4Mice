import os
import sys

from base_actions.connect import connect
from vr4mice.utils.logger import Logger, config_logger

logger = Logger.get_logger()

import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)

"""
    Pool of commands

    Modes:
        "connect": connect to the database
        "populate": to populate the data from files
        "fetch": to create .npy file for dropdown menu
"""


if __name__ == "__main__":
    config_logger(level="INFO", debug=False)

    mode = sys.argv[1]  # TODO: connect arg deprecate

    connect(tag="")

    if mode == "test_an":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            {"dataset": "Oribi_2024-08-16_1"},
            {"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            base_analysis.DataFrame().make(key=t)
            base_analysis.BoxDataFrame().make(key=t)
            base_analysis.JShaped().make(key=t)
            base_analysis.GitCommit().make(key=t)

    elif mode == "test_dlc":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            {"dataset": "Oribi_2024-08-16_1"},
            {"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            dlc.DLCProcessor().make(key=t)
            dlc.DLCKptsDf().make(key=t)
