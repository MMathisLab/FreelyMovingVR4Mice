"""One-off maintenance tasks for the DataJoint pipeline."""

from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def rebuild_lineage():
    """Rebuild DataJoint lineage tables for all pipeline schemas."""
    from vr4mice.schema import (
        base,
        base_analysis,
        decision,
        dlc,
        inputs_videos,
        interpolated_trajectories,
        latency_tests,
        session_metrics,
        vr4mice,
    )

    schemas = [
        ("vr4mice", vr4mice.schema),
        ("base", base.schema),
        ("base_analysis", base_analysis.schema),
        ("dlc", dlc.schema),
        ("session_metrics", session_metrics.schema),
        ("interpolated_trajectories", interpolated_trajectories.schema),
        ("latency_tests", latency_tests.schema),
        ("inputs_videos", inputs_videos.schema),
        ("decision", decision.schema),
    ]

    for name, schema in schemas:
        logger.info("Rebuilding lineage for %s", name)
        schema.rebuild_lineage()
        logger.info("Done rebuilding lineage for %s", name)
