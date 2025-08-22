import os
import torch

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv
from gymnasium.wrappers import TimeLimit

from utils.feature_extractor import Extractor
from rl_task_gym_wrapper import MouseTaskToGymWrapper

ENV_PATH = "AR_build/macOS/augmented_reality.app"
MODEL_SAVE_DIR = "rl_task/models"

config = {
    "algorithm": "PPO",
    "policy_type": "CnnPolicy",
    "n_steps": 4096,
    "batch_size": 64,
    "n_epochs": 10,
    "total_timesteps": 500_000,
    "env_name": "AugmentedReality",
    "num_envs": 1,
}

if __name__ == "__main__":
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

    # env = make_env(
    #     env_path=ENV_PATH,
    #     num_envs=config["num_envs"],
    #     seed=42,
    #     time_horizon=64,
    # )

    env = MouseTaskToGymWrapper(
        env_path=ENV_PATH,
        fps=50,
        base_port=5005,
        worker_id=0,
        batchmode=True,
    )
    env = TimeLimit(env, max_episode_steps=300)
    env = DummyVecEnv([lambda: Monitor(env=env)])

    policy_kwargs = dict(
        optimizer_class=torch.optim.Adam,
        # optimizer_kwargs=dict(lr=3e-4, weight_decay=1e-4),
        features_extractor_class=Extractor,
        features_extractor_kwargs=dict(pretrained=True, freeze_backbone=True),
    )

    model = PPO(
        env=env,
        policy=config["policy_type"],
        n_steps=config["n_steps"] // config["num_envs"],
        batch_size=config["batch_size"],
        n_epochs=config["n_epochs"],
        policy_kwargs=policy_kwargs,
        verbose=1,
        device="cuda" if torch.cuda.is_available() else "cpu",
    )

    print(f"[DEBUG] Starting training on {config['num_envs']} environment(s)...")
    model.learn(
        total_timesteps=config["total_timesteps"],
        progress_bar=True,
    )
