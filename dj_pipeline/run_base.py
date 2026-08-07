"""
Entry point for exp/mice recovery and parent-DB sync (not a replacement for cron).

Normal ingest: python run.py populate | analysis | dlc | ...
With GUI=True, that populate path writes exp/mice from session .npy as usual.

Recovery / registry sync (run separately; see docs/software/base_schema_sync.md):
    sync_mice        — pull Mouse metadata from main (Dataset/Session/GUI names)
    recover_base     — populate unpopulated GUI .npy into local exp/mice only
    cleanup_orphans  — list/delete local exp/mice with no vr4mice.Dataset
    cleanup_mice     — remove stub Mouse rows without local sessions
    sync_exp         — optional: push missing local (non-collab) sessions to main
"""

import argparse

from base_actions.connect import connect
from vr4mice.utils.bootstrap import configure_runtime
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="exp/mice recovery and parent-DB sync (run.py remains normal cron ingest)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply destructive cleanup (cleanup_orphans, cleanup_mice).",
    )
    parser.add_argument(
        "mode",
        choices=[
            "sync_mice",
            "sync_exp",
            "recover_base",
            "cleanup_orphans",
            "cleanup_mice",
        ],
        help="Recovery / sync mode to execute.",
    )

    args = parser.parse_args()

    logger = configure_runtime(verbose=args.verbose, debug=args.verbose)
    connect(tag="")

    if args.mode == "sync_mice":
        from vr4mice.actions.mouse_sync import sync_mice_from_main

        sync_mice_from_main(log=logger)

    elif args.mode == "sync_exp":
        from vr4mice.actions.mouse_sync import sync_exp_to_main

        sync_exp_to_main(log=logger)

    elif args.mode == "recover_base":
        from vr4mice.actions.recover_base import run_recovery

        run_recovery()

    elif args.mode == "cleanup_orphans":
        from vr4mice.actions.recover_base import (
            check_replication_off,
            cleanup_orphan_exp_mice,
        )

        check_replication_off(log=logger)
        cleanup_orphan_exp_mice(dry_run=not args.force)

    elif args.mode == "cleanup_mice":
        from vr4mice.actions.mouse_sync import cleanup_mice_without_sessions

        cleanup_mice_without_sessions(dry_run=not args.force, stubs_only=True)
