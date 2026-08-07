"""
Entry point for exp/mice base-schema workflows (separate from the main vr4mice cron).

Use this script on rigs that sync local exp/mice with a main database registry.
The main pipeline remains: python run.py populate | analysis | dlc | ...

Modes:
    sync_mice     — pull Mouse metadata from main DB (DJ_MAIN_HOST)
    sync_exp      — push local exp.Session (+ SessionScoreSheet) to main DB
    cleanup_mice  — remove stub Mouse rows without local sessions
    recover_base  — recovery: cleanup orphans, repopulate exp/mice from GUI files
    sync_days     — fix experiment day in GUI .npy files (data + processed)
    fetch         — export gui_menu.npy for the rig GUI dropdowns
    populate      — ingest with exp/mice base schema (POPULATE_BASE on)
"""

import argparse
import os
import sys

from base_actions.connect import connect
from vr4mice.utils.bootstrap import configure_runtime
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def check_folder_existence(folder_path: str) -> None:
    if not os.path.exists(folder_path):
        logger.warning("Folder '%s' does not exist. Exiting.", folder_path)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="exp/mice base schema utilities (separate from run.py cron pipeline)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level).",
    )
    parser.add_argument(
        "--aws",
        action="store_true",
        help="AWS layout: read from /data/processed, do not move files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply destructive cleanup (cleanup_mice, recover_base).",
    )
    parser.add_argument(
        "--no-populate-base",
        action="store_true",
        help="For populate mode only: skip exp/mice base schema (vr4mice only).",
    )
    parser.add_argument(
        "mode",
        choices=[
            "sync_mice",
            "sync_exp",
            "cleanup_mice",
            "recover_base",
            "sync_days",
            "fetch",
            "populate",
        ],
        help="Base-schema mode to execute.",
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

    elif args.mode == "cleanup_mice":
        from vr4mice.actions.mouse_sync import cleanup_mice_without_sessions

        cleanup_mice_without_sessions(dry_run=not args.force, stubs_only=True)

    elif args.mode == "recover_base":
        from vr4mice.actions.recover_base import run_recovery

        run_recovery(force=args.force)

    elif args.mode == "sync_days":
        from vr4mice.actions.sync_days import sync_days

        sync_days()

    elif args.mode == "fetch":
        from vr4mice.actions.fetch_data import fetch_data

        check_folder_existence("/shared")
        fetch_data(dst="/shared/gui_menu.npy")

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
        populate_rig(
            path=path,
            move=move,
            populate_base=not args.no_populate_base,
        )
        populate_pending(vr4mice.Collab, vr4mice.Dataset, logger=logger)
