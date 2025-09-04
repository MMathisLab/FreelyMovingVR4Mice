"""Gymnasium wrapper for the Unity-based Active Sensing task.

This adapter exposes the Unity environment (accessed via the
``ActiveSensingTaskRL`` facade) as a Gymnasium-compatible environment so it can
be trained with libraries like Stable-Baselines3.

Notes:
- Observations are visual (C, H, W) uint8 images. If the upstream env returns
  floats in [0, 1], they are converted to uint8 in-place.
- Rewards are shaped according to the ``*_reward_size`` parameters; the
  underlying Unity env returns a ternary signal {-1, 0, 1} which is mapped here
  to scalar rewards.
"""

import numpy as np
import gymnasium as gym

from gymnasium import spaces
from rl_task.task.utils.fake_teensy import FakeTeensy
from rl_task.task.envs.rl_task_active_sensing import ActiveSensingTaskRL
from rl_task.config.config import load_config


class MouseTaskToGymWrapper(gym.Env):
    """Wrap the Unity Active Sensing environment as a Gymnasium env.

    Parameters mirror the Unity task configuration defined in
    ``rl_task/config/rl_experiments.yaml``. The wrapper handles environment
    startup, reward shaping, episode tracking, and observation dtype handling.

    Args:
        env_path: Filesystem path to the Unity build. If ``None``, attaches to
            a running Unity editor.
        task_config: Name of a preset under ``presets`` in the YAML config.
        fps: Simulation step frequency (Hz).
        base_port: Base communication port for Unity ML-Agents.
        worker_id: Worker id offset; useful when spawning multiple envs.
        batchmode: Whether to run Unity headless.
        save_data: Whether to dump a pickle of step-wise data on close.
        pos_reward_size: Reward when Unity emits +1.
        neg_reward_size: Magnitude for Unity -1 (applied as negative reward).
        trunc_penalty_size: Penalty added when an episode times out.
        step_penalty_size: Small step penalty shaping when Unity emits 0.
        max_episode_steps: Truncate episodes locally after this many steps.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 50}

    def __init__(
        self,
        env_path,
        task_config,
        fps=50,
        base_port=5004,
        worker_id=0,
        batchmode=True,
        save_data=False,
        pos_reward_size=1,
        neg_reward_size=0,
        trunc_penalty_size=0,
        step_penalty_size=0,
        max_episode_steps=None,
    ):
        self.pos_reward_size = pos_reward_size
        self.neg_reward_size = neg_reward_size
        self.trunc_penalty_size = trunc_penalty_size
        self.step_penalty_size = step_penalty_size
        self.cfg = load_config(
            preset_name=task_config,
            yaml_path="/app/rl_task/config/rl_experiments.yaml",
            env_path=env_path,
            teensy=FakeTeensy(),
            fps=fps,
            base_port=base_port,
            worker_id=worker_id,
            batchmode=batchmode,
            save_data=save_data,
        )
        self.task = ActiveSensingTaskRL(**self.cfg.as_kwargs())
        self.task.start()

        # Define action space: [move, turn] both in [-1, 1]
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)

        # Define observation space from Unity visual observation spec
        C, H, W = self.task.vis_obs_shape
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(C, H, W), dtype=np.uint8
        )

        # Defining parameters to track
        self.episode_reward = 0.0
        self.episode_length = 0

        # Defining time horizon
        self.max_episode_steps = max_episode_steps

        # Doesn't support rendering at this point in time
        self.render_mode = None

    def _get_obs(self):
        """Return the current visual observation (uint8)."""
        return self.task.vis_state

    def _get_info(self):
        """Return auxiliary info from the Unity task (if any)."""
        return self.task.get_info()

    def _to_uint8(self, obs: np.ndarray) -> np.ndarray:
        """Ensure observations are in uint8 format for SB3 compatibility."""
        if obs.dtype == np.uint8 and obs.min() >= 0 and obs.max() <= 255:
            return obs
        return (255.0 * obs).astype(np.uint8)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs, _ = self.task.reset(seed=seed)

        self.episode_reward = 0.0
        self.episode_length = 0

        return self._to_uint8(obs), {}

    def step(self, action):
        """Step the Unity environment with an action within the defined space.

        Maps Unity's {-1, 0, +1} reward signal to shaped rewards and handles
        local truncation if ``max_episode_steps`` is set.
        """
        observation, reward_signal, terminated, _ = self.task.step_task(action)

        reward = 0
        if reward_signal == 1:
            reward = self.pos_reward_size
        if reward_signal == -1:
            reward = -self.neg_reward_size
        if reward_signal == 0:
            reward = -self.step_penalty_size

        self.episode_reward += reward
        self.episode_length += 1

        truncated = False
        info = {}

        if terminated:
            info["is_success"] = int(reward_signal == 1)
            info["episode"] = {
                "r": self.episode_reward,
                "l": self.episode_length,
            }
        elif (
            self.max_episode_steps is not None
            and self.episode_length >= self.max_episode_steps
        ):
            truncated = True
            timeout_penalty = -self.trunc_penalty_size
            self.episode_reward += timeout_penalty
            reward += timeout_penalty

            info["is_success"] = 0
            info["episode"] = {
                "r": self.episode_reward,
                "l": self.episode_length,
            }

        return self._to_uint8(observation), reward, terminated, truncated, info

    def render(self, mode="human"):
        pass

    def close(self):
        self.task.stop()
