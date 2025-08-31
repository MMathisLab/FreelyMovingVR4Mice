import os, wandb, torch
from datetime import datetime, timedelta
from wandb.integration.sb3 import WandbCallback
from pyvirtualdisplay import Display

from stable_baselines3.ppo import PPO
from stable_baselines3.common.utils import set_random_seed

from dotenv import load_dotenv

from utils.env_factory import make_env
from utils.vanilla_extractor import CustomExtractor

GPU_ID = 0
ENV_PATH = "/app/rl_task/AR_build/augmented_reality.x86_64"
MODEL_SAVE_DIR = "/app/rl_task/models"
CHECKPOINT_PATH = "/app/rl_task/models/PPO_AugmentedReality_20250827_1626/model.zip"
LOAD_CHECKPOINT = True

config = dict(
    seed=42,
    env_name="AugmentedReality",
    algorithm="PPO",
    policy_type="CnnPolicy",
    # model / policy
    net_arch=dict(pi=[512, 256, 128], vf=[512, 256, 128]),
    activation_fn=torch.nn.SiLU,
    normalize_images=True,  # # SB3 scales to [0,1]
    # rollout / optimization
    num_envs=6,
    n_steps=256,
    batch_size=192,
    n_epochs=4,
    learning_rate=1e-4,
    gamma=0.99,
    gae_lambda=0.97,
    clip_range=0.2,
    target_kl=None,
    ent_coef=0.005,
    vf_coef=0.5,
    max_grad_norm=0.5,
    use_sde=True,
    sde_sample_freq=64,
    # training budget
    total_timesteps=1_000_000,
    max_episode_steps=150,
    # reward shaping
    pos_reward_size=1.5,
    neg_reward_size=1.5,
    step_penalty_size=0.01,
)

if __name__ == "__main__":
    display = Display(backend="xvfb", visible=False, size=(420, 245))
    display.start()

    load_dotenv(dotenv_path="/app/rl_task/.env")  # reads .env into os.environ
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
        features_extractor_class=CustomExtractor,
        net_arch=config["net_arch"],
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
            policy=config["policy_type"],
            learning_rate=config["learning_rate"],
            n_steps=config["n_steps"],
            batch_size=config["batch_size"],
            n_epochs=config["n_epochs"],
            gamma=config["gamma"],
            gae_lambda=config["gae_lambda"],
            clip_range=config["clip_range"],
            ent_coef=config["ent_coef"],
            vf_coef=config["vf_coef"],
            max_grad_norm=config["max_grad_norm"],
            target_kl=config["target_kl"],
            use_sde=config["use_sde"],
            sde_sample_freq=config["sde_sample_freq"],
            policy_kwargs=policy_kwargs,
            verbose=1,
            tensorboard_log=f"/app/rl_task/logs/{run.id}",
            device=device,
            seed=config["seed"],
        )

    print(f"[INFO] Starting training on {config['num_envs']} environment(s)...")
    model.learn(
        total_timesteps=config["total_timesteps"],
        callback=WandbCallback(
            model_save_path=os.path.join(MODEL_SAVE_DIR, name),
            model_save_freq=2_000,
            verbose=2,
        ),
        progress_bar=True,
        log_interval=1,
    )

    # Save final model
    final_path = os.path.join(MODEL_SAVE_DIR, name, "final_model")
    os.makedirs(final_path, exist_ok=True)
    model.save(os.path.join(final_path, "model.zip"))

    run.finish()
    display.stop()
