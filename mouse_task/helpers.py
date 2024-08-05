"""
 Helpers functions for mouse_ar_task.py
"""
import json
import logging
from pathlib import Path

def process_config(config_file_path: Path) -> dict:
    """
        Function that processes the task_config file and verifies its content

        Example of json task_config file:

        config.json
        {
            "model_absolute_path": "/home/user/Models/model_name,
            "dlc_video_absolute_path": "/home/user/Videos/video.mp4",
            "ar_env_unity_absolute_path": "unity_ar/Augmented_reality.exe"
        }

        Args:
            config_file_path(Path): path to config file
        Returns:
            dictionary with keys or None if error uncounted

        Notes: errors are reported via logger

    """

    # Check if the config file path is a valid Path object,
    # and if it exists on the file system
    if not isinstance(config_file_path, Path) or not config_file_path.exists():
        logging.error(str(config_file_path) + " does not exist.")
        return None

    # Read the contents of the config file
    try:
        with open(config_file_path) as task_config_file:
            config_dict = json.load(task_config_file)
    except OSError as err:
        logging.error(err)
        return None

    # Check if all necessary keys are present in the config file
    keys = ["ar_env_unity_absolute_path"]
    for k in keys:
        if k not in config_dict:
            logging.error(k + " not in " + config_file_path)

    for paths in config_dict.values():
        if not Path(paths).exists():
            logging.error(str(paths) + " does not exist.")
            return None

    return config_dict
