import os
import json

BASE_DIR = "/tmp/vr4mice_test_gui"

config = {
    "ip": "localhost",
    "host": "",
    "remote_dropdown_menu": f"{os.getcwd()}/menu.npy",
    "host_dropdown_menu": f"{BASE_DIR}/menu.npy",
    "gui_output_folder": f"{BASE_DIR}/raw",
    "cache": "default",
    "remote_dst": f"{BASE_DIR}/remote",
    "raw_data_src": f"{BASE_DIR}/dlc_video_raw",
    "dlc_path": f"{BASE_DIR}/dlc_video_raw",
    "proc_path": f"{BASE_DIR}/dlc_video_raw",
    "video_path": f"{BASE_DIR}/dlc_video_raw",
    "camera_path": f"{BASE_DIR}/dlc_video_raw",
    "teensy_path": f"{BASE_DIR}/dlc_video_raw",
    "processed_path": f"{BASE_DIR}/processed_rig",
}

# Save as JSON file
config_path = "test_config.json"
with open(config_path, "w") as file:
    json.dump(config, file, indent=4)

print(f"Config file saved as {config_path}")
