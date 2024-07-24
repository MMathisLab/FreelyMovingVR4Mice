import pytest
from unittest.mock import patch, MagicMock
import numpy as np
from mouse_task.mouse_VisualDiscrim_random_occluders import ARVisualDiscrim_randomoccluders

@pytest.fixture
def mock_dlcclient():
    with patch('mouse_task.mouse_VisualDiscrim_random_occluders.DLCClient') as mock_dlc:
        mock_dlc_instance = mock_dlc.return_value
        mock_dlc_instance.read.return_value = {"vals": [100, 200, 50], "time": 0.5}
        yield mock_dlc

@pytest.fixture
def task(mock_dlcclient):
    teensy_mock = MagicMock()
    with patch('mouse_task.mouse_VisualDiscrim_random_occluders.process_config') as mock_process_config:
        mock_process_config.return_value = {
            "model_absolute_path": "model_path",
            "dlc_video_absolute_path": "video_path",
            "ar_env_unity_absolute_path": "env_path"
        }
        task_instance = ARVisualDiscrim_randomoccluders(teensy_mock)
        yield task_instance

def test_random_target_location(task):
    initial_value = task.Object_on_left
    task.Prob_Obj_on_Left = 0.5
    task.random_target_location()
    assert task.Object_on_left in [0.0, 1.0]
    #assert task.Object_on_left != initial_value

def test_random_target_locationL(task):
    task.Prob_Obj_on_Left = 1.0
    task.random_target_location()
    assert task.Object_on_left == 1.0

def test_random_target_locationR(task):
    task.Prob_Obj_on_Left = 0.0
    task.random_target_location()
    assert task.Object_on_left == 0.0

def test_block_sampler_switch_block(task):
    task.correct = task.block_length
    initial_block_Left = task.block_Left
    task.block_sampler()
    assert task.correct == 0
    assert task.block_Left != initial_block_Left

def test_block_sampler_no_switch_block(task):
    task.correct = 0
    initial_block_Left = task.block_Left
    task.block_sampler()
    assert task.correct == 0
    assert task.block_Left == initial_block_Left
