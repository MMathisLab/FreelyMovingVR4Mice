"""
Detection task with velocity threshold to initiate the trials.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

import pathlib
import time as time

from mouse_task.task_active_sensing import ActiveSensingTask


config_name = pathlib.Path("task_config.json")
current_dir = pathlib.Path(__file__).parent
config_path = current_dir.joinpath(config_name)  # default class constructor input



class DetectionWithVelocityThresholdTask(ActiveSensingTask):

    """
    Detection task with velocity threshold to initiate the trials.
    """

    def __init__(
        self,
        teensy,
        monitor=None,
        write_video=False,
        fps=60.0,
        session_label=["ar_detection_velthr"],
        epochs=[250],
        epoch_labels=["single_teardrop"],
        config_file_path=config_path,
        reward_size=100,
        cropped_image=[0, 530, 0, 510],
        unity_arena_size=[-9, 9, -10, -2],
        r_report_box=[5, 10, -4, -2],
        l_report_box=[-10, -5, -4, -2],
        start_box=[-4, 4, -9, -5, 90],
        rotate_camera=90.0,
        prob_obj_on_left=0.5,
        prob_block_coherence = 0.5,
        mouse_report_delay=0.0,
        slit_size=[19.0, 20.0, 2],
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
        start_box_delay=0.25,
        velocity_threshold=10.0,
        distractor=0.0,
        grey_screen_active=0.0,
        target_distance=3,
        use_dlc=True,
    ):
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
