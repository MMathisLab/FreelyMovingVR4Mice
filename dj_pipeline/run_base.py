#!/usr/bin/env python3
"""
Entry point for exp/mice recovery (not a replacement for cron).

Run inside the Docker client (make bash), not host python:

    python run_base.py recover_base
    python run_base.py cleanup_orphans
    python run_base.py cleanup_mice --force
    python run_base.py check_session_days
    python run_base.py fix_session_days
    python run_base.py fix_session_days --force

Mouse registry sync from parent is host-side only (no DataJoint):

    make -f mysql.mk sync-mice-from-main
    make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale

Normal ingest (also in client): python run.py populate | analysis | dlc | ...

Modes (see docs/software/base_schema_sync.md):
    recover_base       - populate unpopulated GUI .npy into local exp/mice only
    cleanup_orphans    - list/delete local exp/mice with no vr4mice.Dataset
    cleanup_mice       - remove stub Mouse rows without local sessions
    check_session_days - exit 1 if any exp.Session.day disagrees with doe timeline
    fix_session_days   - rekey Session.day to doe timeline (dry-run; --force applies)

Destructive modes log DJ_HOST + live MySQL host:port/uuid before any change.
"""

import argparse
import os
import sys
import traceback

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
        description="exp/mice recovery (run.py remains normal cron ingest)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Apply changes (cleanup_orphans, cleanup_mice, fix_session_days)."
        ),
    )
    parser.add_argument(
        "mode",
        choices=[
            "recover_base",
            "cleanup_orphans",
            "cleanup_mice",
            "check_session_days",
            "fix_session_days",
        ],
        help="Recovery mode to execute.",
    )

    args = parser.parse_args()

    logger = configure_runtime(verbose=args.verbose, debug=args.verbose)
    try:
        _connect_from_env()

        if args.mode == "recover_base":
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
            from vr4mice.actions.recover_base import log_mutation_target

            log_mutation_target(
                action="cleanup_mice", dry_run=not args.force, log=logger
            )
            cleanup_mice_without_sessions(dry_run=not args.force, stubs_only=True)

        elif args.mode == "check_session_days":
            from vr4mice.actions.recover_base import check_session_days

            check_session_days(raise_on_mismatch=True)

        elif args.mode == "fix_session_days":
            from vr4mice.actions.recover_base import fix_session_days

            fix_session_days(dry_run=not args.force)
    except Exception:
        logger.exception("run_base.py failed")
        traceback.print_exc()
        sys.exit(1)
