# Description: Test the active sensing task by manually controlling the position of the agent in the Unity game through a pygame window interface.
# The manually generated trajectories are saved to a pickle file for later testing.

import os
import unittest
import pygame
import numpy as np
import pickle as pkl

from pathlib import Path
from unittest.mock import MagicMock, patch
from mouse_task.task_active_sensing import ActiveSensingTask
from mouse_task.tests.test_helpers import (
    plot_trajectories,
    compute_trigger_areas_coordinates,
    dict_to_data_frame,
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

    def test_manual(self):
        """Manually controlling the position in the unity game through mouse position in pygame window. Allows
        for manual testing of the game as well as generating trajectories data for later tesing.
        Data is saved to a pickle file (test_trajectories.pkl).
        """

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

        rtolerance = 0.5  # 0.5% error accepted
        self.assertTrue(
            np.allclose(
                np.array([x_rects_lower, y_rects_lower, widths, heights]),
                [
                    [147.222, 0.0, 412.222],  # x_rects_lower
                    [191.25, 0.0, 0.0],  # y_rects_lower
                    [235.556, 117.778, 117.778],  # widths
                    [255.0, 127.5, 127.5],  # heights
                ],
                atol=0,
                rtol=rtolerance,
            )
        )

        # Initialize Unity environment
        self.task.start()

        # Tracking properties
        dot_x, dot_y = window_width // 2, window_height // 2  # Start at center
        speed = 12  # Pixels per frame
        tracking = False  # Whether the dot is tracking the cursor

        # Main loop
        running = True
        is_ITI = False
        clock = pygame.time.Clock()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:  # Quit on pressing "ESC" key
                        if is_ITI:  # Can quit only when in ITI
                            running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left mouse button
                        # Toggle tracking state
                        tracking = not tracking

            if tracking:
                # Get current mouse position
                mouse_x, mouse_y = pygame.mouse.get_pos()

                # Calculate movement vector
                dx = mouse_x - dot_x
                dy = mouse_y - dot_y
                distance = (dx**2 + dy**2) ** 0.5  # Euclidean distance

                # Move only if the cursor is not already at the dot's position
                if distance > 1:
                    # Normalize the direction vector and scale by speed
                    dot_x += (dx / distance) * min(speed, distance)
                    dot_y += (dy / distance) * min(speed, distance)

            x, y = dot_x, dot_y

            # Fill the screen with a background color
            screen.fill(BLACK)

            # Draw the mouse position
            pygame.draw.circle(screen, RED, (x, y), 5)

            # Draw the trigger areas using list comprehension
            [
                pygame.draw.rect(screen, GREEN, (xrl, yrl, ws, hs))
                for xrl, yrl, ws, hs in zip(
                    x_rects_lower, y_rects_lower, widths, heights
                )
            ]

            # Interpolate cursor (digital) coordinates on pygame screen to unity arena coordinates
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

            # Overriding the get_action()
            with patch(
                "mouse_task.task_active_sensing.ActiveSensingTask.get_action",
                return_value=np.array([x, y, 0, 0]).reshape((1, -1)),
            ):
                self.task.loop()

            # Get if mouse is in ITI
            is_ITI = True if self.task.get_data()["state"][-1][4] == 1.0 else False

            # Update display
            pygame.display.flip()

            # Limit FPS to 100
            clock.tick(100)
        pygame.quit()

        data = format_data(self.task.get_data())
        self.task.stop()

        plot_trajectories(
            data,
            arena=self.unity_arena_size,
            Lbox=self.l_report_box,
            Rbox=self.r_report_box,
            Sbox=self.start_box,
        )

        # Store trajectory coordinates as .npy
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(parent_dir, "test_trajectories.npy")
        np.save(
            out_path,
            np.vstack(
                (
                    data["action_x"],
                    data["action_y"],
                )
            ).T,
        )


if __name__ == "__main__":
    unittest.main()
