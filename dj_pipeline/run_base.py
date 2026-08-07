#!/usr/bin/env python3
"""
Entry point for exp/mice recovery and parent-DB sync (not a replacement for cron).

Run inside the Docker client (make bash), not host python:

    python run_base.py sync_mice
    python run_base.py sync_mice --mouse Flamingo
    python run_base.py sync_mice --mouse Flamingo --mouse Whale

Normal ingest (also in client): python run.py populate | analysis | dlc | ...

Modes (see docs/software/base_schema_sync.md):
    sync_mice        - pull Mouse metadata from main (local names, or --mouse)
    recover_base     - populate unpopulated GUI .npy into local exp/mice only
    cleanup_orphans  - list/delete local exp/mice with no vr4mice.Dataset
    cleanup_mice     - remove stub Mouse rows without local sessions
    sync_exp         - optional: push missing local (non-collab) sessions to main
"""

import argparse
import os

from base_actions.utils.login import LoginUser
from base_actions.utils.schema_config import connect_to_database
from vr4mice.utils.bootstrap import configure_runtime
from vr4mice.utils.logger import Logger

logger = Logger.get_logger()


def _connect_from_env() -> None:
    """Connect via DJ_* env vars (do not parse sys.argv — unlike connect())."""
    connect_to_database(
        LoginUser(
            user_name=os.environ["DJ_USER"],
            user_password=os.environ["DJ_PWD"],
            db_host=os.environ["DJ_HOST"],
        ),
        prefix="",
        create_tables=True,
    )


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
        "--mouse",
        action="append",
        dest="mice",
        metavar="NAME",
        help="With sync_mice: pull this mouse from main (repeatable). "
        "Use to preload before recordings. Default: incomplete local Dataset/GUI/Session names.",
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
    _connect_from_env()

    if args.mode == "sync_mice":
        from vr4mice.actions.mouse_sync import sync_mice_from_main

        sync_mice_from_main(log=logger, mouse_names=args.mice)

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
