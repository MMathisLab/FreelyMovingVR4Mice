import logging
import os
import argparse

import sys
import warnings

from base_actions.connect import connect
from vr4mice.utils.logger import Logger, config_logger

logger = Logger.get_logger()


logging.getLogger("settings").setLevel(logging.ERROR)

warnings.simplefilter(action="ignore", category=FutureWarning)


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


def run_step(name, func):
    logger.info(f"[run] start {name}")
    try:
        func()
        logger.info(f"[run] done {name}")
    except Exception:
        logger.exception(f"[run] failed {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
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

    config_logger(level="INFO", debug=False)
    connect(tag="")

    if args.mode == "connect":
        from vr4mice.schema import vr4mice, base_analysis, dlc, base

        pass

    elif args.mode == "populate":
        from vr4mice.actions.populate_rig import populate_rig
        from vr4mice.schema import vr4mice

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
        run_step(
            "populate_rig",
            lambda: populate_rig(path=path, move=move),
        )
        run_step("vr4mice.Collab.populate", lambda: vr4mice.Collab().populate())

    elif args.mode == "analysis":
        from vr4mice.schema import base_analysis, base

        # NOTE: populate has to be run before

        create_folder_if_not_exist("/data/summary_plots")
        run_step("base_analysis.DataFrame.populate", base_analysis.DataFrame.populate)
        run_step(
            "base_analysis.BoxDataFrame.populate",
            lambda: base_analysis.BoxDataFrame().populate(),
        )
        run_step(
            "base_analysis.GitCommit.populate",
            lambda: base_analysis.GitCommit().populate(),
        )

    elif args.mode == "summary":
        from vr4mice.schema import base_analysis

        run_step(
            "base_analysis.SummaryPlots.populate",
            lambda: base_analysis.SummaryPlots().populate(),
        )
        run_step(
            "base_analysis.TrackingSummaryPlots.populate",
            lambda: base_analysis.TrackingSummaryPlots().populate(),
        )

    elif args.mode == "dlc":
        # NOTE: populate and analysis have to be run before
        from vr4mice.schema import dlc

        create_folder_if_not_exist("/data/summary_plots")
        run_step("dlc.DLCProcessor.populate", lambda: dlc.DLCProcessor().populate())
        run_step("dlc.DLCKptsDf.populate", lambda: dlc.DLCKptsDf().populate())
        run_step(
            "dlc.SyncDLCKptsDf.populate",
            lambda: dlc.SyncDLCKptsDf().populate(),
        )
        run_step(
            "dlc.OfflineKinematics.populate",
            lambda: dlc.OfflineKinematics().populate(),
        )

    elif args.mode == "interp":

        from vr4mice.schema import interpolated_trajectories, session_metrics

        run_step(
            "session_metrics.SessionMetrics.populate",
            lambda: session_metrics.SessionMetrics().populate(),
        )
        run_step(
            "session_metrics.TrialMetrics.populate",
            lambda: session_metrics.TrialMetrics().populate(),
        )

        run_step(
            "interpolated_trajectories.InterpolatedTrials.populate",
            lambda: interpolated_trajectories.InterpolatedTrials().populate(),
        )
        run_step(
            "interpolated_trajectories.MeanXYTrajectory.populate",
            lambda: interpolated_trajectories.MeanXYTrajectory().populate(),
        )
        run_step(
            "interpolated_trajectories.YBinnedXYTrajectory.populate",
            lambda: interpolated_trajectories.YBinnedXYTrajectory().populate(),
        )
        run_step(
            "interpolated_trajectories.MeanVelocities.populate",
            lambda: interpolated_trajectories.MeanVelocities().populate(),
        )

    elif args.mode == "ar_paper":

        from vr4mice.schema import interpolated_trajectories, session_metrics, vr4mice

        keys = (
            vr4mice.Dataset() * vr4mice.Groups() * vr4mice.Labels() & "label='ar_paper'"
        ).fetch("dataset", as_dict=True)

        run_step(
            "session_metrics.SessionMetrics.populate(ar_paper)",
            lambda: session_metrics.SessionMetrics().populate(keys),
        )
        run_step(
            "session_metrics.TrialMetrics.populate(ar_paper)",
            lambda: session_metrics.TrialMetrics().populate(keys),
        )

        run_step(
            "interpolated_trajectories.InterpolatedTrials.populate(ar_paper)",
            lambda: interpolated_trajectories.InterpolatedTrials().populate(keys),
        )

        run_step(
            "interpolated_trajectories.MeanXYTrajectory.populate",
            lambda: interpolated_trajectories.MeanXYTrajectory().populate(),
        )
        run_step(
            "interpolated_trajectories.YBinnedXYTrajectory.populate",
            lambda: interpolated_trajectories.YBinnedXYTrajectory().populate(),
        )
        run_step(
            "interpolated_trajectories.MeanVelocities.populate",
            lambda: interpolated_trajectories.MeanVelocities().populate(),
        )

    elif args.mode == "latency":

        from vr4mice.schema import vr4mice, latency_tests

        run_step(
            "vr4mice.SignalsPhotodiode.populate",
            lambda: vr4mice.SignalsPhotodiode().populate(),
        )
        run_step(
            "latency_tests.SignalsPhotodiodeAligned.populate",
            lambda: latency_tests.SignalsPhotodiodeAligned().populate(),
        )
        run_step(
            "latency_tests.AllLatencies.populate",
            lambda: latency_tests.AllLatencies().populate(),
        )

    elif args.mode == "inputs_videos":
        from vr4mice.schema import inputs_videos

        run_step(
            "inputs_videos.RawVideo.populate",
            lambda: inputs_videos.RawVideo().populate(),
        )
        run_step(
            "inputs_videos.ProcessedVideo.populate",
            lambda: inputs_videos.ProcessedVideo().populate(),
        )
        run_step(
            "inputs_videos.VideoSyncSignal.populate",
            lambda: inputs_videos.VideoSyncSignal().populate(),
        )
        run_step(
            "inputs_videos.AlignedVideoFrame.populate",
            lambda: inputs_videos.AlignedVideoFrame().populate(),
        )

    elif args.mode == "decision":
        from vr4mice.schema import decision

        run_step(
            "decision.ValidGroup.populate", lambda: decision.ValidGroup().populate()
        )
        run_step(
            "decision.PredictionModel.populate",
            lambda: decision.PredictionModel().populate(),
        )
        run_step(
            "decision.DecisionPoints.populate",
            lambda: decision.DecisionPoints().populate(),
        )

    elif args.mode == "fetch":  # TODO: adjust path
        from vr4mice.actions.fetch_data import fetch_data

        path = "/shared"
        check_folder_existence(path)

        fetch_data(dst="/shared/gui_menu.npy")

    elif args.mode == "sync_days":
        from vr4mice.actions.sync_days import sync_days

        sync_days(path="/data/data")
