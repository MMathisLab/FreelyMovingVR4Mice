import time
import pickle
import random
import numpy as np

from typing import List
from pathlib import Path
from mlagents_envs.environment import UnityEnvironment, ActionTuple
from unittest.mock import patch

from rl_task.fake_teensy import FakeTeensy
from mouse_task.task_active_sensing import ActiveSensingTask


class ActiveSensingTaskRL(ActiveSensingTask):
    def __init__(
        self,
        env_path: Path | None,
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
        batchmode: bool = True,
        base_port: int = 5004,
        worker_id: int = 0,
        save_data: bool = False,
    ):

        self.angle_in_degrees = True
        self.max_lin_speed = 300  # mm / s
        self.max_ang_speed = np.pi  # rad / s
        self.dt = 1 / fps
        self.default_virtual_state = np.array(
            [cropped_image[1] // 2, cropped_image[3] // 4, 0]
        )

        self.batchmode = batchmode
        self.base_port = base_port
        self.worker_id = worker_id

        self.save_data = save_data

        with patch(
            "mouse_task.task_active_sensing.process_config",
            return_value={"ar_env_unity_absolute_path": env_path},
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
        self.start_time = time.time()

        self.set_channel()

        if self.env_path is None:
            print("[INFO] Waiting for Unity editor to connect...")

        self.env = UnityEnvironment(
            file_name=self.env_path,
            base_port=self.base_port,
            worker_id=self.worker_id,
            additional_args=["-batchmode"] if self.batchmode else [],
            side_channels=[self.channel],
        )

        if self.env_path is None:
            print("[INFO] Editor connected successfully!")

        self.env.reset()

        self.agent = list(self.env.behavior_specs)[0]
        self.agent_spec = self.env.behavior_specs[self.agent]

        # Retrieve the action and observation spaces of the agent
        self.action_space = self.agent_spec.action_spec
        self.observation_space = self.agent_spec.observation_specs

        # print(f"[DEBUG] Agent information")
        # print(f"[DEBUG]   * Action space : {self.action_space}")
        # print(f"[DEUBG]   * Observation space : {self.observation_space}")

        # Set up state observations
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
        self.ep_length = 0

        self.virtual_state = self.default_virtual_state

    def _wrap_angle(self, a):
        return (a + np.pi) % (2 * np.pi) - np.pi

    def _change_space(self, x, z, space1, space2):
        # Interpolate input coordinates from space 1 to space 2
        v_x0, v_x1, v_z0, v_z1 = space1
        u_x0, u_x1, u_z0, u_z1 = space2

        x_u = np.interp(x, [v_x0, v_x1], [u_x0, u_x1])
        z_u = np.interp(z, [v_z0, v_z1], [u_z0, u_z1])

        return np.array([x_u, z_u])

    def transform_action(self, action):
        # Implement navigation kinematics to send Unity next absolute position

        dt = self.dt
        move, turn = action

        # rescaling "move" action to [0, 1] so that it cannot move backwards
        move = (move + 1) / 2

        # Unpack current virtual state
        x, z, a = self.virtual_state

        v = move * self.max_lin_speed
        omega = turn * self.max_ang_speed

        da = omega * dt
        theta = a + da

        ux0, ux1, uz0, uz1 = self.unity_arena_size
        unity_width = ux1 - ux0
        unity_length = uz1 - uz0

        dx = v * dt * np.sin(theta)
        dz = v * dt * np.cos(theta) * unity_width / unity_length

        x_new = x + dx
        z_new = z + dz
        a_new = a + da

        # Clamp to virtual arena bounds
        vx0, vx1, vz0, vz1 = self.cropped_image
        virtual_x = float(np.clip(x_new, vx0, vx1))
        virtual_z = float(np.clip(z_new, vz0, vz1))

        self.virtual_state = (virtual_x, virtual_z, a_new)

        unity_x, unity_z = self._change_space(
            virtual_x,
            virtual_z,
            space1=self.cropped_image,
            space2=self.unity_arena_size,
        )

        # Persist and format output angle
        a_out = np.degrees(a_new) if self.angle_in_degrees else a_new
        return np.array([unity_x, unity_z, a_out, 0.0], dtype=np.float32)

    def loop(self, action):
        self.step += 1
        self.ep_length += 1
        self.cur_time = time.time() - self.start_time

        self.episode_vec.append(self.episode)  # trial
        self.step_vec.append(self.step)  # frame
        self.time_vec.append(self.cur_time)  # time for each frame

        # Select action
        self.action = self.transform_action(action)
        self.action_vec.append(self.action)

        # Take step in environment
        action_tuple = ActionTuple()
        action_tuple.add_continuous(self.action.reshape(1, -1))
        self.env.set_actions(self.agent, action_tuple)

        self.env.step()

        # Get observations
        step_result = self.get_step_result()
        self.reward = step_result.reward
        self.reward_vec.append(self.reward)
        self.ep_reward += self.reward

        self.terminal = self.done  # last frame --> next trial
        self.terminal_vec.append(self.terminal)
        self.check_reward()

        # Get state and info
        self.state = step_result.obs[self.vec_obs_ind]
        self.state_vec.append(self.state)
        print(self.vis_state.shape)

        self.vis_state = step_result.obs[self.vis_obs_ind]

        info = self.get_info()

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

        # Setting the Unity env to be in RL mode
        self.channel.set_float_parameter("RL_training", 1)
        # self.channel.set_float_parameter("RL_pos_reward_size", self.reward_size[0])
        # self.channel.set_float_parameter("RL_neg_reward_size", self.neg_reward_size)
        # self.channel.set_float_parameter("RL_step_penalty_size", self.step_penalty_size)

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
            "episode_num": self.episode,
            "episode": {"r": self.ep_reward, "l": self.ep_length},
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

    def sample_start_state(self):
        # Uniformly sample starting position coordinates within the self.start_box

        # Sample (x, z) in Unity coordinates
        x_min, x_max, z_min, z_max, _ = self.start_box
        x = np.random.uniform(x_min, x_max)
        z = np.random.uniform(z_min, z_max)

        # Uniformly sample head angle between -pi/4 and +pi/4 radians
        theta = np.random.uniform(-np.pi / 4, np.pi / 4)

        # Interpolate to cropped_image pixel space
        px, py = self._change_space(
            x, z, space1=self.unity_arena_size, space2=self.cropped_image
        )

        return np.array([px, py, theta])

    def reset_environment(self):
        info = self.get_info()

        self.set_channel()
        self.env.reset()

        self.ep_reward = 0
        self.ep_length = 0
        self.episode_start_time = self.cur_time

        decision_steps, _ = self.env.get_steps(self.agent)
        self.state = decision_steps[self.agent_num].obs[self.vec_obs_ind]
        self.vis_state = decision_steps[self.agent_num].obs[self.vis_obs_ind]
        self.virtual_state = self.sample_start_state()

        # Send an null action to reset agent to default position
        self.loop(action=np.array([0.0, 0.0]))

        return self.vis_state, info

    def reset(self, seed=None):
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)
        return self.reset_environment()

    def stop(self):
        self.env.close()

        if self.save_data:
            data_to_save = self.get_data()
            pickle.dump(data_to_save, open("/app/rl_task_data.pkl", "wb"))
