"""Training callbacks for evaluation and model checkpointing.

Contains a template evaluation callback.
"""

import os
import numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecEnv


class CustomCallback(BaseCallback):
    """Template to define a custom evaluation callback"""

    def __init__(
        self,
        verbose: int = 0,
    ):
        super().__init__(verbose)

    def _on_step(self) -> bool:
        return True

    def _composite_score(self, m) -> float:
        return 0

    def _evaluate(self):
        return {}
