import unittest
import time
import pygame
import tkinter as tk
import numpy as np
import pandas as pd
from tkinter import filedialog
from pathlib import Path
from unittest.mock import MagicMock, patch
from mouse_task.tests.test_task_class import TestTask


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
        self.test_trajectory = []
        self.previous_pos_idx = 0

        root = tk.Tk()
        root.withdraw()

        folder_path = filedialog.askopenfilename()
        self.config = {"ar_env_unity_absolute_path": folder_path}

        with patch(
            "mouse_task.task_active_sensing.process_config",
            return_value=self.config,
        ):
            self.task = TestTask(
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
                test_trajectory=self.test_trajectory,
                previous_pos_idx=self.previous_pos_idx,
            )

    # def test_manual_trajectories(self):
    #     pygame.init()
    #     screen = pygame.display.set_mode((530, 510))

    #     trajectory = []

    #     # Initialize Unity environment
    #     self.task.start()
    #     self.task.reset_environment()

    #     # Main loop
    #     running = True
    #     while running:
    #         for event in pygame.event.get():
    #             if event.type == pygame.QUIT:
    #                 running = False
    #             elif event.type == pygame.KEYDOWN:
    #                 if event.key == pygame.K_ESCAPE:  # Quit on pressing Escape key
    #                     running = False

    #         # Get mouse position within the arena bounds
    #         mouse_pos = pygame.mouse.get_pos()

    #         # Ensure it is within bounds
    #         x = max(0, min(mouse_pos[0], 530))
    #         z = max(0, min(mouse_pos[1], 510))

    #         # Fill the screen with a background color
    #         screen.fill((0, 0, 0))
    #         pygame.draw.circle(screen, (255, 0, 0), (x, z), 5)

    #         x = np.interp(
    #             x,
    #             [self.cropped_image[0], self.cropped_image[1]],
    #             [self.unity_arena_size[0], self.unity_arena_size[1]],
    #         )
    #         z = np.interp(
    #             510 - z,
    #             [self.cropped_image[2], self.cropped_image[3]],
    #             [self.unity_arena_size[2], self.unity_arena_size[3]],
    #         )

    #         self.task.loop(override_action=True, action=np.array([x, z, 0, 0]))
    #         trajectory.append((x, z))

    #         # Update display
    #         pygame.display.flip()
    #         time.sleep(0.02)

    #     pygame.quit()
    #     self.task.stop()

    #     np.save(arr=trajectory, file="./trajectory.npy", allow_pickle=True)

    def test_stored_trajectories(self):

        position_coordinates = []
        self.test_trajectory = np.load("./trajectory.npy")

        self.task.start()

        for pos in self.test_trajectory:
            self.task.loop(
                override_action=True, action=np.array([pos[0], pos[1], 0, 0])
            )
            position_coordinates.append(self.task.get_info()["position"])

        data = self.task.get_data()
        self.task.stop()

        import matplotlib.pyplot as plt

        plt.plot(position_coordinates)
        plt.show()


if __name__ == "__main__":
    unittest.main()
