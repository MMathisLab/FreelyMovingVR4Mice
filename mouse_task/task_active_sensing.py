"""
This module contains the `ActiveSensingTask` class for Augmented Reality Visual discrimination tasks.
It uses DLClive for position tracking and Unity for visual flow. This class is designed to be integrated
with the teensyexp module, inheriting from `UnityTask` and `GuiTask` classes for dynamic task loading via GUI.

Note: Ensure the model path is defined in the local `task_config.json` file.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"

import pathlib
import numpy as np
import time

from mouse_task.helpers import process_config

from teensyexp.tasks_abc.unity_task import UnityTask
from teensyexp.tasks_abc.dlc_deque_socket import DLCClient
from teensyexp.teensy import Teensy
from mouse_task.kfilter import OneEuroFilter

from typing import List, Optional


class ActiveSensingTask(UnityTask):
    """
    Active Sensing Task Class

    This class represents a visual discrimination task for mice using augmented reality.
    It inherits from UnityTask and GuiTask from the `teensyexp` module.

    Attributes:
        teensy (Teensy): Instance of Teensy class to control the microcontroller.
        monitor (bool): Monitor on which to display the game. Set to `None`.
        write_video (bool): Flag to indicate if video of visual observations should be written.
            Caution: if possible, games should not include visual observations, as this really
            slows down the speed of the game.
        fps (float): Frames per second at which to write the video of visual observations.
        session_label (List[str]): Label for the session.
        epochs (int): Number of trials before parameters should be changed.
            The task will end at the end of the last epoch is the game trial based (1) or
            time based (0).
        epoch_labels (List[str]): Indicates of the game is trial-based ([1]), or time-based ([0]).
        config_file_path (pathlib.Path): Path to the configuration JSON file.
        reward_size (int): Size of the reward.
        cropped_image (List[int]): Dimensions of the cropped image.
        unity_arena_size (List[int]): Dimensions of the Unity arena.
        r_report_box (List[int]): Dimensions of the right water report box.
        l_report_box (List[int]): Dimensions of the left water report box.
        start_box (List[int]): Dimensions of the start box.
        rotate_camera (float): Camera rotation angle.
        prob_obj_on_left (float): Probability of the object appearing on the left.
        mouse_report_delay (float): Delay for the mouse report.
        slit_size (List[int]): Size of the slit between occluders.
        slit_depth (float): Depth of the slit based on depth of the occluders.
        target_selection (float): Target selection parameter. Defines the identity
            of the target object displayed.
        distractor_selection (float): Distractor selection parameter. Defines the identity
            of the distractor object displayed.
        occlusion_type (float): Type of occlusion. Set to 0 in the init.
        camera_type (float): Type of camera.
        target_spread (float): Spread of the target object.
        target_rotation (float): Rotation of the target object.
        target_size (float): Size of the target object.
        target_height (float): Height of the target object.
        block_length (float): Length of the trials block if utilized for the training.
        start_box_delay (float): Time that the mouse needs to stay in the start box to launch
            the trial.
        velocity_threshold (float): Threshold for velocity for to launch the trial.
        distractor (float): Indicate if the distractor should be display (1) or not (0).
        grey_screen_active (float): Flag to indicate if grey screen is active.
        target_distance (float): Distance of the target.
        use_dlc (bool): Flag to indicate if DLC is used.
    """

    def __init__(
        self,
        teensy: Teensy,
        session_label: List[str],
        config_file_path: pathlib.Path,
        monitor: Optional[bool],
        write_video: bool,
        fps: float,
        epochs: int,
        epoch_labels: List[str],
        reward_size: int,
        cropped_image: List[int],
        unity_arena_size: List[int],
        r_report_box: List[int],
        l_report_box: List[int],
        start_box: List[int],
        rotate_camera: float,
        prob_obj_on_left: float,
        prob_block_coherence: float,
        mouse_report_delay: float,
        slit_size: List[int],
        slit_depth: float,
        target_selection: float,
        distractor_selection: float,
        occlusion_type: float,
        camera_type: float,
        target_spread: float,
        target_rotation: float,
        target_size: float,
        target_height: float,
        block_length: float,
        start_box_delay: float,
        velocity_threshold: float,
        distractor: float,
        grey_screen_active: float,
        target_distance: float,
        use_dlc: bool,
    ):

        # Initialized in init_DLC_live()
        self.t_count = None
        self.filt = None
        self.params = None
        if use_dlc == True:
            self.address = ("localhost", 6000)
            self.dlcClient = DLCClient(address=self.address)
        self.t_count = 0
        self.degrees = 0
        self.correct = 0
        self.session_label = session_label
        self.grey_screen_active = grey_screen_active

        config_dict = process_config(config_file_path)

        if config_dict is None:
            # Error messages are showed on process_config() function level
            print("config not found!")
            return

        env_path = config_dict["ar_env_unity_absolute_path"]

        super().__init__(
            teensy=teensy,
            env=env_path,
            monitor=monitor,
            write_video=write_video,
            fps=fps,
            epochs=epochs,
            epoch_trials=True,
        )

        # Game parameters
        self.cropped_image = cropped_image
        self.unity_arena_size = unity_arena_size
        self.rotate_camera = rotate_camera
        self.r_report_box = r_report_box
        self.l_report_box = l_report_box
        self.start_box = start_box

        self.start_box_delay = start_box_delay
        self.velocity_threshold = velocity_threshold

        self.previous = np.array(
            [
                9,
                -5,
                0,
                0,
            ],
            dtype=np.float16,
        ).reshape(1, -1)

        # Game trial parameters
        # add to class and enforce list structure
        self.reward_size = self.as_list(reward_size)
        self.slit_size = slit_size
        slit_sizes_list = self.as_list(slit_size)
        self.slit_sizes = np.linspace(
            slit_sizes_list[0], slit_sizes_list[1], int(slit_sizes_list[2])
        )

        self.slit_depth = self.as_list(slit_depth)
        self.epoch_labels = self.as_list(epoch_labels)
        self.target_spread = self.as_list(target_spread)
        self.target_height = self.as_list(target_height)
        self.mouse_report_delay = self.as_list(mouse_report_delay)
        self.target_rotation = self.as_list(target_rotation)

        self.prob_obj_on_left = prob_obj_on_left
        self.prob_block_coherence = prob_block_coherence

        self.block_Left = np.random.choice([0.0, 1.0], p=[0.5, 0.5])
        print("block_left", self.block_Left)

        if self.block_Left == 0.0:
            print("Right block")
            self.object_on_left = np.random.choice(
                [0.0, 1.0], p=[self.prob_block_coherence, 1 - self.prob_block_coherence]
            )

        else:
            print("Left block")
            self.object_on_left = np.random.choice(
                [0.0, 1.0], p=[1 - self.prob_block_coherence, self.prob_block_coherence]
            )

        print("object_on_left: ", self.object_on_left)

        self.block_length = block_length
        self.distractor = distractor
        self.target_size = target_size
        self.target_selection = self.as_list(target_selection)
        self.distractor_selection = self.as_list(distractor_selection)
        self.occlusion_type = self.as_list(occlusion_type)
        self.camera_type = camera_type
        self.target_distance = self.as_list(target_distance)
        self.use_dlc = use_dlc

        self.n_rewards = 0

        # Create empty vectors to keep track of game parameters per trial
        self.trial_epoch_labels = []
        self.trial_reward_size = []
        self.trial_prob_obj_on_left = []
        self.trial_slit_size = []
        self.trial_slit_depth = []
        self.trial_target_spread = []
        self.trial_target_height = []
        self.trial_target_selection = []
        self.trial_distractor_selection = []
        self.trial_occlusion_type = []
        self.trial_target_distance = []
        self.trial_target_rotation = []

        self.dlc_read_time = []
        self.dlc_x = []
        self.dlc_y = []
        self.dlc_heading = []
        self.dlc_time_step = []
        self.trial_mouse_report_delay = []

        # self.set_channel()
        # self.reset_environment()

    def _get_dlc_on_frame(self):
        """
        Runs DLC on every frame.

        It is used in ``get_action()``, called by teensyexp's module Agent.
        This is run on every frame after the dlc processor is initialized.
        """

        # run DLC on every frame to be given as input to the agent
        this_read = self.dlcClient.read()

        if this_read != None:
            self.params = np.array(this_read["vals"][1:])
            if self.t_count == 0:
                self.filt = OneEuroFilter(
                    t0=self.t_count,
                    x0=np.array(self.params),
                    beta=0.01,
                    min_cutoff=0.01,
                )
            else:
                self.params = self.filt(self.t_count, np.array(self.params))
            self.t_count = self.t_count + 1
            x = self.params[0]
            z = self.params[1]
            head_angle = self.params[2]
            photodiode_intensity = np.array(this_read["vals"])[-1]
            self.dlc_x.append(x)
            self.dlc_y.append(z)
            self.dlc_heading.append(head_angle)
            self.dlc_read_time.append(this_read["time"])

            # interp mouse pixel space into arena space
            x = np.interp(
                x,
                [self.cropped_image[0], self.cropped_image[1]],
                [self.unity_arena_size[0], self.unity_arena_size[1]],
            )
            z = np.interp(
                z,
                [self.cropped_image[2], self.cropped_image[3]],
                [self.unity_arena_size[2], self.unity_arena_size[3]],
            )
            self.degrees = (head_angle - (self.rotate_camera)) % 360
            output = np.array([x, z, self.degrees, photodiode_intensity])
            self.previous = output
        else:
            # print("missed dlc frame")
            time.sleep(0)
            output = self.previous
        return output.reshape((1, -1))

    def set_channel(self):
        """
        Send parameters to unity when the game is reset i.e. at the beginning of each trial

        Method inherited from task parent class interface.

        Note: can use this function to save data to the .pickle file and send parameters to unity
        """

        if self.block_length == 1:
            self.random_target_location()
        if self.block_length > 1:
            self.block_sampler()

        this_prob_obj_left = self.prob_obj_on_left
        print("prob left", this_prob_obj_left)
        this_slit_size = np.random.choice(self.slit_sizes)
        print("slit_size", this_slit_size)
        this_slit_depth = self.get_epoch_value("slit_depth")
        this_target_spread = self.get_epoch_value("target_spread")
        this_target_height = self.get_epoch_value("target_height")
        this_mouse_report_delay = self.get_epoch_value("mouse_report_delay")
        this_target_selection = self.get_epoch_value("target_selection")
        this_distractor_selection = self.get_epoch_value("distractor_selection")
        this_occlusion_type = 0.0  # self.get_epoch_value("occlusion_type")
        this_target_distance = self.get_epoch_value("target_distance")
        this_target_rotation = self.get_epoch_value("target_rotation")

        self.channel.set_float_parameter("cameraSelection", self.camera_type)
        self.channel.set_float_parameter("target_selection", this_target_selection)
        self.channel.set_float_parameter(
            "distractor_selection", this_distractor_selection
        )
        self.channel.set_float_parameter("object_on_left", self.object_on_left)
        self.channel.set_float_parameter("slitSize", this_slit_size)
        self.channel.set_float_parameter("slit_depth", this_slit_depth)
        self.channel.set_float_parameter("targetsFromMidline", this_target_spread)
        self.channel.set_float_parameter("targetsheight", this_target_height)
        self.channel.set_float_parameter("mouseReportDelay", this_mouse_report_delay)
        self.channel.set_float_parameter("startBoxDelay", self.start_box_delay)
        self.channel.set_float_parameter("velocityThreshold", self.velocity_threshold)
        self.channel.set_float_parameter("occlusion_type", this_occlusion_type)
        self.channel.set_float_parameter("targetsZpos", this_target_distance)
        self.channel.set_float_parameter("target_rotation", this_target_rotation)
        print("this occ_type: ", this_occlusion_type)

        # set properties for start box, left report box and right report box
        self.channel.set_float_parameter("L_box_x_min", self.l_report_box[0])
        self.channel.set_float_parameter("L_box_x_max", self.l_report_box[1])
        self.channel.set_float_parameter("L_box_z_min", self.l_report_box[2])
        self.channel.set_float_parameter("L_box_z_max", self.l_report_box[3])

        self.channel.set_float_parameter("R_box_x_min", self.r_report_box[0])
        self.channel.set_float_parameter("R_box_x_max", self.r_report_box[1])
        self.channel.set_float_parameter("R_box_z_min", self.r_report_box[2])
        self.channel.set_float_parameter("R_box_z_max", self.r_report_box[3])

        self.channel.set_float_parameter("TT_box_x_min", self.start_box[0])
        self.channel.set_float_parameter("TT_box_x_max", self.start_box[1])
        self.channel.set_float_parameter("TT_box_z_min", self.start_box[2])
        self.channel.set_float_parameter("TT_box_z_max", self.start_box[3])
        self.channel.set_float_parameter("TT_box_angle", self.start_box[4])
        self.channel.set_float_parameter("distractor", self.distractor)
        self.channel.set_float_parameter("targetSize", self.target_size)
        self.channel.set_float_parameter("Grey_screen_active", self.grey_screen_active)

        # add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_slit_size.append(this_slit_size)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_spread.append(this_target_spread)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_height.append(this_target_height)
        self.trial_mouse_report_delay.append(this_mouse_report_delay)
        self.trial_distractor_selection.append(this_distractor_selection)
        self.trial_target_selection.append(this_target_selection)
        self.trial_occlusion_type.append(this_occlusion_type)
        print(self.trial_occlusion_type)
        self.trial_target_distance.append(this_target_distance)
        self.trial_target_rotation.append(this_target_rotation)
        # super().reset_environment()

    def get_action(self):
        """
        Get actions from DLC and parse them to unity.

        Called by teensyexp's module Agent.
        This function is called on every frame of the game.
        """
        if self.use_dlc == False:
            output = self.previous
        else:
            output = self._get_dlc_on_frame()

        return output

    def check_reward(self):
        """
        Set up the reward.
        """
        if self.reward > 0:
            self.correct += 1

            if self.state[7] > 0:
                print("___ Rewarded - left ___")
                print(self.reward_size)
                self.teensy.write("l_water", [self.reward_size[0]])
            else:
                print("___ Rewarded - right ___")
                print(self.reward_size)
                self.teensy.write("r_water", [self.reward_size[0]])
            self.n_rewards += 1

    def random_target_location(self):
        self.object_on_left = np.random.choice(
            [0.0, 1.0], p=[1 - self.prob_obj_on_left, self.prob_obj_on_left]
        )
        print("object on left", self.object_on_left)

    def block_sampler(self):
        if self.correct == self.block_length:
            if self.block_Left == 0.0:
                self.block_Left = 1.0
            else:
                self.block_Left = 0.0
            self.correct = 0
        if self.block_Left == 0.0:
            self.object_on_left = np.random.choice(
                [0.0, 1.0], p=[self.prob_block_coherence, 1 - self.prob_block_coherence]
            )
        else:
            self.object_on_left = np.random.choice(
                [0.0, 1.0], p=[1 - self.prob_block_coherence, self.prob_block_coherence]
            )
        print("object on left", self.object_on_left)

    def reset_environment(self):
        """
        Reset environment.

        Use parent method implementation call.
        """
        super().reset_environment()

    def get_info(self):
        """
        Get information about position and angle on the GUI

        Returns:
            Dictionnary with 'position' and 'h_angle' keys.
        """
        pos = (
            None
            if self.state is None
            else "%0.3f, %0.3f" % (self.state[0], self.state[1])
        )
        h_angle = None if self.state is None else "%0.2f" % (self.state[2])
        velocity = None if self.state is None else "%0.2f" % (self.state[-1])
        in_left_box = None if self.state is None else "%0.2f" % (self.state[7])
        in_right_box = None if self.state is None else "%0.2f" % (self.state[8])

        return {
            "session time": round(self.cur_time, 1),
            "epoch": self.epoch_labels[self.epoch],
            "episode": self.episode,
            "position": pos,
            "h_angle": self.degrees,
            "rewards": self.n_rewards,
            "velocity": velocity,
            "in_left_box": in_left_box,
            "in_right_box": in_right_box,
        }

    def get_data(self):
        """
        Get data, parent method implementation call

        Returns:
            Dictionary with data
        """
        data_dict = super().get_data()
        data_dict["session_label"] = self.session_label
        data_dict["dlc_read_time"] = np.array(self.dlc_read_time)
        data_dict["dlc_x"] = np.array(self.dlc_x)
        data_dict["dlc_y"] = np.array(self.dlc_y)
        data_dict["dlc_heading"] = np.array(self.dlc_heading)
        data_dict["block_labels"] = np.array(self.trial_epoch_labels)
        data_dict["slit_size"] = np.array(self.trial_slit_size)
        data_dict["trial_slit_depth"] = np.array(self.trial_slit_depth)
        data_dict["r_report_box"] = np.array(self.r_report_box)
        data_dict["l_report_box"] = np.array(self.l_report_box)
        data_dict["start_box"] = np.array(self.start_box)
        data_dict["cropped_image"] = np.array(self.cropped_image)
        data_dict["unity_arena_size"] = np.array(self.unity_arena_size)
        data_dict["camera_rotation"] = np.array(self.rotate_camera)
        data_dict["mouse_report_delay"] = np.array(self.trial_mouse_report_delay)
        data_dict["velocity_threshold"] = self.velocity_threshold
        data_dict["start_box_delay"] = self.start_box_delay
        data_dict["distractor"] = self.distractor
        data_dict["target_size"] = self.target_size
        data_dict["grey_screen_active"] = self.grey_screen_active
        data_dict["camera_type"] = self.camera_type
        data_dict["target_selection"] = np.array(self.trial_target_selection)
        data_dict["distractor_selection"] = np.array(self.trial_distractor_selection)
        data_dict["occlusion_type"] = np.array(self.trial_occlusion_type)
        data_dict["target_distance"] = np.array(self.trial_target_distance)
        data_dict["target_rotation"] = np.array(self.trial_target_rotation)
        data_dict["reward_size"] = np.array(self.trial_reward_size)
        data_dict["prob_obj_on_left"] = self.prob_obj_on_left
        data_dict["slit_size_param"] = np.array(self.slit_size)
        data_dict["block_length_param"] = np.array(self.block_length)
        data_dict["prob_block_coherence"] = np.array(self.prob_block_coherence)
        return data_dict
