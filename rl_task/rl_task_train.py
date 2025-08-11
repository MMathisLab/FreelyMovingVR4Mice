import os
import torch
from stable_baselines3 import PPO

# from utility import make_env
# from feature_extractor import Extractor


# ENV_PATH = "/app/environments/chaser/single/chaser_single.x86_64"
# ENV_PATH = "/app/environments/roller/roller.x86_64"
ENV_PATH = None
MODEL_SAVE_DIR = "rl_task/models"

config = {
    "algorithm": "PPO",
    "policy_type": "CnnPolicy",
    "n_steps": 4096,
    "batch_size": 64,
    "n_epochs": 10,
    "total_timesteps": 500_000,
    "env_name": "RollerAgent",
    "num_envs": 16,
}

if __name__ == "__main__":
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

    env = make_env(
        env_path=ENV_PATH,
        num_envs=config["num_envs"],
        seed=42,
        time_horizon=64,
    )

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
