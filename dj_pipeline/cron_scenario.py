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

    def run_step(name, func):
        logger.info(f"[cron] start {name}")
        try:
            func()
            logger.info(f"[cron] done {name}")
        except Exception:
            logger.exception(f"[cron] failed {name}")

    if args.aws:
        path = "/data/processed"
        move = False
    else:
        path = "/data/data"
        move = True

    run_step(
        "populate_rig",
        lambda: (
            check_folder_existence(path),
            populate_rig(path=path, gui=os.environ["GUI"], move=move),
        ),
    )

    from vr4mice.schema import (
        base_analysis,
        dlc,
        vr4mice,
        interpolated_trajectories,
        session_metrics,
        latency_tests,
        inputs_videos,
        decision,
    )

    run_step(
        "create_summary_plots_dir",
        lambda: create_folder_if_not_exist("/data/summary_plots"),
    )

    run_step("vr4mice.Collab.populate", lambda: vr4mice.Collab().populate())
    run_step("base_analysis.DataFrame.populate", base_analysis.DataFrame.populate)
    run_step("base_analysis.BoxDataFrame.populate", base_analysis.BoxDataFrame.populate)
    run_step("base_analysis.GitCommit.populate", base_analysis.GitCommit.populate)

    run_step("dlc.DLCProcessor.populate", lambda: dlc.DLCProcessor().populate())
    run_step("dlc.DLCKptsDf.populate", lambda: dlc.DLCKptsDf().populate())
    run_step("dlc.SyncDLCKptsDf.populate", lambda: dlc.SyncDLCKptsDf().populate())
    run_step(
        "dlc.OfflineKinematics.populate", lambda: dlc.OfflineKinematics().populate()
    )

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

    run_step(
        "base_analysis.SummaryPlots.populate",
        lambda: base_analysis.SummaryPlots().populate(),
    )
    run_step(
        "base_analysis.TrackingSummaryPlots.populate",
        lambda: base_analysis.TrackingSummaryPlots().populate(),
    )

    run_step(
        "inputs_videos.RawVideo.populate", lambda: inputs_videos.RawVideo().populate()
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

    run_step(
        "decision.ExperimentMember.populate",
        lambda: decision.ExperimentMember().populate(),
    )
    run_step(
        "decision.InclusionStatus.populate",
        lambda: decision.InclusionStatus().populate(),
    )
    run_step("decision.LabelSet.fill", lambda: decision.LabelSet.fill())
    run_step(
        "decision.PredictionModel.populate",
        lambda: decision.PredictionModel().populate(),
    )
    run_step(
        "decision.DecisionPoints.populate", lambda: decision.DecisionPoints().populate()
    )

    run_step(
        "fetch_data",
        lambda: (
            check_folder_existence("/shared"),
            fetch_data(dst="/shared/gui_menu.npy"),
        ),
    )


if __name__ == "__main__":
    main()
