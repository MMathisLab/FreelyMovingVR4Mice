import yaml, wandb, os, torch
from datetime import datetime, timedelta
from wandb.integration.sb3 import WandbCallback
from pyvirtualdisplay import Display
from stable_baselines3 import PPO
from dotenv import load_dotenv

from utils.utility import make_env
from utils.feature_extractor import Extractor

ENV_PATH = "/app/rl_task/AR_build/augmented_reality.x86_64"
MODEL_SAVE_DIR = "/app/rl_task/models"
CHECKPOINT_PATH = "/app/rl_task/models/PPO_AugmentedReality_20250822_1330/model.zip"

config = {
    "algorithm": "PPO",
    "policy_type": "CnnPolicy",
    "n_steps": 2048,
    "batch_size": 64, # try 128?
    "n_epochs": 5,
    "gamma": .995,
    "clip_range": 0.3,
    "ent_coef": 0.01,
    "use_sde": True,
    "total_timesteps": 500_000,
    "env_name": "AugmentedReality",
    "time_horizon": 300,
    "pos_reward_size": 2,
    "neg_reward_size": 2,
    "step_penalty_size": 0.01,
    "num_envs": 4,
}

if __name__ == "__main__":
    # Start a virtual display
    display = Display(visible=0, size=(600, 300))
    display.start()

    load_dotenv(dotenv_path="/app/rl_task/.env")  # reads .env into os.environ
    wandb.login()
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    now = (datetime.now() + timedelta(hours=2)).strftime("%Y%m%d_%H%M")
    name = f"PPO_{config['env_name']}_{now}"

    run = wandb.init(
        name=name,
        project="semester-project",
        config=config,
        sync_tensorboard=True,
        save_code=True,
    )

    env = make_env(
        env_path=ENV_PATH,
        num_envs=config["num_envs"],
        seed=None,
        time_horizon=config["time_horizon"],
        pos_reward_size=config["pos_reward_size"],
        neg_reward_size=config["neg_reward_size"],
        step_penalty_size=config["step_penalty_size"],
    )

    policy_kwargs = dict(
        optimizer_class=torch.optim.Adam,
        # optimizer_kwargs=dict(lr=3e-4, weight_decay=1e-4),
        features_extractor_class=Extractor,
        features_extractor_kwargs=dict(pretrained=True, freeze_backbone=True),
    )
    
    if os.path.exists(CHECKPOINT_PATH):
        print(f"[DEBUG] Loading checkpoint from {CHECKPOINT_PATH} ...")
        model = PPO.load(
            CHECKPOINT_PATH,
            env=env,  # attach new env
            custom_objects={  # make sure new extractor/env overrides are used
                "observation_space": env.observation_space,
                "action_space": env.action_space,
            },
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
        # update policy kwargs if they changed
        model.policy_kwargs = policy_kwargs
    else:
        print("[DEBUG] No checkpoint found, starting fresh...")
        model = PPO(
            env=env,
            policy=config["policy_type"],
            n_steps=config["n_steps"] // config["num_envs"],
            batch_size=config["batch_size"],
            n_epochs=config["n_epochs"],
            gamma=config["gamma"],
            clip_range=config["clip_range"],
            ent_coef=config["ent_coef"],
            use_sde=config["use_sde"],
            policy_kwargs=policy_kwargs,
            verbose=1,
            tensorboard_log=f"/app/rl_task/logs/{run.id}",
            device="cuda" if torch.cuda.is_available() else "cpu",
        )

    print(f"[DEBUG] Starting training on {config['num_envs']} environment(s)...")
    model.learn(
        total_timesteps=config["total_timesteps"],
        callback=WandbCallback(
            model_save_path=os.path.join(MODEL_SAVE_DIR, name),
            model_save_freq=250,  # based on wandb's step
            verbose=2,
        ),
        progress_bar=True,
    )

    run.finish()

    # Stop the virtual display
    display.stop()
