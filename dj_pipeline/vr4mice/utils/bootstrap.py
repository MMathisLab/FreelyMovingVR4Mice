"""Shared runtime setup for run.py, cron_scenario.py, and other entry points."""

import logging
import warnings

_verbose = False


def is_verbose() -> bool:
    return _verbose


def configure_runtime(*, verbose: bool = False, debug: bool = False):
    """Configure warnings, third-party log levels, and the vr4mice logger."""
    global _verbose
    _verbose = verbose or debug

    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings(
        "ignore",
        message=r".*contains underscores.*",
        category=UserWarning,
    )

    logging.getLogger("settings").setLevel(logging.ERROR)
    logging.getLogger("datajoint").setLevel(logging.DEBUG if _verbose else logging.WARNING)

    from vr4mice.utils.logger import Logger, config_logger

    config_logger(level="INFO", debug=debug or verbose)
    return Logger.get_logger()
