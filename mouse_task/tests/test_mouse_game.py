import os
import unittest
import numpy as np
import pandas as pd

from pathlib import Path
from unittest.mock import MagicMock, patch
from mouse_task.task_active_sensing import ActiveSensingTask
from mouse_task.tests.test_helpers import (
    dict_to_data_frame,
    save_visual_observation,
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

        self.task.start()
        env = self.task.env

        # Only considering the first Behavior
        behavior_name = list(env.behavior_specs)[0]
        self.assertEqual(behavior_name, "My Behavior?team=0")
        spec = env.behavior_specs[behavior_name]

        # Check that agent has two observations: one vector and one visual
        self.assertEqual(len(spec.observation_specs), 2)

        # Double-check presence of visual observation
        # Visual observations have 3 dimensions: Height, Width and number of channels
        vis_obs = any(len(spec.shape) == 3 for spec in spec.observation_specs)
        self.assertTrue(vis_obs)

        # Check there are 4 continuous actions (i.e. x, y, head_angle and photodiode)
        self.assertTrue(spec.action_spec.continuous_size > 0)
        self.assertEqual(spec.action_spec.continuous_size, 4)

        parent_dir = os.path.dirname(os.path.abspath(__file__))
        in_path = os.path.join(parent_dir, "test_trajectories.pkl")
        trajectories_df = pd.read_pickle(in_path)

        for i, step in trajectories_df.iterrows():
            x, y = step["action_x"], step["action_y"]

            # Overriding the get_action()
            with patch(
                "mouse_task.task_active_sensing.ActiveSensingTask.get_action",
                return_value=np.array([x, y, 0, 0]).reshape((1, -1)),
            ):
                self.task.loop()

            # Save visual observation halfway through (if there is one)
            if i == len(trajectories_df) // 2:
                decision_steps, _ = env.get_steps(behavior_name)

                out_path = os.path.join(parent_dir, "test_visual_observation.png")
                vis_obs_shape, vec_obs_size = save_visual_observation(
                    i=i,
                    dec_steps=decision_steps,
                    obs_specs=spec.observation_specs,
                    out_path=out_path,
                )

                # Check correct size of visual observation
                self.assertEqual(vis_obs_shape, (1, 3, 256, 256))

                # Check correct size of vector observation
                self.assertEqual(vec_obs_size, 13)

        # Collect data
        data = dict_to_data_frame(self.task.get_data())

        # Quit task
        self.task.stop()

        # Check that there are no duplicate steps
        self.assertTrue(data["step"].is_unique)

        # Check that are no missing values in the data
        self.assertEqual(data.isna().sum().sum(), 0)

        data = data.apply(pd.to_numeric, errors="coerce")

        # Check that actions sent correspond to agent's position (on same step)
        self.assertTrue(np.allclose(data["action_x"].to_numpy(), data["x"].to_numpy()))
        self.assertTrue(np.allclose(data["action_y"].to_numpy(), data["y"].to_numpy()))

        # Check that agent cannot be in both boxes at the same time
        self.assertTrue((data["mouseInLeft_box"] * data["mouseInRight_box"]).sum() == 0)

        # Check that there are no more rewards than there are episodes
        self.assertTrue(data["reward"].sum() <= data["episode"].max())

        # Check that the number of terminal steps corresponds to number of episodes
        data_df = data.groupby("episode").last()
        self.assertTrue(data_df["terminal"].sum() + 1 == data_df.index.max())

        # Check that rewards were correctly assigned
        data_df = data[data.ITI == 1].groupby("episode").first()
        data_df["spawner_green_on_right"] = (
            data_df["spawner_green_on_left"] == 0
        ).astype(float)
        self.assertTrue(
            all(
                data_df["reward"]
                == data_df["spawner_green_on_left"] * data_df["mouseInLeft_box"]
                + data_df["spawner_green_on_right"] * data_df["mouseInRight_box"]
            )
        )


if __name__ == "__main__":
    unittest.main()
