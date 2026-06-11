import logging
import warnings
import argparse

logging.getLogger("settings").setLevel(logging.ERROR)
warnings.simplefilter(action="ignore", category=FutureWarning)


def main():
    parser = argparse.ArgumentParser(
        description="Script to handle AWS or local execution."
    )
    parser.add_argument(
        "--aws", action="store_true", help="Enable AWS-specific execution."
    )
    args = parser.parse_args()

    from base_actions.connect import connect
    from vr4mice.utils.logger import Logger, config_logger

    config_logger(level="INFO", debug=False)
    logger = Logger.get_logger()
    failed_steps = []

    def run_named(name, func, *, capture=False):
        logger.info("[cron] start %s", name)
        try:
            result = func()
            logger.info("[cron] done %s", name)
            return result if capture else None
        except Exception:
            logger.exception("[cron] failed %s", name)
            failed_steps.append(name)
            return None if capture else None

    def run_step(name, func):
        run_named(name, func)

    def run_import(name, import_func):
        return run_named(name, import_func, capture=True)

    run_step("connect", lambda: connect(tag=""))

    def import_run_helpers():
        from run import check_folder_existence, create_folder_if_not_exist

        return check_folder_existence, create_folder_if_not_exist

    def import_actions():
        from vr4mice.actions.populate_rig import populate_rig
        from vr4mice.actions.fetch_data import fetch_data

        return populate_rig, fetch_data

    if args.aws:
        path = "/data/processed"
        move = False
    else:
        path = "/data/data"
        move = True

    run_helpers = run_import("import run helpers", import_run_helpers)
    actions = run_import("import actions", import_actions)

    check_folder_existence = create_folder_if_not_exist = None
    populate_rig = fetch_data = None
    if run_helpers:
        check_folder_existence, create_folder_if_not_exist = run_helpers
    if actions:
        populate_rig, fetch_data = actions

    if check_folder_existence and populate_rig:
        run_step(
            "populate_rig",
            lambda: (
                check_folder_existence(path),
                populate_rig(path=path, move=move),
            ),
        )

    def import_core_schemas():
        from vr4mice.schema import (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
        )

        return (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
        )

    core_schemas = run_import("import core schemas", import_core_schemas)
    if core_schemas and create_folder_if_not_exist:
        (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
        ) = core_schemas

        run_step(
            "create_summary_plots_dir",
            lambda: create_folder_if_not_exist("/data/summary_plots"),
        )

        run_step("vr4mice.Collab.populate", lambda: vr4mice.Collab().populate())
        run_step(
            "base_analysis.DataFrame.populate", base_analysis.DataFrame.populate
        )
        run_step(
            "base_analysis.BoxDataFrame.populate",
            base_analysis.BoxDataFrame.populate,
        )
        run_step(
            "base_analysis.GitCommit.populate", base_analysis.GitCommit.populate
        )

        run_step("dlc.DLCProcessor.populate", lambda: dlc.DLCProcessor().populate())
        run_step("dlc.DLCKptsDf.populate", lambda: dlc.DLCKptsDf().populate())
        run_step(
            "dlc.SyncDLCKptsDf.populate", lambda: dlc.SyncDLCKptsDf().populate()
        )
        run_step(
            "dlc.OfflineKinematics.populate",
            lambda: dlc.OfflineKinematics().populate(),
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

    if args.aws:

        def import_decision_schema():
            from vr4mice.schema import decision

            return decision

        decision = run_import("import decision schema", import_decision_schema)
        if decision:
            run_step(
                "decision.sync_lookup_contents",
                decision.sync_lookup_contents,
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
                "decision.DecisionPoints.populate",
                lambda: decision.DecisionPoints().populate(),
            )
            run_step(
                "decision.PredictionModel10Windows.populate",
                lambda: decision.PredictionModel10Windows().populate(),
            )
            run_step(
                "decision.DecisionPoints10Windows.populate",
                lambda: decision.DecisionPoints10Windows().populate(),
            )
    else:

        def import_inputs_videos_schema():
            from vr4mice.schema import inputs_videos

            return inputs_videos

        inputs_videos = run_import(
            "import inputs_videos schema", import_inputs_videos_schema
        )
        if inputs_videos:
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

            if check_folder_existence and fetch_data:
                run_step(
                    "fetch_data",
                    lambda: (
                        check_folder_existence("/shared"),
                        fetch_data(dst="/shared/gui_menu.npy"),
                    ),
                )

    if failed_steps:
        logger.error("[cron] failed steps: %s", ", ".join(failed_steps))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
