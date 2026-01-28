import os
import argparse
from base_actions.connect import connect

connect(tag="", db_host=os.environ["DJ_HOST"])


from vr4mice.actions.populate_rig import populate_rig
from vr4mice.actions.fetch_data import fetch_data
from vr4mice.utils.logger import Logger
from run import check_folder_existence, create_folder_if_not_exist


logger = Logger.get_logger()

# note: paths and args are set here to default (same as in the source file),
# here to show up the specs


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
    )
    args = parser.parse_args()

    try:
        if args.aws:
            path = "/data/processed"
            move = False
        else:
            path = "/data/data"
            move = True

        check_folder_existence(path)
        populate_rig(path=path, gui=os.environ["GUI"], move=move)
    except Exception as e:
        logger.error(
            f"An error occurred in the raw data population (populate_rig): {e}"
        )

    try:
        from vr4mice.schema import (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
            inputs_videos,
            decision
        )

        vr4mice.Collab().populate()
        create_folder_if_not_exist("/data/summary_plots")
        base_analysis.DataFrame.populate()
        base_analysis.BoxDataFrame.populate()
        base_analysis.GitCommit().populate()

        dlc.DLCProcessor().populate()
        dlc.DLCKptsDf().populate()
        dlc.SyncDLCKptsDf().populate()
        dlc.OfflineKinematics().populate()

        interpolated_trajectories.InterpolatedTrials().populate()
        interpolated_trajectories.MeanXYTrajectory().populate()
        interpolated_trajectories.YBinnedXYTrajectory().populate()
        interpolated_trajectories.MeanVelocities().populate()

        session_metrics.SessionMetrics().populate()
        session_metrics.TrialMetrics().populate()

        vr4mice.SignalsPhotodiode().populate()
        latency_tests.SignalsPhotodiodeAligned().populate()
        latency_tests.AllLatencies()

        base_analysis.SummaryPlots().populate()
        base_analysis.TrackingSummaryPlots().populate()
        
        inputs_videos.RawVideo().populate()
        inputs_videos.ProcessedVideo().populate()
        inputs_videos.VideoSyncSignal().populate()
        inputs_videos.AlignedVideoFrame().populate()
        
        decision.ValidGroup().populate()
        decision.PredictionModel().populate()
        
    except Exception as e:
        logger.error(f"An error occurred in populate_decision_making.populate: {e}")

    try:
        path = "/shared"
        check_folder_existence(path)
        fetch_data(dst="/shared/gui_menu.npy")
    except Exception as e:
        logger.error(f"An error occurred in fetch_data: {e}")


if __name__ == "__main__":
    main()
