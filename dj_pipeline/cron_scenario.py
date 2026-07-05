import argparse
import time

from vr4mice.utils.bootstrap import configure_runtime


def main():
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
    args = parser.parse_args()

    from base_actions.connect import connect

    logger = configure_runtime(verbose=args.verbose, debug=args.verbose)
    failed_steps = []

    def run_named(name, func, *, capture=False):
        logger.info("[cron] start %s", name)
        started = time.monotonic()
        try:
            result = func()
            elapsed = time.monotonic() - started
            logger.info("[cron] done %s (%.1fs)", name, elapsed)
            return result if capture else None
        except Exception:
            elapsed = time.monotonic() - started
            logger.exception("[cron] failed %s (%.1fs)", name, elapsed)
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
            summary_emails,
        )

        return (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
            summary_emails,
        )

    core_schemas = run_import("import core schemas", import_core_schemas)
    if core_schemas and create_folder_if_not_exist:
        from vr4mice.utils.populate_helpers import populate_pending

        (
            base_analysis,
            dlc,
            vr4mice,
            interpolated_trajectories,
            session_metrics,
            latency_tests,
            summary_emails,
        ) = core_schemas

        run_step(
            "create_summary_plots_dir",
            lambda: create_folder_if_not_exist("/data/summary_plots"),
        )

        run_step(
            "vr4mice.Collab.populate",
            lambda: populate_pending(vr4mice.Collab, vr4mice.Dataset, logger=logger),
        )
        run_step(
            "base_analysis.DataFrame.populate",
            lambda: populate_pending(
                base_analysis.DataFrame, vr4mice.Dataset, logger=logger
            ),
        )
        run_step(
            "base_analysis.BoxDataFrame.populate",
            lambda: populate_pending(
                base_analysis.BoxDataFrame, base_analysis.DataFrame, logger=logger
            ),
        )
        run_step(
            "base_analysis.GitCommit.populate",
            lambda: populate_pending(
                base_analysis.GitCommit, base_analysis.DataFrame, logger=logger
            ),
        )

        run_step(
            "dlc.DLCProcessor.populate",
            lambda: populate_pending(dlc.DLCProcessor, vr4mice.DLC, logger=logger),
        )
        run_step(
            "dlc.DLCKptsDf.populate",
            lambda: populate_pending(dlc.DLCKptsDf, vr4mice.DLC, logger=logger),
        )
        run_step(
            "dlc.SyncDLCKptsDf.populate",
            lambda: populate_pending(
                dlc.SyncDLCKptsDf, dlc.DLCKptsDf, logger=logger
            ),
        )
        run_step(
            "dlc.OfflineKinematics.populate",
            lambda: populate_pending(
                dlc.OfflineKinematics, dlc.SyncDLCKptsDf, logger=logger
            ),
        )

        run_step(
            "session_metrics.SessionMetrics.populate",
            lambda: populate_pending(
                session_metrics.SessionMetrics, vr4mice.Dataset, logger=logger
            ),
        )
        run_step(
            "session_metrics.TrialMetrics.populate",
            lambda: populate_pending(
                session_metrics.TrialMetrics, base_analysis.DataFrame, logger=logger
            ),
        )

        run_step(
            "interpolated_trajectories.InterpolatedTrials.populate",
            lambda: populate_pending(
                interpolated_trajectories.InterpolatedTrials,
                base_analysis.DataFrame,
                logger=logger,
            ),
        )
        run_step(
            "interpolated_trajectories.MeanXYTrajectory.populate",
            lambda: populate_pending(
                interpolated_trajectories.MeanXYTrajectory,
                interpolated_trajectories.InterpolatedTrials,
                logger=logger,
            ),
        )
        run_step(
            "interpolated_trajectories.YBinnedXYTrajectory.populate",
            lambda: populate_pending(
                interpolated_trajectories.YBinnedXYTrajectory,
                interpolated_trajectories.InterpolatedTrials,
                logger=logger,
            ),
        )
        run_step(
            "interpolated_trajectories.MeanVelocities.populate",
            lambda: populate_pending(
                interpolated_trajectories.MeanVelocities,
                interpolated_trajectories.InterpolatedTrials,
                logger=logger,
            ),
        )

        run_step(
            "vr4mice.SignalsPhotodiode.populate",
            lambda: populate_pending(
                vr4mice.SignalsPhotodiode, vr4mice.Dataset, logger=logger
            ),
        )
        run_step(
            "latency_tests.SignalsPhotodiodeAligned.populate",
            lambda: populate_pending(
                latency_tests.SignalsPhotodiodeAligned,
                vr4mice.SignalsPhotodiode,
                logger=logger,
            ),
        )
        run_step(
            "latency_tests.AllLatencies.populate",
            lambda: populate_pending(
                latency_tests.AllLatencies,
                latency_tests.SignalsPhotodiodeAligned,
                logger=logger,
            ),
        )

        run_step(
            "base_analysis.SummaryPlots.populate",
            lambda: populate_pending(
                base_analysis.SummaryPlots,
                base_analysis.DataFrame & base_analysis.BoxDataFrame,
                logger=logger,
            ),
        )
        run_step(
            "summary_emails.send_pending_summary_emails",
            lambda: summary_emails.send_pending_summary_emails(logger=logger),
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
            from vr4mice.schema import vr4mice
            from vr4mice.utils.populate_helpers import populate_pending

            run_step(
                "inputs_videos.RawVideo.populate",
                lambda: populate_pending(
                    inputs_videos.RawVideo, vr4mice.Dataset, logger=logger
                ),
            )
            run_step(
                "inputs_videos.ProcessedVideo.populate",
                lambda: populate_pending(
                    inputs_videos.ProcessedVideo,
                    inputs_videos.RawVideo,
                    logger=logger,
                ),
            )
            run_step(
                "inputs_videos.VideoSyncSignal.populate",
                lambda: populate_pending(
                    inputs_videos.VideoSyncSignal,
                    inputs_videos.ProcessedVideo,
                    logger=logger,
                ),
            )
            run_step(
                "inputs_videos.AlignedVideoFrame.populate",
                lambda: populate_pending(
                    inputs_videos.AlignedVideoFrame,
                    inputs_videos.VideoSyncSignal,
                    logger=logger,
                ),
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
