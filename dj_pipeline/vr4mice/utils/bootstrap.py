"""Shared runtime setup for run.py, cron_scenario.py, and other entry points."""

import logging
import warnings

_verbose = False


class _DataJointNoiseFilter(logging.Filter):
    """Drop repetitive DJ 2.x messages that are safe to ignore after explicit-key fixes."""

    _SKIP_SUBSTRINGS = ("Semantic check disabled: ~lineage table not found",)

    def filter(self, record: logging.LogRecord) -> bool:
        if _verbose:
            return True
        message = record.getMessage()
        return not any(skip in message for skip in self._SKIP_SUBSTRINGS)


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

    dj_logger = logging.getLogger("datajoint")
    dj_logger.addFilter(_DataJointNoiseFilter())
    dj_logger.setLevel(logging.DEBUG if _verbose else logging.WARNING)

    logging.getLogger("settings").setLevel(logging.ERROR)

    from vr4mice.utils.logger import Logger, config_logger

    config_logger(level="INFO", debug=debug or verbose)
    return Logger.get_logger()
