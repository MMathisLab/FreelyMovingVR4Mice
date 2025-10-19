# Script to test make commands

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
    "CHECKPOINT_PATH", "/app/rl_task/models/PPO_AugmentedReality_20250827_1626/model.zip"
)
LOAD_CHECKPOINT = os.getenv("LOAD_CHECKPOINT", False)

print("Script executed successfully.")