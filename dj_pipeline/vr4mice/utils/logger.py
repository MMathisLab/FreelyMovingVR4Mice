import logging
import os
import sys
import tempfile
from datetime import datetime as dt
from pathlib import Path

import datajoint as dj

"""
    Logger initialisation script
"""


def _has_file_handler(logger, log_filepath: Path) -> bool:
    target = Path(log_filepath).resolve()
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                existing = Path(handler.baseFilename).resolve()
            except Exception:
                continue
            if existing == target:
                return True
    return False


def _has_stream_handler(logger) -> bool:
    return any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in logger.handlers
    )


def _resolve_log_filepath() -> Path | None:
    """Pick a writable log path; None means file logging unavailable."""
    log_filename = dt.now().strftime("log_%y%m%d_%H%M%S.log")
    candidates = [
        Path.cwd() / "logs",
        Path(os.environ.get("HOME", "/tmp")) / ".vr4mice" / "logs",
        Path(tempfile.gettempdir()) / "vr4mice_logs",
    ]
    for folder in candidates:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / log_filename
            with open(path, "a+", encoding="utf-8"):
                pass
            return path
        except OSError:
            continue
    return None


class Logger:
    __logger = None

    @classmethod
    def get_logger(cls, write_stdout=True):
        if cls.__logger:
            return cls.__logger

        logging_level = logging.INFO  # lowest level, tracks everything

        # create utils with parameters, handlers, etc
        logger = logging.getLogger("vr4mice")
        logger.setLevel(logging_level)
        logger.propagate = False

        file_formatter = logging.Formatter(
            ":%(asctime)s::%(levelname)s::%(filename)s::%(funcName)s::%(lineno)d::%(message)s"
        )
        log_filepath = _resolve_log_filepath()
        if log_filepath is not None and not _has_file_handler(logger, log_filepath):
            try:
                file_handler = logging.FileHandler(log_filepath, mode="a+")
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except OSError as err:
                print(
                    f"warning: cannot write log file {log_filepath} ({err}); "
                    "continuing with stdout only",
                    file=sys.stderr,
                )

        if write_stdout and not _has_stream_handler(logger):
            stream_handler = logging.StreamHandler()
            stream_formatter = logging.Formatter(
                "%(asctime)-s::%(levelname)s::%(filename)s::%(message)s"
            )
            stream_handler.setFormatter(stream_formatter)
            logger.addHandler(stream_handler)

        cls.__logger = logger

        return logger


def config_logger(level="INFO", debug=False):
    logger = Logger.get_logger()
    log_level = (
        logging.DEBUG if debug else getattr(logging, level.upper(), logging.INFO)
    )
    logger.setLevel(log_level)

    dj.config["loglevel"] = "DEBUG" if debug else "WARNING"

    if debug:
        logging.getLogger("datajoint").setLevel(logging.DEBUG)
