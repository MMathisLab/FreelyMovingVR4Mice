"""
Test task without velocity threshold to initiate the trials.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

import pathlib
import pygame
import time as time
import numpy as np

from mouse_task.task_active_sensing import ActiveSensingTask
from test_helpers import dict_to_data_frame

# from mouse_task.dlc_utils.fake_processors.test_socket_send import MyProcessor_socket


config_name = pathlib.Path("task_config.json")
current_dir = pathlib.Path(__file__).parent
config_path = current_dir.joinpath(config_name)  # default class constructor input


class TestTask(ActiveSensingTask):
    """
    Test task without velocity threshold to initiate the trials.
    """

    def __init__(
        self,
        teensy,
        monitor=None,
        write_video=False,
        fps=60.0,
        session_label=["task_test"],
        epochs=[250],
        epoch_labels=["test"],
        config_file_path=config_path,
        reward_size=100,
        cropped_image=[0, 530, 0, 510],
        unity_arena_size=[-9, 9, -10, -2],
        r_report_box=[5, 10, -4, -2],
        l_report_box=[-10, -5, -4, -2],
        start_box=[-4, 4, -9, -5, 90],
        rotate_camera=90.0,
        prob_obj_on_left=0.5,
        prob_block_coherence=0.5,
        mouse_report_delay=0.0,
        slit_size=[4.0, 4.0, 1],
        slit_depth=0.2,
        target_selection=6.0,
        distractor_selection=4.0,
        occlusion_type=0.0,
        camera_type=1.0,
        target_spread=4.0,
        target_rotation=0,
        target_size=2.0,
        target_height=3.0,
        block_length=1.0,
        start_box_delay=0.1,
        velocity_threshold=20.0,
        distractor=0.0,
        grey_screen_active=0.0,
        target_distance=3,
        use_dlc=True,
        test_data=None,
    ):
        if test_data is not None:
            self.test_data = dict_to_data_frame(test_data)
        else:
            self.test_data = None
        self.pos_idx = 0
        super().__init__(
            teensy=teensy,
            monitor=monitor,
            write_video=write_video,
            fps=fps,
            session_label=session_label,
            epochs=epochs,
            epoch_labels=epoch_labels,
            config_file_path=config_file_path,
            reward_size=reward_size,
            cropped_image=cropped_image,
            unity_arena_size=unity_arena_size,
            r_report_box=r_report_box,
            l_report_box=l_report_box,
            start_box=start_box,
            rotate_camera=rotate_camera,
            prob_obj_on_left=prob_obj_on_left,
            prob_block_coherence=prob_block_coherence,
            mouse_report_delay=mouse_report_delay,
            slit_size=slit_size,
            slit_depth=slit_depth,
            target_selection=target_selection,
            distractor_selection=distractor_selection,
            occlusion_type=occlusion_type,
            camera_type=camera_type,
            target_spread=target_spread,
            target_rotation=target_rotation,
            target_size=target_size,
            target_height=target_height,
            block_length=block_length,
            start_box_delay=start_box_delay,
            velocity_threshold=velocity_threshold,
            distractor=distractor,
            grey_screen_active=grey_screen_active,
            target_distance=target_distance,
            use_dlc=use_dlc,
        )

    def _get_dlc_on_frame(self):
        if self.test_trajectory is not None:
            x, z = (
                self.test_data.iloc[self.pos_idx].x,
                self.test_data.iloc[self.pos_idx].y,
            )
            self.pos_idx += 1

            self.degrees = 0
            output = np.array([x, z, self.degrees, 0])
            return output.reshape((1, -1))
        else:
            raise ValueError("No test data provided.")


# class TestSocket(MyProcessor_socket):
#     def __init__(
#         self,
#         save_file_path="./",
#         test_trajectory=None,
#     ):
#         super().__init__(save_file_path=save_file_path)
#         self.test_trajectory = test_trajectory
#         self.pos_idx = 0

#     def process(self):
#         self.curr_time = time.time()
#         self.get_curr_signal()
#         print(self.curr_signal)
#         if self.test_trajectory is not None:
#             self.conn.send(
#                 [
#                     self.curr_time,
#                     self.test_trajectory[self.pos_idx][0],
#                     self.test_trajectory[self.pos_idx][1],
#                     0,
#                     0,
#                     self.curr_signal,
#                 ]
#             )
#             self.pos_idx += 1
#         else:
#             raise ValueError("No test trajectory provided.")

#         self.signal.append(self.curr_signal)
#         self.step.append(self.curr_step)
#         self.time_stamp.append(self.curr_time)
#         self.curr_step = self.curr_step + 1

#         # self.time_stamp.append(time.time)
#         ## Sending data at 50Hz ##
#         time.sleep(1 / 50)
#         # print(self.st - time.time())
