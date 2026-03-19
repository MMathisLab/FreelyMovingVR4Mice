import logging
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


class Logger:
    __logger = None

    @classmethod
    def get_logger(cls):
        if cls.__logger:
            return cls.__logger

        log_filename = dt.now().strftime("log_%y%m%d_%H%M%S.log")
        logs_folder = Path(__name__).parent / "logs"
        logs_folder.mkdir(parents=True, exist_ok=True)

        write_stdout = True
        log_filepath = logs_folder / log_filename
        logging_level = logging.INFO  # lowest level, tracks everything

        # TODO(ahmed) if useful: read config file and get parameters

        # create utils with parameters, handlers, etc
        logger = logging.getLogger("base_actions")
        logger.setLevel(logging_level)
        logger.propagate = False

        file_formatter = logging.Formatter(
            "%(asctime)s::%(levelname)s::%(filename)s::%(funcName)s::%(lineno)d::%(message)s"
        )
        if not _has_file_handler(logger, log_filepath):
            file_handler = logging.FileHandler(log_filepath, mode="a+")
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        if write_stdout and not _has_stream_handler(logger):
            stream_handler = logging.StreamHandler()
            # different formatter, more readable in console
            stream_formatter = formatter = logging.Formatter(
                "%(asctime)-s::%(levelname)s::%(filename)s::%(message)s"
            )
            stream_handler.setFormatter(stream_formatter)
            logger.addHandler(stream_handler)

        cls.__logger = logger

        return logger


def config_logger(level="INFO", debug=False):
    logger = Logger.get_logger()
    logger.setLevel(logging.INFO)

    dj.config["loglevel"] = "INFO"

    if debug:
        logger.setLevel(logging.DEBUG)
        dj.config["loglevel"] = "DEBUG"
