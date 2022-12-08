from helpers import process_config
from pathlib import Path
import logging
import json

def create_paths(config_name: str):
    # Create a dictionary with the paths
    test_dic = {
        "model_absolute_path": "./mary/model",
        "dlc_video_absolute_path": "./mary/dlc.mp4",
        "ar_env_unity_relative_path": "unity_ar/Augmented_reality.exe"
    }

    # Create the directories and files specified in the dictionary
    for path in test_dic.values():
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

    # Write the dictionary to a config file
    with open(config_name, "w") as outfile:
        json.dump(test_dic, outfile)

    return config_name


def main():
    """
        program main entry point
    """
    config = Path("./task_config_demo.json")
    create_paths(config)
    ret = process_config(config)

__name__ == '__main__'
main()