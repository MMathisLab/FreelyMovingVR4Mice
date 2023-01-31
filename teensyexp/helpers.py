"""
 Helpers functions for mouse_ar_task.py
"""
import json
import logging
from pathlib import Path
logging.getLogger().setLevel(logging.INFO)

def process_config(config_file_path: Path) -> dict:
    """
        Function that processes the config file and verifies its content

        Example of json config file:

        config.json
        {
            "config_path": "/home/user/config,
        }

        Args:
            config_file_path(Path): path to config file
        Returns:
            dictionary with keys or None if error uncounted

        Notes: errors are reported via logger

    """

    # Check if the config file path is a valid Path object,
    # and if it exists on the file system
    if not isinstance(config_file_path, Path):
        config_file_path = Path(config_file_path)

    if not config_file_path.exists():
        logging.debug(str(config_file_path) + " does not exist.")
        return None

    # Read the contents of the config file
    try:
        with open(config_file_path) as task_config_file:
            config_dict = json.load(task_config_file)
    except OSError as err:
        logging.info(err)
        return None

    # Check if all necessary keys are present in the config file
    keys = ["config_path"]
    for k in keys:
        if k not in config_dict:
            logging.debug(k + " not in " + config_file_path)

    for paths, keys in config_dict.items():
        paths = Path(paths).absolute()
        if not paths.exists():
            logging.debug(str(paths) + " does not exist.")
            return None
        config_dict[keys] = paths
    return config_dict
