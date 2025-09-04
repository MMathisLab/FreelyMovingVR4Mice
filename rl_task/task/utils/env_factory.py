"""Factory utilities to build vectorized Gym environments for training.

This module exposes ``make_env`` which constructs either a single-process
``DummyVecEnv`` or a multi-process ``SubprocVecEnv``, and wraps it with
``VecMonitor`` for metric logging compatible with SB3.
"""

from stable_baselines3.common.vec_env import (
    DummyVecEnv,
    SubprocVecEnv,
    VecMonitor,
    VecEnv,
)

from rl_task.task.envs.rl_task_gym_wrapper import MouseTaskToGymWrapper


def make_env(
    env_path: str,
    task_config: str,
    fps: int = 50,
    num_envs: int = 1,
    base_port: int = 5004,
    batchmode: bool = True,
    save_data: bool = False,
    pos_reward_size: float = 1.0,
    neg_reward_size: float = 0.0,
    step_penalty_size: float = 0.0,
    trunc_penalty_size: float = 0.0,
    max_episode_steps: int | None = None,
) -> VecEnv:
    """
    Create a Unity-based Gymnasium environment, optionally vectorized for parallelism.

    Args:
        env_path (str): Path to the Unity executable build.
        task_config (str): Preset name from ``rl_task/config/rl_experiments.yaml``. Examples:
            "contrast_discrim", "shape_discrim_occluders", etc.
        num_envs (int, optional): Number of parallel environments to create. Defaults to 1.
        base_port (int, optional): Base port for Unity communication. Each environment instance will increment this port. Defaults to 5005.
        batchmode (bool, optional): Whether to run Unity in batch mode (no graphics). Defaults to True.
        save_data (bool, optional): Whether to save the step-wise agent information as a .pkl file at the end of training
        pos_reward_size (float, optional): Size of positive reward to give agent for correct execution.
        neg_reward_size (float, optional): Size of negative reward to give agent for wrong execution.
        step_penalty_size (float, optional): Size of penalty to be given to the agent at each step.
        trunc_penalty_size (float, optional): Size of penalty to be given to the agent if environment times out (related to max_episode_steps).
        max_episode_steps (int, optional): Maximum number of steps before each episode is truncated.

    Returns:
        VecEnv: A Gymnasium-compatible vectorized environment. If ``num_envs > 1``,
        returns a ``SubprocVecEnv``; otherwise, a ``DummyVecEnv``.

    Notes:
        - The vector environment is wrapped with ``VecMonitor`` for logging.
    """

    def make_thunk(worker_id: int):
        def _thunk():
            env = MouseTaskToGymWrapper(
                env_path=env_path,
                task_config=task_config,
                fps=fps,
                base_port=base_port,
                worker_id=worker_id,
                batchmode=batchmode,
                save_data=save_data,
                pos_reward_size=pos_reward_size,
                neg_reward_size=neg_reward_size,
                trunc_penalty_size=trunc_penalty_size,
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
