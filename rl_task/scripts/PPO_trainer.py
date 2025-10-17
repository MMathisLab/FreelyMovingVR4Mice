"""Train a PPO agent on the Unity Active Sensing task.

Provides vectorized environment setup, configurable policy extractor, and
Weights & Biases logging with optional checkpoint loading.
"""

import os, wandb, torch

from pathlib import Path
from datetime import datetime, timedelta
from pyvirtualdisplay.display import Display
from wandb.integration.sb3 import WandbCallback
from stable_baselines3.common.callbacks import (
    EvalCallback,
    StopTrainingOnNoModelImprovement,
    CallbackList,
)

from stable_baselines3.ppo import PPO
from stable_baselines3.common.utils import set_random_seed

from dotenv import load_dotenv

from rl_task.task.utils.env_factory import make_env
from rl_task.task.extractors.custom_extractors import CnnMlpExtractor

_rltask = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_rltask / ".env")

GPU_ID = 0
ENV_PATH = os.getenv("UNITY_ENV_PATH", "/app/rl_task/AR_build/augmented_reality.x86_64")
MODEL_SAVE_DIR = os.getenv("MODEL_DIR", "/app/rl_task/models")
CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_DIR", "/app/rl_task/models/PPO_AugmentedReality_20250827_1626/model.zip"
)
LOAD_CHECKPOINT = os.getenv("LOAD_CHECKPOINT", False)

# Training configuration parameters
config = dict(
    seed=None,
    env_name="AugmentedReality",
    algorithm="PPO",
    # environment
    env_kwargs=dict(
        task_config="shape_discrim",
        pos_reward_size=1.5,
        neg_reward_size=1.5,
        trunc_penalty_size=1.5,
        step_penalty_size=0.0,
        max_episode_steps=220,
    ),
    # rollout / optimization
    algo_kwargs=dict(
        policy="CnnPolicy",
        learning_rate=1e-4,
        n_steps=256,
        batch_size=192,
        n_epochs=4,
        gamma=0.99,
        gae_lambda=0.97,
        clip_range=0.2,
        ent_coef=0.005,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=None,
        use_sde=False,
    ),
    # model / policy
    policy_kwargs=dict(
        net_arch=dict(pi=[256, 128], vf=[256, 128]),
        activation_fn=torch.nn.SiLU,
        normalize_images=True,  # SB3 scales to [0,1]
    ),
    # training budget
    num_envs=6,
    total_timesteps=1_000_000,
)

if __name__ == "__main__":
    display = Display(backend="xvfb", visible=False, size=(420, 245))
    display.start()

    wandb.login()
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    set_random_seed(config["seed"])

    now = (datetime.now() + timedelta(hours=2)).strftime("%Y%m%d_%H%M")
    name = f"PPO_{config['env_name']}_{now}"

    run = wandb.init(
        name=name,
        project="semester-project",
        config=config,
        sync_tensorboard=True,
        save_code=True,
    )

    # Training
    env = make_env(
        env_path=ENV_PATH,
        num_envs=config["num_envs"],
        **config["env_kwargs"],
    )

    # Evaluation
    eval_env = make_env(
        env_path=ENV_PATH,
        num_envs=1,
        base_port=5004 + config["num_envs"],
        **config["env_kwargs"],
    )

    device = f"cuda:{GPU_ID}" if torch.cuda.is_available() else "cpu"

    if LOAD_CHECKPOINT and os.path.exists(CHECKPOINT_PATH):
        print(f"[INFO] Loading checkpoint from {CHECKPOINT_PATH}...")
        model = PPO.load(
            CHECKPOINT_PATH,
            env=env,
            custom_objects={
                "observation_space": env.observation_space,
                "action_space": env.action_space,
            },
            device=device,
        )

    else:
        print("[INFO] No checkpoint found, starting fresh...")
        model = PPO(
            env=env,
            **config["algo_kwargs"],
            policy_kwargs=config["policy_kwargs"],
            verbose=1,
            tensorboard_log=f"/app/rl_task/logs/{run.id}",
            device=device,
            seed=config["seed"],
        )

    # Evaluation frequency every 4 rollouts
    eval_freq_steps = int(4 * config["algo_kwargs"]["n_steps"] * config["num_envs"])

    # Early stopping if no new best for N evals
    eval_cb = EvalCallback(
        eval_env=eval_env,
        best_model_save_path=os.path.join(MODEL_SAVE_DIR, name, "best"),
        log_path=os.path.join(MODEL_SAVE_DIR, name, "eval"),
        eval_freq=eval_freq_steps,
        n_eval_episodes=20,
        deterministic=True,
        render=False,
        callback_after_eval=StopTrainingOnNoModelImprovement(
            max_no_improvement_evals=10,  # patience
            min_evals=5,
            verbose=1,
        ),
    )

    cb = CallbackList(
        [
            WandbCallback(
                model_save_path=os.path.join(MODEL_SAVE_DIR, name),
                model_save_freq=2_000,
                verbose=2,
            ),
            eval_cb,
        ]
    )

    try:
        print(f"[INFO] Starting training on {config['num_envs']} environment(s)...")
        model.learn(
            total_timesteps=config["total_timesteps"],
            callback=cb,
            progress_bar=True,
            log_interval=1,
        )
    except:
        print("\n[INFO] Training interrupted. Saving current model...")

        # save interrupted model
        interrupted_path = os.path.join(MODEL_SAVE_DIR, name, "interrupted_model")
        os.makedirs(interrupted_path, exist_ok=True)
        model.save(os.path.join(interrupted_path, "model.zip"))
    finally:
        # always cleanup
        print("[INFO] Cleaning up...")
        env.close()
        eval_env.close()
        run.finish()
        display.stop()

        # save final (or interrupted) model
        final_path = os.path.join(MODEL_SAVE_DIR, name, "final_model")
        os.makedirs(final_path, exist_ok=True)
        model.save(os.path.join(final_path, "model.zip"))
        print(f"[INFO] Model saved to {final_path}")
