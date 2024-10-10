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

    if mode == "an_test":
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

    if mode == "an_drop":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            {"dataset": "Oribi_2024-08-16_1"},
            {"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            (base_analysis.DataFrame() & t).delete()
            (base_analysis.BoxDataFrame() & t).delete()
            (base_analysis.JShaped() & t).delete()
            (base_analysis.GitCommit() & t).delete()

    elif mode == "dlc_test":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            {"dataset": "Oribi_2024-08-16_1"},
            {"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            dlc.DLCProcessor().make(key=t)
            dlc.DLCKptsDf().make(key=t)
            dlc.SyncDLCKptsDf().make(key=t)
            dlc.OfflineKinematics().make(key=t)

    elif mode == "dlc_drop":
        from vr4mice.schema import vr4mice, base_analysis, dlc

        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            {"dataset": "Oribi_2024-08-16_1"},
            {"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            (dlc.DLCProcessor() & t).delete()
            (dlc.DLCKptsDf() & t).delete()
            (dlc.SyncDLCKptsDf() & t).delete()
            (dlc.OfflineKinematics() & t).delete()

    elif mode == "summary_test":
        from vr4mice.schema import vr4mice, base_analysis, dlc
        from vr4mice.analysis.summary_dj import fetch_data
        
        test_datasets = [
            {"dataset": "Jacana_2024-08-21_1"},
            #{"dataset": "Oribi_2024-08-16_1"},
            #{"dataset": "Pheasant_2024-08-28_1"},
        ]
        for t in test_datasets:
            data_db = fetch_data(t, database=True)
            print(data_db)
            data_compute = fetch_data(t, database=False)
            print(data_compute)
