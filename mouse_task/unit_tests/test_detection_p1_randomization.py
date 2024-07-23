import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from pathlib import Path
from mouse_task.mouse_VD_detection_p1  import Detection_p1   # Assuming your script is named detection_p1.py

class TestDetectionP1Randomization(unittest.TestCase):

    def setUp(self):
        self.teensy = MagicMock()
        self.monitor = None
        self.write_video = False
        self.fps = 60.0
        self.session_label = ["AR_VD_detection_p1"]
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
        self.Prob_Obj_on_Left = 0.5
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

        self.detection_p1 = Detection_p1(
            self.teensy,
            self.monitor,
            self.write_video,
            self.fps,
            self.session_label,
            self.epochs,
            self.epoch_labels,
            self.config_file_path,
            self.reward_size,
            self.cropped_image,
            self.unity_arena_size,
            self.R_report_box,
            self.L_report_box,
            self.Start_box,
            self.rotate_camera,
            self.Prob_Obj_on_Left,
            self.mouse_report_delay,
            self.slit_size,
            self.slit_depth,
            self.target_selection,
            self.distractor_selection,
            self.occlusion_type,
            self.Camera_type,
            self.target_spread,
            self.target_rotation,
            self.target_size,
            self.target_height,
            self.block_length,
            self.start_box_delay,
            self.velocity_threshold,
            self.distractor,
            self.grey_screen_active,
            self.target_distance,
            self.use_dlc
        )

    def test_random_target_location(self):
        # Mock the np.random.choice to ensure repeatability
        with patch('numpy.random.choice', return_value=0.0):
            self.detection_p1.random_target_location()
            self.assertEqual(self.detection_p1.Object_on_left, 0.0)
        
        with patch('numpy.random.choice', return_value=1.0):
            self.detection_p1.random_target_location()
            self.assertEqual(self.detection_p1.Object_on_left, 1.0)

    def test_block_sampler(self):
        # Test block sampler functionality
        self.detection_p1.block_length = 2  # Ensure block length is greater than 1
        self.detection_p1.correct = 1
        self.detection_p1.block_Left = 0.0

        with patch('numpy.random.choice', return_value=1.0):
            self.detection_p1.block_sampler()
            self.assertEqual(self.detection_p1.Object_on_left, 1.0)

        self.detection_p1.correct = 2  # Simulate correct trials reaching block length
        self.detection_p1.block_sampler()
        self.assertEqual(self.detection_p1.correct, 0)
        self.assertEqual(self.detection_p1.block_Left, 1.0)

        with patch('numpy.random.choice', return_value=0.0):
            self.detection_p1.block_sampler()
            self.assertEqual(self.detection_p1.Object_on_left, 0.0)


if __name__ == '__main__':
    unittest.main()