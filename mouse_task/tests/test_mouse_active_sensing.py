import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from mouse_task.task_active_sensing import ActiveSensingTask  # Ensure this path is correct
import numpy as np

class TestDetectionP1Randomization(unittest.TestCase):
    def setUp(self):
        """Setup the initial conditions for each test."""
        self.teensy = MagicMock()
        self.monitor = None
        self.write_video = False
        self.fps = 60.0
        self.session_label = ["test"]
        self.epochs = [250]
        self.epoch_labels = ["single_teardrop"]
        self.config_file_path = Path("../task_config.json")
        self.reward_size = 100
        self.cropped_image = [0, 530, 0, 510]
        self.unity_arena_size = [-9, 9, -10, -2]
        self.R_report_box = [5, 10, -4, -2]
        self.L_report_box = [-10, -5, -4, -2]
        self.Start_box = [-4, 4, -9, -5, 90]
        self.rotate_camera = 90.0
        self.prob_obj_on_left = 0.5
        self.mouse_report_delay = 0.0
        self.slit_size = [4.0, 4.0, 1]
        self.slit_depth = 0.1
        self.target_selection = 6.0
        self.distractor_selection = 0.0
        self.occlusion_type = 0.0
        self.Camera_type = 1.0
        self.target_spread = 4.0
        self.target_rotation = 0
        self.target_size = 2.0
        self.target_height = 3.0
        self.block_length = 1.0
        self.start_box_delay = 0.1
        self.velocity_threshold = 20.0
        self.distractor = 0.0
        self.grey_screen_active = 0.0
        self.target_distance = 3.0
        self.use_dlc = False
        self.prob_block_coherence = 1.0

        self.mock_config = {
            "ar_env_unity_absolute_path": "mock_path"
        }

        with patch('mouse_task.task_active_sensing.process_config', return_value=self.mock_config):
            self.task = ActiveSensingTask(
                teensy=self.teensy,
                monitor=self.monitor,
                write_video=self.write_video,
                fps=self.fps,
                session_label=self.session_label,
                epochs=self.epochs,
                epoch_labels=self.epoch_labels,
                config_file_path=self.config_file_path,
                reward_size=self.reward_size,
                cropped_image=self.cropped_image,
                unity_arena_size=self.unity_arena_size,
                r_report_box=self.R_report_box,
                l_report_box=self.L_report_box,
                start_box=self.Start_box,
                rotate_camera=self.rotate_camera,
                prob_obj_on_left=self.prob_obj_on_left,
                prob_block_coherence=self.prob_block_coherence,
                mouse_report_delay=self.mouse_report_delay,
                slit_size=self.slit_size,
                slit_depth=self.slit_depth,
                target_selection=self.target_selection,
                distractor_selection=self.distractor_selection,
                occlusion_type=self.occlusion_type,
                camera_type=self.Camera_type,
                target_spread=self.target_spread,
                target_rotation=self.target_rotation,
                target_size=self.target_size,
                target_height=self.target_height,
                block_length=self.block_length,
                start_box_delay=self.start_box_delay,
                velocity_threshold=self.velocity_threshold,
                distractor=self.distractor,
                grey_screen_active=self.grey_screen_active,
                target_distance=self.target_distance,
                use_dlc=self.use_dlc,
            )
    
    def test_target_on_left(self):
        """test that target appears on the left"""
        self.task.prob_obj_on_left = 1.0
        self.task.random_target_location()
        self.assertEqual(self.task.object_on_left, 1.0)
    
    def test_target_on_right(self):
        """test that target appears on the right"""
        self.task.prob_obj_on_left = 0.0
        self.task.random_target_location()
        self.assertEqual(self.task.object_on_left, 0.0)
        
    def test_target_on_lr(self):
        """ test that target appears on either the left or the right"""
        self.task.prob_obj_on_left = 0.5
        self.task.random_target_location()
        self.assertIn(self.task.object_on_left, [0.0,1.0])
        
    def test_block_sampler_stay(self):
        """ test that if number correct is less than the block length we stay within the same block"""
        self.task.block_length = 2
        self.task.correct = 1
        self.task.block_Left = 0.0
        self.task.prob_block_coherence = 1.0
        self.task.block_sampler()
        self.assertEqual(self.task.object_on_left, 0.0)
         
        self.task.block_length = 2
        self.task.correct = 1
        self.task.block_Left = 1.0
        self.task.prob_block_coherence = 1.0
        self.task.block_sampler()
        self.assertEqual(self.task.object_on_left, 1.0)
         
        self.task.block_length = 2
        self.task.correct = 1
        self.task.block_Left = 1.0
        self.task.prob_block_coherence = 0.0
        self.task.block_sampler()
        self.assertEqual(self.task.object_on_left, 0.0)
         
         
    def test_block_switch(self):
        """ Tests that the block switches at the correct time.
        """
        # if block coherence is 1 and we are in a left block 
        # the next block should right and the target should appear on the right
        self.task.block_length = 2
        self.task.correct = 2
        self.task.block_Left = 1.0
        self.task.prob_block_coherence = 1.0
        self.task.block_sampler()
        self.assertEqual(self.task.object_on_left, 0.0)
        
        # if block coherence is 0 and we are in a left block 
        # the next block should left but the target should be on the right
        self.task.block_length = 2
        self.task.correct = 2
        self.task.block_Left = 1.0
        self.task.prob_block_coherence = 0.0
        self.task.block_sampler()
        self.assertEqual(self.task.object_on_left, 1.0)
        self.assertEqual(self.task.block_Left, 0.0)
        
    def test_slit_size_linspace(self):
        """ Test when slit_sizes_list has exactly 3 elements"""
        slit_sizes_list = [1.0, 10.0, 5]
        expected_result = np.linspace(1.0, 10.0, 5)
        result = self.task.get_slit_sizes(slit_sizes_list)
        np.testing.assert_array_equal(result, expected_result, 
                                      err_msg="Failed to generate linspace with exactly 3 elements.")
        
    def test_slit_size_custom(self):
        """ Test when slit_sizes_list has more than 3 elements """
        slit_sizes_list = [1.0, 2.0, 3.0, 4.0]
        expected_result = np.array(slit_sizes_list)
        result = self.task.get_slit_sizes(slit_sizes_list)
        np.testing.assert_array_equal(result, expected_result, 
                                      err_msg="Failed to return array when slit_sizes_list has more than 3 elements.")
        
    def test_slit_sizes_1_element(self):
        """Test when slit_sizes_list has 3 elements and check the array size"""
        slit_sizes_list = [0, 10, 1]
        expected_result = np.linspace(0, 10, 1)
        result = self.task.get_slit_sizes(slit_sizes_list)
        np.testing.assert_array_equal(result, expected_result, 
                                      err_msg="Failed to handle edge case with 3 elements but minimal linspace generation.")
        
        
    def test_slit_size_empty_list(self):
        """Test when slit_sizes_list is empty"""
        slit_sizes_list = []
        with self.assertRaises(ValueError):
            self.task.get_slit_sizes(slit_sizes_list)

    def test_slit_size_invalid_length(self):
        """Test when slit_sizes_list has less than 3 elements"""
        slit_sizes_list = [1.0, 2.0]
        with self.assertRaises(ValueError):
            self.task.get_slit_sizes(slit_sizes_list)

    def test_slit_size_invalid_type(self):
        """ Test when slit_sizes_list contains non-numeric types"""
        slit_sizes_list = [1.0, 2.0, 'a']
        with self.assertRaises(TypeError):
            self.task.get_slit_sizes(slit_sizes_list)





 

if __name__ == '__main__':
    unittest.main()
