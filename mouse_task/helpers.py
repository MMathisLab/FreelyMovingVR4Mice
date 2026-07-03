"""
 Helpers functions for mouse_ar_task.py
"""
import json
import logging
from pathlib import Path

import yaml

# Directory holding the modular task configs (``common.yaml`` + ``tasks/*.yaml``).
CONFIG_DIR = Path(__file__).parent / "configs"


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge ``override`` into ``base`` in-place."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def load_task_config(task_config: str, config_dir: Path = CONFIG_DIR) -> dict:
    """Load ``common.yaml`` and overlay the task-specific overrides.

    Args:
        task_config: Stem of a file in ``configs/tasks/`` (e.g. ``"shape_mouse_discrim"``).
        config_dir: Root of the config tree (defaults to ``mouse_task/configs``).

    Returns:
        Flat dict of task parameters: every key from ``common.yaml`` with the
        task's ``params`` block merged on top.
    """
    params = _load_yaml(config_dir / "common.yaml")

    task_path = config_dir / "tasks" / f"{task_config}.yaml"
    if not task_path.exists():
        available = sorted(p.stem for p in (config_dir / "tasks").glob("*.yaml"))
        raise FileNotFoundError(
            f"Task config not found: {task_path}. Available: {available}"
        )
    _deep_merge(params, _load_yaml(task_path).get("params") or {})
    return params


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
