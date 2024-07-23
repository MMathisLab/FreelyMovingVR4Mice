import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from mouse_task.mouse_VisualDiscrim_random_occluders import ARVisualDiscrim_randomoccluders

class TestARVisualDiscrim_randomoccluders(unittest.TestCase):

    def setUp(self):
        self.teensy_mock = MagicMock()
        with patch('mouse_task.mouse_VisualDiscrim_random_occluders.process_config') as mock_process_config:
            mock_process_config.return_value = {
                "model_absolute_path": "model_path",
                "dlc_video_absolute_path": "video_path",
                "ar_env_unity_absolute_path": "env_path"
            }
            self.mock_dlcclient = patch('mouse_task.mouse_VisualDiscrim_random_occluders.DLCClient').start()
            self.mock_dlcclient_instance = self.mock_dlcclient.return_value
            self.mock_dlcclient_instance.read.return_value = {"vals": [100, 200, 50], "time": 0.5}
            self.task = ARVisualDiscrim_randomoccluders(self.teensy_mock)

    def test_random_target_location(self):
        initial_value = self.task.Object_on_left
        self.task.Prob_Obj_on_Left = 0.5
        self.task.random_target_location()
        self.assertIn(self.task.Object_on_left, [0.0, 1.0])
        #self.assertNotEqual(self.task.Object_on_left, initial_value)
        
    def test_random_target_locationL(self):
        # test with probability giving a certain left choice
        self.task.Prob_Obj_on_Left = 1.0
        self.task.random_target_location()
        self.assertEqual(self.task.Object_on_left, 1.0)
    
    def test_random_target_locationR(self):
        self.task.Prob_Obj_on_Left = 0.0
        self.task.random_target_location()
        self.assertEqual(self.task.Object_on_left, 0.0)
        

    def test_block_sampler_switch_block(self):
        self.task.correct = self.task.block_length
        initial_block_Left = self.task.block_Left
        self.task.block_sampler()
        self.assertEqual(self.task.correct, 0)
        self.assertNotEqual(self.task.block_Left, initial_block_Left)

    def test_block_sampler_no_switch_block(self):
        self.task.correct = 0
        initial_block_Left = self.task.block_Left
        self.task.block_sampler()
        self.assertEqual(self.task.correct, 0)
        self.assertEqual(self.task.block_Left, initial_block_Left)
            
    

if __name__ == '__main__':
    unittest.main()
    
