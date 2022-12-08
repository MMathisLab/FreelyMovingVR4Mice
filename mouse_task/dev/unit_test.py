import pytest

from pathlib import Path

from mouse_task.helpers import process_config

def test_process_config():
    # Create a mock config file
    config_file_path = "task_config.json"
    with open(config_file_path, "w") as f:
        f.write('{"model_absolute_path": "/path/to/model", "dlc_video_absolute_path": "/path/to/video", "ar_env_unity_relative_path": "unity_ar/Augmented_reality.exe"}')

    # Test the process_config() function with the mock config file
    assert process_config(config_file_path) == {
        "model_absolute_path": "/path/to/model",
        "dlc_video_absolute_path": "/path/to/video",
        "ar_env_unity_relative_path": "unity_ar/Augmented_reality.exe"
    }

    # Delete the mock config file
    Path(config_file_path).unlink()

def test_process_config_missing_file():
    # Test the process_config() function with a missing config file
    with pytest.raises(FileNotFoundError):
        process_config("missing_file.json")

def test_process_config_invalid_path():
    # Test the process_config() function with an invalid path
    with pytest.raises(TypeError):
        process_config(123)

def test_process_config_missing_keys():
    # Create a mock config file with missing keys
    config_file_path = "task_config.json"
    with open(config_file_path, "w") as f:
        f.write('{"model_absolute_path": "/path/to/model", "ar_env_unity_relative_path": "unity_ar/Augmented_reality.exe"}')

    # Test the process_config() function with the mock config file
    assert process_config(config_file_path) is None

    # Delete the mock config file
    Path(config_file_path).unlink()

def test_process_config_non_existent_paths():
    # Create a mock config file with non-existent paths
    config_file_path = "task_config.json"
    with open(config_file_path, "w") as f:
        f.write('{"model_absolute_path": "/path/to/missing/model", "dlc_video_absolute_path": "/path/to/missing/video", "ar_env_unity_relative_path": "unity_ar/missing/Augmented_reality.exe"}')

    # Test the process_config() function with the mock config file
    assert process_config(config_file_path) is None

    # Delete the mock config file
    Path(config_file_path).unlink()
