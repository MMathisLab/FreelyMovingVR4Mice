import unittest
import time
import pygame
import pickle as pkl
import tkinter as tk
import numpy as np
import pandas as pd

from tkinter import filedialog
from pathlib import Path
from unittest.mock import MagicMock, patch
from mouse_task.task_active_sensing import ActiveSensingTask
from mouse_task.tests.test_helpers import (
    plot_trajectories,
    compute_trigger_areas_coordinates,
    dict_to_data_frame,
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
        self.config_file_path = Path("./test_config.json")
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

    def test_manual_trajectories(self):

        window_width = self.cropped_image[1]
        window_height = self.cropped_image[3]

        RED = (255, 0, 0)
        GREEN = (0, 255, 0)
        BLACK = (0, 0, 0)

        pygame.init()
        screen = pygame.display.set_mode((window_width, window_height))

        x_rects_lower, y_rects_lower, widths, heights = (
            compute_trigger_areas_coordinates(
                self.unity_arena_size,
                self.cropped_image,
                self.start_box,
                self.r_report_box,
                self.l_report_box,
            )
        )

        print("------->", x_rects_lower, y_rects_lower, widths, heights)

        # Initialize Unity environment
        self.task.start()

        # Main loop
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:  # Quit on pressing Escape key
                        running = False

            # Get mouse position within the arena bounds
            mouse_pos = pygame.mouse.get_pos()

            # Ensure it is within bounds
            x = max(0, min(mouse_pos[0], window_width))
            y = max(0, min(mouse_pos[1], window_height))

            # Fill the screen with a background color
            screen.fill(BLACK)

            pygame.draw.circle(screen, RED, (x, y), 5)
            [
                pygame.draw.rect(screen, GREEN, (x, y, w, h))
                for x, y, w, h in zip(x_rects_lower, y_rects_lower, widths, heights)
            ]

            x = np.interp(
                x,
                [self.cropped_image[0], self.cropped_image[1]],
                [self.unity_arena_size[0], self.unity_arena_size[1]],
            )
            y = np.interp(
                y,
                [self.cropped_image[2], self.cropped_image[3]],
                [self.unity_arena_size[3], self.unity_arena_size[2]],
            )

            with patch(
                "mouse_task.task_active_sensing.ActiveSensingTask.get_action",
                return_value=np.array([x, y, 0, 0]).reshape((1, -1)),
            ):
                self.task.loop()

            # Update display
            pygame.display.flip()
            time.sleep(1 / 50)

        pygame.quit()

        data = self.task.get_data()
        self.task.stop()

        with open("./data.pkl", "wb") as handle:
            pkl.dump(data, handle, protocol=pkl.HIGHEST_PROTOCOL)

        plot_trajectories(data)

    def test_data_integrity(self):
        with open("./data.pkl", "rb") as handle:
            data = dict_to_data_frame(pkl.load(handle))

        # checking that there are no duplicate steps
        self.assertTrue(data["step"].is_unique)

        # checking that are no missing values in the data
        self.assertEqual(data.isna().sum().sum(), 0)

        data = data.apply(pd.to_numeric, errors="coerce")

        # checking that actions sent correspond to agent's position (on same step)
        self.assertTrue(np.allclose(data["action_x"].to_numpy(), data["x"].to_numpy()))
        self.assertTrue(np.allclose(data["action_y"].to_numpy(), data["y"].to_numpy()))

        # checking that agent cannot be in both boxes at the same time
        self.assertTrue((data["mouseInLeft_box"] * data["mouseInRight_box"]).sum() == 0)

        # checking that there are no more rewards than there are episodes
        self.assertTrue(data["reward"].sum() <= data["episode"].max())

        # checking that the number of terminal steps corresponds to number of episodes
        data_df = data.groupby("episode").last()
        self.assertTrue(data_df["terminal"].sum() + 1 == data_df.index.max())

        # checking that rewards were correctly assigned
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
    import os, json

    # saving game executable location for future use
    if not os.path.exists("./test_config.json"):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(title="Select game executable")

        with open("./test_config.json", "w") as f:
            json.dump({"ar_env_unity_absolute_path": file_path}, f)

        root.destroy()
    unittest.main()
