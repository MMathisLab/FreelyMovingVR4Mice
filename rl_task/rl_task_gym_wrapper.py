import numpy as np
import gymnasium as gym

from gymnasium import spaces
from rl_task.fake_teensy import FakeTeensy
from rl_task.rl_task_active_sensing import ActiveSensingTaskRL


class MouseTaskToGymWrapper(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 50}

    def __init__(
        self,
        env_path,
        fps=50,
        render_mode=None,
        base_port=5004,
        worker_id=0,
        worker_seed=None,
        batchmode=True,
        save_data=False,
        pos_reward_size=1,
        neg_reward_size=0,
        step_penalty_size=0,
        max_episode_steps=None,
    ):

        self.worker_seed = worker_seed
        self.pos_reward_size = pos_reward_size
        self.neg_reward_size = neg_reward_size
        self.step_penalty_size = step_penalty_size
        self.task = ActiveSensingTaskRL(
            env_path=env_path,
            teensy=FakeTeensy(),
            monitor=None,
            write_video=False,
            fps=fps,
            session_label=["rl_ar_discrim_multi_occluders"],
            epochs=[250],
            epoch_labels=["dual_teardrop"],
            config_file_path=None,
            reward_size=pos_reward_size,
            cropped_image=[0, 530, 0, 510],
            unity_arena_size=[-9, 9, -10, -2],
            # r_report_box=[5, 10, -4, -2],
            r_report_box=[7, 10, -3.5, -1],
            # l_report_box=[-10, -5, -4, -2],
            l_report_box=[-10, -7, -3.5, -1],
            start_box=[-4, 4, -9, -5, 90],
            rotate_camera=90.0,
            prob_obj_on_left=0.5,
            prob_block_coherence=0.5,
            mouse_report_delay=0.0,
            slit_size=[15.0, 10.78, 7.75, 5.57, 4.0],
            slit_depth=0.02,
            target_selection=6.0,
            distractor_selection=4.0,
            occlusion_type=0.0,
            camera_type=1.0,
            target_spread=4.0,
            target_rotation=0.0,
            target_size=2.0,
            target_height=3.0,
            block_length=1.0,
            start_box_delay=0.25,
            velocity_threshold=20.0,
            distractor=1.0,
            grey_screen_active=0.0,
            target_distance=3.0,
            use_dlc=False,
            base_port=base_port,
            worker_id=worker_id,
            batchmode=batchmode,
            save_data=save_data,
        )
        self.task.start()

        # Define action space
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)

        # Define observation space
        C, H, W = self.task.vis_obs_shape
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(C, H, W), dtype=np.uint8
        )

        # Defining parameters to track
        self.episode_reward = 0.0
        self.episode_length = 0

        # Defining time horizon
        self.max_episode_steps = max_episode_steps

        assert render_mode is None or render_mode in self.metadata["render_modes"]
        self.render_mode = render_mode

        self.window = None
        self.clock = None

    def _get_obs(self):
        return self.task.vis_state

    def _get_info(self):
        return self.task.get_info()

    def _to_uint8(self, obs: np.ndarray):
        if obs.dtype == np.uint8 and obs.min() >= 0 and obs.max() <= 255:
            return obs
        return (255.0 * obs).astype(np.uint8)

    def reset(self, *, seed=None, options=None):
        s = seed if self.worker_seed is None else self.worker_seed
        super().reset(seed=s)
        obs, _ = self.task.reset(seed=s)

        self.episode_reward = 0.0
        self.episode_length = 0

        return self._to_uint8(obs), {}  # Gymnasium API

    def step(self, action):
        observation, reward, terminated, _ = self.task.loop(action)

        true_reward = 0
        if reward == 1:
            true_reward = self.pos_reward_size
        if reward == -1:
            true_reward = -self.neg_reward_size
        if reward == 0:
            true_reward = -self.step_penalty_size

        self.episode_reward += true_reward
        self.episode_length += 1

        truncated = False
        info = {}

        if terminated:
            info["episode"] = {
                "r": self.episode_reward,
                "l": self.episode_length,
            }
        elif self.max_episode_steps is not None:
            if self.episode_length >= self.max_episode_steps:
                truncated = True
                info["episode"] = {
                    "r": self.episode_reward,
                    "l": self.episode_length,
                }

        return self._to_uint8(observation), true_reward, terminated, truncated, info

    def render(self, mode="human"):
        # return self.unity.render(mode=mode)
        pass

    def close(self):
        self.task.stop()
