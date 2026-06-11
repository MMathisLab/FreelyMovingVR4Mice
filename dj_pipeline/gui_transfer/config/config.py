import os
import shutil
import json
import subprocess
from pathlib import Path

from utils.logger import Logger

logger = Logger.get_logger()

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


def get_system_config(
    config_path=os.environ["config_path"], config_name=os.environ["config_name"]
):
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

    Todo: config not found error
    """
    if config_path == "default":
        config_path = Path(__file__).parent.absolute().joinpath(config_name)

    if not Path(config_path).exists():
        print("Config not found")
        return False

    with open(config_path) as config_path:
        config_dict = json.load(config_path)
    return config_dict


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

     Todo: check that all default paths exist
    """

    config_dict = get_system_config()
    cache_file = Path(__file__).parent.absolute().joinpath("cache.json")

    @property
    def get_ip(self):
        return self.config_dict["ip"]

    @property
    def get_host(self):
        return self.config_dict["host"]

    @property
    def get_dst_path(self):
        return self.config_dict["remote_dst"]  # todo make here : video/data

    @property
    def get_menu_path(self):
        # scp
        ip = self.get_ip
        if ip != "localhost":
            host = self.get_host
            adr = str(host) + "@" + str(ip) + ":"
        else:
            adr = ip + ":"

        dst = self.config_dict["host_dropdown_menu"]

        if "localhost" in ip:
            src = self.config_dict["remote_dropdown_menu"]
            if Path(src) != Path(dst):
                if Path(src).exists():
                    shutil.copy(Path(src), Path(dst))
                    self.config_dict["dropdown_menu"] = dst
        else:
            src = adr + self.config_dict["remote_dropdown_menu"]
            dst = str(dst).replace("\\", "/")
            cmd = ["scp", src, dst]

            process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                logger.warning(f"{cmd} failed: {stdout} {stderr}")
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
