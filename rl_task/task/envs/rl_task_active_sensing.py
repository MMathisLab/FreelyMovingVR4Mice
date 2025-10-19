"""Unity Active Sensing task compatibility layer for RL usage.

This extends the base ``ActiveSensingTask`` to provide an interface compatible
with the Gymnasium environment structure and common RL training loops:

- Starts/stops the Unity player with configurable ports/worker ids.
- Exposes a Gym-like step/reset via ``step`` and ``reset``.
- Converts SB3-style continuous actions into Unity-compatible absolute poses.

With this class the artificial agent is allowed to freely move inside a window of size ``cropped_image``
corresponding to the size of video feed coming from the camera on the rig used for tracking the mouse with DLC.
"""

import pickle
import random
import numpy as np

from typing import List
from pathlib import Path
from unittest.mock import patch

from rl_task.task.utils.fake_teensy import FakeTeensy
from mouse_task.task_active_sensing import ActiveSensingTask


class ActiveSensingTaskRL(ActiveSensingTask):
    """RL-oriented wrapper around the Unity Active Sensing task.

    Args are primarily forwarded to the parent task. Only Unity process options
    (``batchmode``, ``base_port``, ``worker_id``) and logging (``save_data``)
    are handled locally.
    """

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

        # RL / Unity process specific args to create vector envs
        # where each instance needs its own port/worker_id and all
        # should run in batchmode without needing dlc tracking.
        use_dlc: bool = False,
        batchmode: bool = True,
        base_port: int = 5004,
        worker_id: int = 0,
        save_data: bool = False,
    ):

        self.angle_in_degrees = True

        # Empirical upper bounds based on both visual inspection and
        # on analysis of real behavioral data of mice performing the task.
        self.max_lin_speed = 300  # mm / s
        self.max_ang_speed = np.pi  # rad / s

        self.dt = 1 / fps
        self.default_virtual_state = np.array(
            [cropped_image[1] // 2, cropped_image[3] // 4, 0]
        )

        self.save_data = save_data

        # Patching the config processing to inject the Unity env path
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
                batchmode,
                base_port,
                worker_id,
            )

    def start(self):
        """Start Unity environment and initialize observation spaces."""
        self.display_args = ["-batchmode"] if self.batchmode else []

        super().start()

        # Retrieve the action and observation spaces of the agent
        self.action_space = self.agent_spec.action_spec
        self.observation_space = self.agent_spec.observation_specs

        decision_steps, _ = self.env.get_steps(self.agent)
        self.vis_state = decision_steps.obs[self.vis_obs_ind]

        # Define the default agent virtual state to be the center of the cropped image.
        # The agent is able to freely move within a virtual arena that has the same size
        # as the cropped image from the camera feed used for dlc tracking.
        self.virtual_state = self.default_virtual_state

    def _wrap_angle(self, a: float) -> float:
        """Wrap angle to [-pi, pi] range."""
        return (a + np.pi) % (2 * np.pi) - np.pi

    def _change_space(
        self, x: float, z: float, space1: List[float], space2: List[float]
    ):
        """Interpolate coordinates from one (x,z) space to another.

        ``space`` is [x_min, x_max, z_min, z_max].
        """
        v_x0, v_x1, v_z0, v_z1 = space1
        u_x0, u_x1, u_z0, u_z1 = space2

        x_u = np.interp(x, [v_x0, v_x1], [u_x0, u_x1])
        z_u = np.interp(z, [v_z0, v_z1], [u_z0, u_z1])

        return np.array([x_u, z_u])

    def _kinematics(self, action: np.ndarray) -> np.ndarray:
        """Map a normalized [move, turn] action to Unity absolute pose.

        Implements simple unicycle kinematics in a virtual pixel space and then
        converts to Unity's arena coordinates.

        The order in which actions are processed: first turn, then move
        """

        dt = self.dt
        move, turn = action

        # rescaling "move" action to [0, 1] so that it cannot move backwards
        # Choice made to account for the fact that mice in the real task
        # rarely move backwards.
        move = (move + 1) / 2

        # Unpack current virtual state
        x, z, a = self.virtual_state

        v = move * self.max_lin_speed
        omega = turn * self.max_ang_speed

        # Update heading angle (direction) before moving
        da = omega * dt
        theta = a + da

        ux0, ux1, uz0, uz1 = self.unity_arena_size
        unity_width = ux1 - ux0
        unity_length = uz1 - uz0

        # Move along the new head direction
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

        # Interpolate from agent virtual space to Unity space
        unity_x, unity_z = self._change_space(
            virtual_x,
            virtual_z,
            space1=self.cropped_image,
            space2=self.unity_arena_size,
        )

        # Persist and format output angle
        a_out = np.degrees(a_new) if self.angle_in_degrees else a_new
        return np.array([unity_x, unity_z, a_out, 0.0], dtype=np.float32)

    def get_action(self):
        """Overrides superclass method.
        Returns current step Unity pos computed by ``_kinematics()`` method.
        """
        # Check if the current instance has an attribute named 'action'
        if hasattr(self, "action"):
            return self.action
        else:
            raise AttributeError("The 'action' attribute is missing.")

    def step_task(self, action):
        """One environment step with action; returns (obs, reward, done, info)."""
        self.action = self._kinematics(action)

        _, _ = super().loop()

        step_result = self.get_step_result()
        self.vis_state = step_result.obs[self.vis_obs_ind]

        return self.vis_state, self.reward, self.terminal, {}

    def _check_end_session(self):
        """Overrides superclass default behavior"""
        return True

    def set_channel(self):
        """Push the current episode parameters to the Unity side channel."""
        # Setting mouse task env params
        super().set_channel()

        # Setting the Unity env to be in RL mode
        self.channel.set_float_parameter("RL_training", 1)

    def sample_start_state(self) -> np.ndarray:
        """Uniformly sample a start (x,z,theta) within the start box."""

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

    def reset(self, seed=None):
        """Reset Unity episode and return initial visual observation, info."""
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)

        super().reset_environment()

        decision_steps, _ = self.env.get_steps(self.agent)
        self.state = decision_steps[self.agent_num].obs[self.vec_obs_ind]
        self.vis_state = decision_steps[self.agent_num].obs[self.vis_obs_ind]

        # Randomly sample a starting position within the start_box
        self.virtual_state = self.sample_start_state()

        # Send a dummy action to reset agent to starting position
        self.step_task(action=np.array([0.0, 0.0]))

        return self.vis_state, {}

    def stop(self):
        """Close Unity and optionally persist step-wise data to disk."""
        super().stop()

        if self.save_data:
            data_to_save = self.get_data()
            pickle.dump(data_to_save, open("/app/rl_task_data.pkl", "wb"))
