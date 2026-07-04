import os
import argparse
import sys

from base_actions.connect import connect
from vr4mice.utils.bootstrap import configure_runtime
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


"""
    Pool of commands

    Modes:
    "connect": connect to the database
    "populate": populate the raw data from files
    "fetch": create .npy file for dropdown menu
    "analysis": perform data analysis: populate base_analysis
    "summary": generate summary plots: populate summary plots
    "dlc": process DeepLabCut data: populate dlc tables
    "update": sync missing data in existing tables
    "sync_days": synchronize days in the dataset (process raw .npy files)
    "interp": interpolate trajectories and compute kinematics
    "latency": compute latencies based on photodiode signals
    "inputs_videos": process input videos and extract frames
    "decision": analyze decision-making metrics
"""


def create_folder_if_not_exist(folder_path):
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            logger.info(f"Folder '{folder_path}' created successfully.")
        except OSError as e:
            logger.warning(f"Error: {e}")
            exit(1)
    else:
        logger.info(f"Folder '{folder_path}' already exists.")


def check_folder_existence(folder_path):
    if not os.path.exists(folder_path):
        logger.warning(f"Folder '{folder_path}' does not exist. Exiting.")
        sys.exit(1)
    else:
        logger.info(f"Folder '{folder_path}' exists.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level).",
    )

    parser.add_argument(
        "mode",
        choices=[
            "connect",
            "populate",
            "analysis",
            "summary",
            "fetch",
            "dlc",
            "interp",
            "ar_paper",
            "latency",
            "sync_days",
            "inputs_videos",
            "decision",
        ],
        help="Mode to execute: 'connect', 'populate', 'summary', 'dlc', 'fetch', 'sync_days', 'analysis', 'inputs_videos', 'decision'",
    )

    args = parser.parse_args()

    logger = configure_runtime(verbose=args.verbose, debug=args.verbose)
    connect(tag="")

    if args.mode == "connect":
        from vr4mice.schema import vr4mice, base_analysis, dlc, base

        pass

    elif args.mode == "populate":
        from vr4mice.actions.populate_rig import populate_rig
        from vr4mice.schema import vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        if args.aws:
            path = "/data/processed"
            move = False
        else:
            path = "/data/data"
            move = True

        check_folder_existence(path)
        # Intentionally not calling sync_days here: day synchronization should be
        # run explicitly via the "sync_days" mode when needed, rather than on every
        # populate run.
        populate_rig(path=path, move=move)
        populate_pending(vr4mice.Collab, vr4mice.Dataset, logger=logger)

    elif args.mode == "analysis":
        from vr4mice.schema import base_analysis, vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        # NOTE: populate has to be run before

        create_folder_if_not_exist("/data/summary_plots")
        populate_pending(base_analysis.DataFrame, vr4mice.Dataset, logger=logger)
        populate_pending(
            base_analysis.BoxDataFrame, base_analysis.DataFrame, logger=logger
        )
        populate_pending(base_analysis.GitCommit, base_analysis.DataFrame, logger=logger)

    elif args.mode == "summary":
        from vr4mice.schema import base_analysis, vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        populate_pending(base_analysis.SummaryPlots, vr4mice.Dataset, logger=logger)

    elif args.mode == "dlc":
        # NOTE: populate and analysis have to be run before
        from vr4mice.schema import dlc, vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        create_folder_if_not_exist("/data/summary_plots")
        populate_pending(dlc.DLCProcessor, vr4mice.DLC, logger=logger)
        populate_pending(dlc.DLCKptsDf, vr4mice.DLC, logger=logger)
        populate_pending(dlc.SyncDLCKptsDf, dlc.DLCKptsDf, logger=logger)
        populate_pending(dlc.OfflineKinematics, dlc.SyncDLCKptsDf, logger=logger)

    elif args.mode == "interp":

        from vr4mice.schema import (
            base_analysis,
            interpolated_trajectories,
            session_metrics,
            vr4mice,
        )
        from vr4mice.utils.populate_helpers import populate_pending

        populate_pending(session_metrics.SessionMetrics, vr4mice.Dataset, logger=logger)
        populate_pending(
            session_metrics.TrialMetrics, base_analysis.DataFrame, logger=logger
        )

        populate_pending(
            interpolated_trajectories.InterpolatedTrials,
            base_analysis.DataFrame,
            logger=logger,
        )
        populate_pending(
            interpolated_trajectories.MeanXYTrajectory,
            interpolated_trajectories.InterpolatedTrials,
            logger=logger,
        )
        populate_pending(
            interpolated_trajectories.YBinnedXYTrajectory,
            interpolated_trajectories.InterpolatedTrials,
            logger=logger,
        )
        populate_pending(
            interpolated_trajectories.MeanVelocities,
            interpolated_trajectories.InterpolatedTrials,
            logger=logger,
        )

    elif args.mode == "ar_paper":

        from vr4mice.schema import interpolated_trajectories, session_metrics, vr4mice

        keys = (
            vr4mice.Dataset() * vr4mice.Groups() * vr4mice.Labels() & "label='ar_paper'"
        ).fetch("dataset", as_dict=True)

        session_metrics.SessionMetrics().populate(keys)
        session_metrics.TrialMetrics().populate(keys)

        interpolated_trajectories.InterpolatedTrials().populate(keys)

        interpolated_trajectories.MeanXYTrajectory().populate()
        interpolated_trajectories.YBinnedXYTrajectory().populate()
        interpolated_trajectories.MeanVelocities().populate()

    elif args.mode == "latency":

        from vr4mice.schema import latency_tests, vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        populate_pending(vr4mice.SignalsPhotodiode, vr4mice.Dataset, logger=logger)
        populate_pending(
            latency_tests.SignalsPhotodiodeAligned,
            vr4mice.SignalsPhotodiode,
            logger=logger,
        )
        populate_pending(
            latency_tests.AllLatencies,
            latency_tests.SignalsPhotodiodeAligned,
            logger=logger,
        )

    elif args.mode == "inputs_videos":
        from vr4mice.schema import inputs_videos, vr4mice
        from vr4mice.utils.populate_helpers import populate_pending

        populate_pending(inputs_videos.RawVideo, vr4mice.Dataset, logger=logger)
        populate_pending(inputs_videos.ProcessedVideo, inputs_videos.RawVideo, logger=logger)
        populate_pending(
            inputs_videos.VideoSyncSignal, inputs_videos.ProcessedVideo, logger=logger
        )
        populate_pending(
            inputs_videos.AlignedVideoFrame,
            inputs_videos.VideoSyncSignal,
            logger=logger,
        )

    elif args.mode == "decision":
        from vr4mice.schema import decision

        decision.sync_lookup_contents()
        decision.ExperimentMember().populate()
        decision.InclusionStatus().populate()
        decision.LabelSet().fill()
        decision.PredictionModel().populate()
        decision.DecisionPoints().populate()
        decision.PredictionModel10Windows().populate()
        decision.DecisionPoints10Windows().populate()

    elif args.mode == "fetch":
        from vr4mice.actions.fetch_data import fetch_data

        path = "/shared"
        check_folder_existence(path)

        fetch_data(dst="/shared/gui_menu.npy")

    elif args.mode == "sync_days":
        from vr4mice.actions.sync_days import sync_days

        sync_days(path="/data/data")
