import numpy as np

from PIL import Image
from mlagents_envs.environment import UnityEnvironment
from gymnasium.wrappers import TimeLimit
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.monitor import Monitor

from rl_task.rl_task_gym_wrapper import MouseTaskToGymWrapper


def make_env(
    env_path: str,
    num_envs: int = 1,
    base_port: int = 5005,
    seed: int = 42,
    batchmode: bool = True,
    save_data: bool = False,
    pos_reward_size: float = 1.0,
    neg_reward_size: float = 0.0,
    step_penalty_size: float = 0.0,
    max_episode_steps: int | None = None,
):
    """
    Create a Unity-based Gym environment, optionally vectorized for parallelism.

    Args:
        env_path (str): Path to the Unity executable build.
        num_envs (int, optional): Number of parallel environments to create. Defaults to 1.
        base_port (int, optional): Base port for Unity communication. Each environment instance will increment this port. Defaults to 5005.
        seed (int, optional): Random seed for reproducibility. Each environment will use seed + worker_id. Defaults to 42.
        batchmode (bool, optional): Whether to run Unity in batch mode (no graphics). Defaults to True.

    Returns:
        gym.Env: A Gym-compatible environment. If num_envs > 1, returns a SubprocVecEnv for parallel execution; otherwise, returns a DummyVecEnv.

    Notes:
        - Each environment instance is wrapped with a Monitor for logging.
        - The Unity environment is wrapped with UnityToGymWrapper for Gym compatibility.
        - For multiple environments, SubprocVecEnv is used for parallelism.
        - The returned environment(s) use uint8 visual observations.
    """

    def make_thunk(worker_id: int):
        def _thunk():
            # give each worker a distinct seed if seed is provided
            worker_seed = None if seed is None else seed + worker_id
            env = MouseTaskToGymWrapper(
                env_path=env_path,
                fps=40,
                base_port=base_port,
                worker_id=worker_id,
                worker_seed=worker_seed,
                batchmode=batchmode,
                save_data=save_data,
                pos_reward_size=pos_reward_size,
                neg_reward_size=neg_reward_size,
                step_penalty_size=step_penalty_size,
                max_episode_steps=max_episode_steps,
            )

            return Monitor(env)

        return _thunk

    env_fns = [make_thunk(i) for i in range(num_envs)]
    if num_envs > 1:
        return SubprocVecEnv(env_fns)
    else:
        return DummyVecEnv(env_fns)


def save_visual_obs(obs: np.ndarray, name: str = ""):
    """
    Save a visual observation (image) to disk as a PNG file.

    Args:
        obs (np.ndarray): The observation array, which may be batched or unbatched,
            and may be channel-first or channel-last. Handles both single and multiple
            observations (e.g., from vectorized environments).

    The function processes the observation to ensure it is in the correct format
    (removing batch dimension, converting to channel-last, and ensuring uint8 type)
    before saving it as './obs/obs.png'.
    """
    if isinstance(obs, tuple) or isinstance(obs, list):
        obs = obs[0]
    if obs is not None:
        # Remove batch dimension if present
        if len(obs.shape) == 4:
            obs = obs[0]
        # If channel first, convert to channel last
        if obs.shape[0] in [1, 3] and obs.shape[-1] not in [1, 3]:
            obs = np.transpose(obs, (1, 2, 0))
        # Convert to uint8 if needed
        if obs.dtype != np.uint8:
            obs = np.clip(obs, 0, 255).astype(np.uint8)
        img = Image.fromarray(obs)
        img.save(f"{name}_obs.png")
        print(f"[INFO] Saved first_obs image to {name}_obs.png")
