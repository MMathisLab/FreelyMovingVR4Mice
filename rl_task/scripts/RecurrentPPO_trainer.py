"""Train a RecurrentPPO agent on the Unity Active Sensing task.

The choice for RecurrentPPO is inspired by the following paper: 
*   http://arxiv.org/abs/2505.12278

This script wires up vectorized environments, a visual feature extractor,
evaluation callbacks, W&B logging, and optional checkpoint loading.
"""

import os, wandb, torch

from pathlib import Path
from datetime import datetime, timedelta
from wandb.integration.sb3 import WandbCallback
from stable_baselines3.common.callbacks import (
    EvalCallback,
    StopTrainingOnNoModelImprovement,
    CallbackList,
)
from pyvirtualdisplay.display import Display

from sb3_contrib.ppo_recurrent import RecurrentPPO

from dotenv import load_dotenv

from rl_task.task.utils.env_factory import make_env
from rl_task.task.extractors.custom_extractors import (
    CnnMlpExtractor,
    CnnExtractor,
    DepthwiseExtractor,
)

_rltask = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_rltask / ".env")

GPU_ID = 1
ENV_PATH = os.getenv("UNITY_ENV_PATH", "/app/rl_task/AR_build/augmented_reality.x86_64")
MODEL_SAVE_DIR = os.getenv("MODEL_DIR", "/app/rl_task/models")
CHECKPOINT_PATH = os.getenv(
    "CHECKPOINT_PATH",
    "/app/rl_task/models/RecurrentPPO_AugmentedReality_20250901_1426/final_model/model.zip",
)
LOAD_CHECKPOINT = os.getenv("LOAD_CHECKPOINT", True)

config = dict(
    seed=None,
    env_name="AugmentedReality",
    algorithm="RecurrentPPO",
    # environment
    env_kwargs=dict(
        task_config="shape_discrim_multi_occluders",
        pos_reward_size=1.5,
        neg_reward_size=1.5,
        trunc_penalty_size=1.5,
        step_penalty_size=0.0,
        max_episode_steps=220,
    ),
    # rollout / optimization
    algo_kwargs=dict(
        policy="CnnLstmPolicy",
        learning_rate=3e-5,
        n_steps=256,
        batch_size=96,
        n_epochs=3,
        gamma=0.99,
        gae_lambda=0.97,
        clip_range=0.15,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=0.03,
        use_sde=False,
    ),
    # policy
    policy_kwargs=dict(
        optimizer_class=torch.optim.Adam,
        features_extractor_class=DepthwiseExtractor,
        share_features_extractor=True,
        features_extractor_kwargs=dict(
            features_dim=400,
            base_channels=24,
            use_depthwise=True,
            pool_out=(12, 8),
            head_channels=32,
            mlp_hidden=(1024, 512),
        ),
        net_arch=dict(
            pi=[400, 300, 200],
            vf=[400, 300, 200],
        ),
        activation_fn=torch.nn.SiLU,
        ortho_init=True,
        lstm_hidden_size=200,
        n_lstm_layers=1,
        shared_lstm=False,
        enable_critic_lstm=True,
        normalize_images=True,  # SB3 input images to [0,1]
    ),
    # training budget
    num_envs=8,
    total_timesteps=5_000_000,
)


if __name__ == "__main__":
    display = Display(backend="xvfb", visible=False, size=(420, 245))
    display.start()

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
        dir="/app/rl_task/",
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
        model = RecurrentPPO.load(
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
        model = RecurrentPPO(
            env=env,
            **config["algo_kwargs"],
            policy_kwargs=config["policy_kwargs"],
            verbose=1,
            tensorboard_log=f"/app/rl_task/logs/{run.id}",
            device=device,
            seed=config["seed"],
        )

    # Set random seed for reproducibility
    if config["seed"] is not None:
        print(f"[INFO] Setting random seed... [{config['seed']}]")
        model.set_random_seed(config["seed"])

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
        def safe_call(obj, method: str, name: str):
            """Call obj.method() if it exists; never raise."""
            try:
                if obj is None:
                    return
                fn = getattr(obj, method, None)
                if callable(fn):
                    fn()
            except Exception as e:
                print(f"[WARN] {name} failed: {e!r}")

        # always cleanup
        print("[INFO] Cleaning up...")
        safe_call(env, "close", "env.close")
        safe_call(eval_env, "close", "eval_env.close")
        safe_call(run, "finish", "wandb.run.finish")
        safe_call(display, "stop", "display.stop")

        # save final (or interrupted) model
        try:
            final_path = Path(MODEL_SAVE_DIR) / name / "final_model"
            final_path.mkdir(parents=True, exist_ok=True)
            if model is not None:
                model.save(final_path / "model.zip")
                print(f"[INFO] Model saved to {final_path}")
            else:
                print("[WARN] model is None; skipping save")
        except Exception as e:
            print(f"[ERROR] Failed to save model: {e!r}")
