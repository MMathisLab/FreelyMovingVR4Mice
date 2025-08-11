import time
import pickle
import numpy as np

from typing import List
from pathlib import Path
from mlagents_envs.environment import UnityEnvironment, ActionTuple
from unittest.mock import patch

from teensy.fake_teensy import FakeTeensy
from mouse_task.task_active_sensing import ActiveSensingTask


class ActiveSensingTaskRL(ActiveSensingTask):
    def __init__(
        self,
        teensy: FakeTeensy,
        session_label: List[str],
        config_file_path: Path,
        monitor: bool | None,
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
        use_dlc: bool = False,
    ):
        with patch(
            "mouse_task.task_active_sensing.process_config",
            return_value={"ar_env_unity_absolute_path": ""},
        ):
            super().__init__(
                teensy,
                session_label,
                config_file_path,
                monitor,
                write_video,
                fps,
                epochs,
                epoch_labels,
                reward_size,
                cropped_image,
                unity_arena_size,
                r_report_box,
                l_report_box,
                start_box,
                rotate_camera,
                prob_obj_on_left,
                prob_block_coherence,
                mouse_report_delay,
                slit_size,
                slit_depth,
                target_selection,
                distractor_selection,
                occlusion_type,
                camera_type,
                target_spread,
                target_rotation,
                target_size,
                target_height,
                block_length,
                start_box_delay,
                velocity_threshold,
                distractor,
                grey_screen_active,
                target_distance,
                use_dlc,
            )

    def start(self):
        # Start tracking time
        self.start_time = time.time()

        # Start unity game
        self.set_channel()

        self.env = UnityEnvironment(
            file_name=None,
            base_port=5004,
            worker_id=0,
            # additional_args=["-batchmode"],
            side_channels=[self.channel],
        )

        self.env.reset()
        self.agent = list(self.env.behavior_specs)[0]
        self.agent_spec = self.env.behavior_specs[self.agent]

        # Retrieve the action space and observation space of the agent
        self.action_space = self.agent_spec.action_spec
        self.observation_space = self.agent_spec.observation_specs

        print(f"[DEBUG] Agent information")
        print(f"[DEBUG]   * Action space : {self.action_space}")
        print(f"[DEUBG]   * Observation space : {self.observation_space}")

        # Set up state observations and video (if necessary)
        obs_shapes = [obs_spec.shape for obs_spec in self.agent_spec.observation_specs]
        obs_dim = [len(shape) for shape in obs_shapes]
        self.vec_obs_ind = np.where(np.array(obs_dim) == 1)[0][0]
        self.vis_obs_inds = np.where(np.array(obs_dim) == 3)[0]
        self.vis_obs_ind = self.vis_obs_inds[0] if len(self.vis_obs_inds) > 0 else None

        if self.vis_obs_ind is not None:
            self.vis_obs_shape = np.array(obs_shapes, dtype=object)[self.vis_obs_ind]

        # Access the environment state
        decision_steps, _ = self.env.get_steps(self.agent)
        self.state = decision_steps.obs[self.vec_obs_ind][0]
        self.vis_state = decision_steps.obs[self.vis_obs_ind]
        self.episode = 1

    def transform_action(self, action):
        raw_move, raw_turn = action
        current_heading = np.deg2rad(self.state[2])

        dx = raw_move * np.sin(current_heading)
        dz = raw_move * np.cos(current_heading)

        print(f"[DEBUG]   * Transformed action : {dx, dz, raw_turn}")
        return np.array([dx, dz, raw_turn, 0], dtype=np.float32)

    def loop(self, action):
        print(f"[DEBUG] Action received : {action}")
        print(f"[DEBUG]   * State before step : {np.round(self.state, 2)}")

        self.step += 1
        self.cur_time = time.time() - self.start_time

        self.episode_vec.append(self.episode)  # trial
        self.step_vec.append(self.step)  # frame
        self.time_vec.append(self.cur_time)  # time for each frame

        self.action = self.transform_action(action)
        self.action_vec.append(self.action)

        # Take step in environment
        action_tuple = ActionTuple()
        action_tuple.add_continuous(self.action.reshape(1, -1))
        self.env.set_actions(self.agent, action_tuple)

        # Unity env++
        self.env.step()

        # Get observations
        step_result = self.get_step_result()
        self.reward = step_result.reward
        self.reward_vec.append(self.reward)
        self.ep_reward += self.reward

        self.terminal = self.done  # last frame --> next trial
        self.terminal_vec.append(self.terminal)
        self.check_reward()

        # Get info
        self.state = step_result.obs[self.vec_obs_ind]
        self.vis_state = step_result.obs[self.vis_obs_ind]
        info = self.get_info()

        print(f"[DEBUG]   * State after step : {np.round(self.state, 2)}")

        self.state_vec.append(self.state)

        return self.vis_state, self.reward, self.terminal, False, info

    def set_channel(self):
        if self.block_length == 1:
            self.random_target_location()
        if self.block_length > 1:
            self.block_sampler()

        this_prob_obj_left = self.prob_obj_on_left
        this_slit_size = np.random.choice(self.slit_sizes)
        this_slit_depth = self.get_epoch_value("slit_depth")
        this_target_spread = self.get_epoch_value("target_spread")
        this_target_height = self.get_epoch_value("target_height")
        this_mouse_report_delay = self.get_epoch_value("mouse_report_delay")
        this_target_selection = self.get_epoch_value("target_selection")
        this_distractor_selection = self.get_epoch_value("distractor_selection")
        this_occlusion_type = self.get_epoch_value("occlusion_type")
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

        # Set properties for start box, left report box and right report box
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

        # Add trial parameters to trial vectors so that we can save them to the log file
        self.trial_epoch_labels.append(self.get_epoch_value("epoch_labels"))
        self.trial_slit_size.append(this_slit_size)
        self.trial_slit_depth.append(this_slit_depth)
        self.trial_target_spread.append(this_target_spread)
        self.trial_target_height.append(this_target_height)
        self.trial_mouse_report_delay.append(this_mouse_report_delay)
        self.trial_distractor_selection.append(this_distractor_selection)
        self.trial_target_selection.append(this_target_selection)
        self.trial_occlusion_type.append(this_occlusion_type)
        self.trial_target_distance.append(this_target_distance)
        self.trial_target_rotation.append(this_target_rotation)
        self.trial_reward_size.append(self.reward_size)
        self.trial_prob_obj_on_left.append(self.prob_obj_on_left)

        # Setting the restart position of the agent
        self.channel.set_float_parameter("start_x", 0)
        self.channel.set_float_parameter("start_z", -8)
        self.channel.set_float_parameter("start_angle", 0)

    def get_info(self):
        pos = (
            None
            if self.state is None
            else "%0.3f, %0.3f" % (self.state[0], self.state[1])
        )
        h_angle = None if self.state is None else "%0.2f" % (self.state[2])
        velocity = None if self.state is None else "%0.2f" % (self.state[9])
        in_left_box = None if self.state is None else "%0.2f" % (self.state[7])
        in_right_box = None if self.state is None else "%0.2f" % (self.state[8])
        start_box_delay = None if self.state is None else "%0.2f" % (self.state[12])
        photodiode_state = None if self.state is None else "%0.2f" % (self.state[11])
        accuracy = (
            0.0
            if self.episode == 0
            else "%0.2f" % (float(self.n_rewards) / self.episode)
        )

        return {
            "epoch": self.epoch_labels[self.epoch],
            "episode": self.episode,
            "position": pos,
            "h_angle": h_angle,
            "degrees": self.degrees,
            "rewards": self.n_rewards,
            "accuracy": accuracy,
            "velocity": velocity,
            "in_left_box": in_left_box,
            "in_right_box": in_right_box,
            "photodiode": photodiode_state,
            "start_box_delay": start_box_delay,
        }

    def reset_environment(self):
        self.set_channel()
        self.env.reset()
        decision_steps, _ = self.env.get_steps(self.agent)
        self.ep_reward = 0
        self.episode_start_time = self.cur_time
        self.state = decision_steps[self.agent_num].obs[self.vec_obs_ind]
        self.vis_state = decision_steps[self.agent_num].obs[self.vis_obs_ind]
        return decision_steps[self.agent_num].obs, self.get_info()

    def reset(self, seed=None):
        if seed is not None:
            import random

            print(f"[DEBUG] Setting random seed : {seed}")
            np.random.seed(seed)
            random.seed(seed)
        return self.reset_environment()

    def stop(self):
        self.env.close()
        data_to_save = self.get_data()
        pickle.dump(data_to_save, open("./rl_task_data.pkl", "wb"))
