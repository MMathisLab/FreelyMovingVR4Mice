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
        fps,
        render_mode=None,
        base_port=5004,
        worker_id=0,
        worker_seed=None,
        batchmode=True,
        pos_reward_size=1,
        neg_reward_size=0,
        step_penalty_size=0,
    ):

        self.worker_seed = worker_seed
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
            r_report_box=[5, 10, -4, -2],
            l_report_box=[-10, -5, -4, -2],
            start_box=[-4, 4, -9, -5, 90],
            rotate_camera=90.0,
            prob_obj_on_left=0.5,
            prob_block_coherence=0.5,
            mouse_report_delay=0.0,
            slit_size=[15.0, 10.78, 7.75, 5.57, 4.0],
            slit_depth=0.02,
            target_selection=13.0,
            distractor_selection=6.0,
            occlusion_type=1.0,
            camera_type=1.0,
            target_spread=3.0,
            target_rotation=15,
            target_size=2.0,
            target_height=3.0,
            block_length=1.0,
            start_box_delay=0.25,
            velocity_threshold=20.0,
            distractor=1.0,
            grey_screen_active=0.0,
            target_distance=4.0,
            use_dlc=False,
            base_port=base_port,
            worker_id=worker_id,
            batchmode=batchmode,
            neg_reward_size=neg_reward_size,
            step_penalty_size=step_penalty_size,
        )
        self.task.start()

        # Define action space
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)

        # Define observation space
        C, H, W = self.task.vis_obs_shape
        self.observation_space = spaces.Box(
            low=0, high=255, shape=(C, H, W), dtype=np.uint8
        )

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
        obs, info = self.task.reset(seed=s)
        return self._to_uint8(obs), info  # Gymnasium API

    def step(self, action):
        observation, reward, terminated, truncation, info = self.task.loop(action)
        return self._to_uint8(observation), reward, terminated, truncation, info

    def render(self, mode="human"):
        # return self.unity.render(mode=mode)
        pass

    def close(self):
        self.task.stop()
