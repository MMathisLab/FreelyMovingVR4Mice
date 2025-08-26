import yaml, wandb, os, torch
from datetime import datetime, timedelta
from wandb.integration.sb3 import WandbCallback
from pyvirtualdisplay import Display
from sb3_contrib.ppo_recurrent import RecurrentPPO
from stable_baselines3.common.utils import get_linear_fn
from dotenv import load_dotenv

from utils.utility import make_env
from utils.feature_extractor import Extractor

ENV_PATH = "/app/rl_task/AR_build/augmented_reality.x86_64"
MODEL_SAVE_DIR = "/app/rl_task/models"
CHECKPOINT_PATH = (
    "/app/rl_task/models/RecurrentPPO_AugmentedReality_20250822_1330/model.zip"
)
LOAD_CHECKPOINT = False

config = {
    "algorithm": "RecurrentPPO",
    "policy_type": "CnnLstmPolicy",
    "learning_rate": 3e-4,
    "n_steps": 1536,  # must be divisible by num_envs
    "batch_size": 192,  # must divide n_steps
    "n_epochs": 4,
    "gamma": 0.995,
    "gae_lambda": 0.97,
    "clip_range": 0.2,
    "target_kl": 0.03,
    "ent_coef": 0.02,
    "use_sde": False,
    "total_timesteps": 1_000_000,
    "env_name": "AugmentedReality",
    "max_episode_steps": 200,
    "pos_reward_size": 2,
    "neg_reward_size": 2,
    "step_penalty_size": 0.01,
    "num_envs": 6,
    # recurrent-specific
    "lstm_hidden_size": 256,
    "n_lstm_layers": 1,
    "shared_lstm": False,
}


if __name__ == "__main__":
    # Start xvfb headless display
    display = Display(backend="xvfb", visible=False, size=(420, 245))
    display.start()

    load_dotenv(dotenv_path="/app/rl_task/.env")
    wandb.login()
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    now = (datetime.now() + timedelta(hours=2)).strftime("%Y%m%d_%H%M")
    name = f"RecurrentPPO_{config['env_name']}_{now}"

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
        pos_reward_size=config["pos_reward_size"],
        neg_reward_size=config["neg_reward_size"],
        step_penalty_size=config["step_penalty_size"],
        max_episode_steps=config["max_episode_steps"],
    )

    policy_kwargs = dict(
        optimizer_class=torch.optim.Adam,
        features_extractor_class=Extractor,
        features_extractor_kwargs=dict(pretrained=True, freeze_backbone=True),
        net_arch=dict(
            pi=[256, 128],  # actor network
            vf=[512, 256],  # critic network
        ),
        lstm_hidden_size=config["lstm_hidden_size"],
        n_lstm_layers=config["n_lstm_layers"],
        shared_lstm=config["shared_lstm"],
    )

    if LOAD_CHECKPOINT and os.path.exists(CHECKPOINT_PATH):
        print(f"[INFO] Loading checkpoint from {CHECKPOINT_PATH}...")
        model = RecurrentPPO.load(
            CHECKPOINT_PATH,
            env=env,
            custom_objects={
                "observation_space": env.observation_space,
                "action_space": env.action_space,
            },
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
        model.policy_kwargs = policy_kwargs

    else:
        print("[INFO] No checkpoint found, starting fresh...")
        model = RecurrentPPO(
            policy=config["policy_type"],
            env=env,
            learning_rate=config["learning_rate"],
            n_steps=config["n_steps"] // config["num_envs"],  # steps per env rollout
            batch_size=config["batch_size"],
            n_epochs=config["n_epochs"],
            gamma=config["gamma"],
            gae_lambda=config["gae_lambda"],
            clip_range=config["clip_range"],
            target_kl=config["target_kl"],
            ent_coef=config["ent_coef"],
            use_sde=config["use_sde"],
            policy_kwargs=policy_kwargs,
            verbose=1,
            tensorboard_log=f"/app/rl_task/logs/{run.id}",
            device="cuda" if torch.cuda.is_available() else "cpu",
        )

    print(f"[INFO] Starting training on {config['num_envs']} environment(s)...")
    model.learn(
        total_timesteps=config["total_timesteps"],
        callback=WandbCallback(
            model_save_path=os.path.join(MODEL_SAVE_DIR, name),
            model_save_freq=250,
            verbose=2,
        ),
        progress_bar=True,
    )

    run.finish()
    display.stop()
