import logging


def get_logger(log_file_name="base_schemas.log"):
    # Check if the logger is already initialized
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        # Logger is not initialized, configure it
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Create a FileHandler to write log messages to a file
        file_handler = logging.FileHandler(log_file_name)

        # Set the logging level for the file handler (you can adjust this as needed)
        file_handler.setLevel(logging.DEBUG)

        # Create a formatter for the file handler (optional)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add the file handler to the logger
        logger.addHandler(file_handler)

    return logger


# Example usage:
logger = get_logger()
