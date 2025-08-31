import numpy as np

from PIL import Image
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor

from rl_task.task.envs.rl_task_gym_wrapper import MouseTaskToGymWrapper


def make_env(
    env_path: str,
    task_config: str,
    fps: int = 50,
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
        save_data (bool, optional): Whether to save the step-wise agent information as a .pkl file at the end of training
        pos_reward_size (float, optional): Size of positive reward to give agent for correct execution.
        neg_reward_size (float, optional): Size of negative reward to give agent for wrong execution.
        step_penalty_size (float, optional): Size of penalty to give agent at each step. Used to encourage the agent to solve the task.
        max_episode_steps (int, optional): Maximum number of steps before each episode is truncated. Acts as an episode time limit.
        frame_stack_size (int, optional): Number of frames (i.e. visual observations) to give the policy at each step. Acts as a sort of "memory".

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
                task_config=task_config,
                fps=fps,
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

            return env

        return _thunk

    env_fns = [make_thunk(i) for i in range(num_envs)]
    if num_envs > 1:
        env = SubprocVecEnv(env_fns, start_method="spawn")
    else:
        env = DummyVecEnv(env_fns)

    return VecMonitor(env)
