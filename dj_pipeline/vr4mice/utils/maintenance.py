"""One-off maintenance tasks for the DataJoint pipeline."""

from __future__ import annotations

from typing import Iterable, Tuple

from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def _schema_pairs() -> Iterable[Tuple[str, object]]:
    """
    Schemas in dependency order for rebuild_lineage().

    mice/exp must come before base (Base -> Mouse, Session). vr4mice must
    come before base (Base -> Dataset).
    """
    from base_schemas.schemas import exp, mice
    from vr4mice.schema import (
        base,
        base_analysis,
        decision,
        dlc,
        inputs_videos,
        interpolated_trajectories,
        latency_tests,
        session_metrics,
        summary_emails,
        vr4mice,
    )

    return (
        ("mice", mice.schema),
        ("exp", exp.schema),
        ("vr4mice", vr4mice.schema),
        ("base", base.schema),
        ("base_analysis", base_analysis.schema),
        ("summary_emails", summary_emails.schema),
        ("dlc", dlc.schema),
        ("session_metrics", session_metrics.schema),
        ("interpolated_trajectories", interpolated_trajectories.schema),
        ("latency_tests", latency_tests.schema),
        ("inputs_videos", inputs_videos.schema),
        ("decision", decision.schema),
    )


def rebuild_lineage(*, strict: bool = True) -> None:
    """Rebuild DataJoint lineage tables for all pipeline schemas."""
    failed = []

    for name, schema in _schema_pairs():
        logger.info("Rebuilding lineage for %s", name)
        try:
            schema.rebuild_lineage()
        except Exception:
            logger.exception("Failed rebuilding lineage for %s", name)
            failed.append(name)
        else:
            logger.info("Done rebuilding lineage for %s", name)

    if failed:
        msg = f"Lineage rebuild failed for: {', '.join(failed)}"
        if strict:
            raise RuntimeError(msg)
        logger.warning(msg)
