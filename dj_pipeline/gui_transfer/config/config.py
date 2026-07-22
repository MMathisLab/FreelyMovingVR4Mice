import os
import shutil
import json
import subprocess
from pathlib import Path

from utils.logger import Logger

logger = Logger.get_logger()

REQUIRED_CONFIG_KEYS = (
    "ip",
    "host",
    "remote_dropdown_menu",
    "host_dropdown_menu",
    "gui_output_folder",
    "cache",
    "remote_dst",
    "raw_data_src",
    "dlc_path",
    "proc_path",
    "video_path",
    "camera_path",
    "teensy_path",
    "processed_path",
)

"""
config.json example 

{
  "ip": "localhost",
  "host": "",

  "remote_dropdown_menu": "/shared/gui_menu.npy",
  "host_dropdown_menu": "./gui_menu.npy",

  "gui_output_folder": "./test_output/raw",
  "cache": "default",

  "remote_dst": "/tmp/test_transfer",

  "raw_data_src": "/data",
  "dlc_path": "/data/dlc_video_raw",
  "proc_path": "/data/lc_video_raw",
  "video_path": "/data/dlc_video_raw",
  "camera_path": "/data/dlc_video_raw",
  "teensy_path": "/data/raw",

  "processed_path": "/data/processed_rig"
}

"""


def get_system_config(config_path=None, config_name=None):
    """
    Loads the system configuration from a JSON file.

    Args:
    config_path (str): The path to the configuration file.
        Defaults to "default", which will look for the file "config.json" in the same directory as this script.
    config_name (str): The name of the configuration file.
        Defaults to "config.json".

    Returns:
    dict or False: The system configuration as a dictionary, or False if the configuration file is not found.

    Notes:
    - This function assumes that the configuration file is a JSON file.
    - If config_path is set to "default", the configuration file is assumed to be named "config.json"
        and located in the same directory as this script.
    - If the configuration file is not found, the function returns False.
    - If the configuration file is found but there is an error loading it,
    an error message will be printed to the console and the function will return None.
    """
    if config_path is None:
        config_path = os.environ.get("config_path", "default")
    if config_name is None:
        config_name = os.environ.get("config_name", "config.json")

    if config_path == "default":
        config_path = Path(__file__).parent.absolute().joinpath(config_name)

    if not Path(config_path).exists():
        print("Config not found")
        return False

    with open(config_path) as config_file:
        config_dict = json.load(config_file)
    return config_dict


def validate_config(config_dict):
    """
    Validate that config.json contains required keys.

    Returns:
        tuple (ok: bool, message: str)
    """
    if not config_dict or not isinstance(config_dict, dict):
        return False, "Config file missing or invalid JSON."
    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config_dict]
    if missing:
        return False, "Missing config keys: " + ", ".join(missing)
    if (
        "localhost" not in str(config_dict.get("ip", ""))
        and not str(config_dict.get("host", "")).strip()
    ):
        return False, "Config 'host' (SSH user) is required when ip is not localhost."
    return True, ""


class Config:
    """
    A class for managing system configuration settings.

    Attributes:
    -----------
    config_dict : dict
        A dictionary containing the configuration settings loaded from the config file.
    cache_file : str
        A string representing the path to the cache file.

    Methods:
    --------
    get_ip()
        Returns the IP address of the configured system.
    get_host()
        Returns the host address of the configured system.
    get_dst_path()
        Returns the destination path for remote files.
    get_menu_path (property)
        Copies the remote dropdown menu to the local host and returns its path.
    get_gui_output_folder_path()
        Returns the path to the configured GUI output folder.
    get_cache_file_path()
        Returns the path to the cache file.
    get_processed_path()
        Returns the path to the configured processed data folder.
    get_path(key)
        Returns the path for a given key.
    get_config(key)
        Returns the configuration value for a given key.
    update(key, value)
        Updates the value for a given configuration key.
    """

    config_dict = get_system_config()
    cache_file = Path(__file__).parent.absolute().joinpath("cache.json")

    @classmethod
    def validate(cls):
        return validate_config(cls.config_dict)

    @property
    def get_ip(self):
        return self.config_dict["ip"]

    @property
    def get_host(self):
        return self.config_dict["host"]

    @property
    def get_dst_path(self):
        return self.config_dict["remote_dst"]

    @property
    def get_menu_path(self):
        dst = self.config_dict["host_dropdown_menu"]
        ip = self.get_ip

        if "localhost" in ip:
            src = self.config_dict["remote_dropdown_menu"]
            src_path = Path(src)
            dst_path = Path(dst)
            if src_path != dst_path:
                if not src_path.exists():
                    logger.warning(f"Menu file not found: {src}")
                    return False
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dst_path)
            self.config_dict["dropdown_menu"] = str(dst_path)
            return self.config_dict["dropdown_menu"]

        host = self.get_host
        adr = str(host) + "@" + str(ip) + ":"
        src = adr + self.config_dict["remote_dropdown_menu"]
        dst = str(dst).replace("\\", "/")
        cmd = ["scp", src, dst]

        process = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            stdout_s = (
                stdout.decode(errors="replace")
                if isinstance(stdout, (bytes, bytearray))
                else str(stdout)
            )
            stderr_s = (
                stderr.decode(errors="replace")
                if isinstance(stderr, (bytes, bytearray))
                else str(stderr)
            )
            logger.warning(f"{cmd} failed: {stdout_s} {stderr_s}")
            return False
        self.config_dict["dropdown_menu"] = dst
        return self.config_dict["dropdown_menu"]

    @property
    def get_gui_output_folder_path(self):
        return self.config_dict["gui_output_folder"]

    @property
    def get_cache_file_path(self):
        if self.config_dict["cache"] == "default":
            return self.cache_file
        return self.config_dict["cache"]

    @property
    def get_processed_path(self):
        return self.config_dict["processed_path"]

    def get_path(self, key):
        if key in self.config_dict.keys():
            if self.config_dict[key] != "default":
                return self.config_dict[key]
        return self.config_dict["raw_data_src"]

    def get_config(self, key):
        return self.config_dict[key]

    def update(self, key, value):
        self.config_dict[key] = value


config = Config()
