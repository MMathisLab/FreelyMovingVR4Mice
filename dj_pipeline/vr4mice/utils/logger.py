import logging
from datetime import datetime as dt
from pathlib import Path

import datajoint as dj


"""
    Logger initialisation script
"""


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
        logger = logging.getLogger()
        logger.setLevel(logging_level)

        file_formatter = logging.Formatter(
            "%(asctime)s::%(levelname)s::%(filename)s::%(funcName)s::%(lineno)d::%(message)s"
        )
        file_handler = logging.FileHandler(log_filepath, mode="a+")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        if write_stdout:
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
