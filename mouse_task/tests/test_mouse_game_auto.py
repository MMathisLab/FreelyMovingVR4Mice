# Description: Test the active sensing task by using artificial trajectories (generated through test_mouse_active_sensing_manual.py) to control the position of
# the agent in the Unity game. The trajectories are loaded from a pickle file. At the end of the virtual session, the saved data undergoes testing to ensure
# data integrity and coherence.

import os
import pickle
import unittest
import numpy as np
import pandas as pd

from pathlib import Path
from unittest.mock import MagicMock, patch
from mouse_task.task_active_sensing import ActiveSensingTask
from mouse_task.tests.test_helpers import (
    format_data,
    select_executable,
)


class TestPositionCoordinates(unittest.TestCase):

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
        self.r_report_box = [5, 10, -4, -2]
        self.l_report_box = [-10, -5, -4, -2]
        self.start_box = [-4, 4, -9, -5, 90]
        self.rotate_camera = 90.0
        self.prob_obj_on_left = 0.5
        self.mouse_report_delay = 0.0
        self.slit_size = [4.0, 4.0, 1]
        self.slit_depth = 0.1
        self.target_selection = 6.0
        self.distractor_selection = 0.0
        self.occlusion_type = 0.0
        self.camera_type = 1.0
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

        game_path = select_executable()
        self.config = {"ar_env_unity_absolute_path": game_path}

        with patch(
            "mouse_task.task_active_sensing.process_config",
            return_value=self.config,
        ):
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
                r_report_box=self.r_report_box,
                l_report_box=self.l_report_box,
                start_box=self.start_box,
                rotate_camera=self.rotate_camera,
                prob_obj_on_left=self.prob_obj_on_left,
                prob_block_coherence=self.prob_block_coherence,
                mouse_report_delay=self.mouse_report_delay,
                slit_size=self.slit_size,
                slit_depth=self.slit_depth,
                target_selection=self.target_selection,
                distractor_selection=self.distractor_selection,
                occlusion_type=self.occlusion_type,
                camera_type=self.camera_type,
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

    def test_game(self):
        """Manually runs the game loop bypassing the get_action() method to control agent position"""

        self.task.start()
        env = self.task.env

        # Only considering the first Behavior
        behavior_name = list(env.behavior_specs)[0]
        self.assertEqual(
            behavior_name,
            "My Behavior?team=0",
        )
        spec = env.behavior_specs[behavior_name]

        # Check that agent has two observation
        # First is visual observation, second is vector observation
        self.assertEqual(
            len(spec.observation_specs),
            2,
        )

        vis_obs_ind = 0
        vec_obs_ind = 1

        # Verify the shape of the visual observation
        self.assertEqual(
            len(spec.observation_specs[vis_obs_ind].shape),
            3,
        )
        
        # Check the size of the vector observation
        self.assertEqual(
            spec.observation_specs[vec_obs_ind].shape,
            (13,),
        )

        # Check the type of the observation (i.e. VectorSensor)
        self.assertTrue("VectorSensor" in spec.observation_specs[vec_obs_ind].name)

        # Check there are 4 continuous actions (i.e. x, y, head_angle and photodiode)
        self.assertGreater(spec.action_spec.continuous_size, 0)
        self.assertEqual(spec.action_spec.continuous_size, 4)

        parent_dir = os.path.dirname(os.path.abspath(__file__))
        in_path = os.path.join(parent_dir, "test_trajectories.npy")
        trajectories = np.load(in_path)

        for x, y in trajectories:
            # Overriding the get_action()
            with patch(
                "mouse_task.task_active_sensing.ActiveSensingTask.get_action",
                return_value=np.array([x, y, 0, 0]).reshape((1, -1)),
            ):
                self.task.loop()

        # Collect data
        data = format_data(self.task.get_data())

        # Quit task
        self.task.stop()

        # Check that there are no duplicate steps
        self.assertEqual(
            len(data["step"]),
            len(np.unique(data["step"])),
        )

        # Check that are no missing values in the data
        self.assertTrue(np.all([not np.isnan(data[key]).any() for key in data.keys()]))

        # Check that actions sent correspond to agent's position (on subsequent steps)
        # i.e. action_x and action_y will get sent on step n and x and y will be updated on step n+1
        self.assertTrue(np.allclose(data["action_x"], data["x"]))
        self.assertTrue(np.allclose(data["action_y"], data["y"]))

        # Check that agent cannot be in both boxes at the same time
        self.assertEqual(
            (data["mouseInLeft_box"] * data["mouseInRight_box"]).sum(),
            0,
        )

        # Check that there are no more rewards than there are episodes
        self.assertLessEqual(
            data["reward"].sum(),
            data["episode"].max(),
        )

        # Check that the number of terminal steps corresponds to number of episodes - 1
        last_ep_step_idx = [
            np.where(data["episode"] == ep)[0][-1] for ep in np.unique(data["episode"])
        ]
        self.assertEqual(
            sum([data["terminal"][idx] for idx in last_ep_step_idx]),
            data["episode"].max() - 1,
        )

        # Check that rewards were correctly assigned
        ITI_idx = np.where(data["ITI"] == 1)[0]  # indices where ITI is 1
        gaps = np.where(np.diff(ITI_idx) > 1)[0]  # gaps in ITI steps (-> new ep.)
        report_idx = np.concatenate(
            [
                [ITI_idx[0]],  # included by default
                ITI_idx[gaps + 1],
            ]
        ).astype(np.int64)
        rewards = [
            (
                data["mouseInLeft_box"][idx] == data["reward"][idx]
                if data["spawner_green_on_left"][idx]
                else data["mouseInRight_box"][idx] == data["reward"][idx]
            )
            for idx in report_idx
        ]
        self.assertTrue(np.all(rewards))


if __name__ == "__main__":
    unittest.main()
