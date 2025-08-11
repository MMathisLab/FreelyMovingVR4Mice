import random
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from teensy.fake_teensy import FakeTeensy
from rl_task_active_sensing import ActiveSensingTaskRL


class MouseTaskToGymWrapper(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}

    def __init__(self, env_path, render_mode=None):
        self.task = ActiveSensingTaskRL(
            teensy=FakeTeensy(),
            monitor=None,
            write_video=False,
            fps=60.0,
            session_label=["ar_discrim"],
            epochs=[250],
            epoch_labels=["dual_teardrop"],
            config_file_path=None,
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
            slit_size=[4.0, 10.0, 2],
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
            distractor=1.0,
            grey_screen_active=0.0,
            target_distance=3.0,
            use_dlc=False,
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

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs, info = self.task.reset(seed=seed)

        # Transform to observation uint8 obervation space
        obs = (255.0 * obs[self.task.vis_obs_ind]).astype(np.uint8)
        return obs, info  # Gymnasium API

    def step(self, action):
        observation, reward, terminated, truncation, info = self.task.loop(action)
        print(f"[DEBUG] Observation type : {type(observation)}")
        return observation, reward, terminated, truncation, info

    def render(self, mode="human"):
        # return self.unity.render(mode=mode)
        pass

    def close(self):
        self.task.stop()
