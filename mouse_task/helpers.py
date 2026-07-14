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

    # Validate required key for runtime.
    required_key = "ar_env_unity_absolute_path"
    if required_key not in config_dict:
        logging.error(required_key + " not in " + str(config_file_path))
        return None

    # Only this path is required for task startup.
    env_path = config_dict[required_key]
    if not Path(env_path).exists():
        logging.error(str(env_path) + " does not exist.")
        return None

    return config_dict
