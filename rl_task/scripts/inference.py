"""Simple on-policy episode rollouts for trained models.

Loads a PPO or RecurrentPPO checkpoint and evaluates several episodes in the
Unity Active Sensing environment, printing summary statistics.
"""

from __future__ import annotations

import numpy as np

from stable_baselines3 import PPO
from sb3_contrib import RecurrentPPO

from rl_task.task.envs.rl_task_gym_wrapper import MouseTaskToGymWrapper

ENV_PATH = "rl_task/AR_build/augmented_reality.x86_64"
ENV_PATH = None
MODEL_PATH = "rl_task/models/RecurrentPPO_AugmentedReality_20250825_1959"
N_EPS = 5
MAX_EP_LEN = 120
DETERMINISTIC = False
ALGO = RecurrentPPO if "recurrentppo" in MODEL_PATH.lower() else PPO


def eval():
    """Run N_EPS episodes and print mean return/length."""
    env = env = MouseTaskToGymWrapper(
        env_path=ENV_PATH,
        task_config="shape_discrim",
        fps=50,
        base_port=5004,
        worker_id=0,
        worker_seed=None,
        batchmode=False,
        save_data=False,
        pos_reward_size=1.5,
        neg_reward_size=1.5,
        step_penalty_size=0.01,
        max_episode_steps=MAX_EP_LEN,
    )
    model = ALGO.load(
        MODEL_PATH,
        env=env,
        custom_objects={
            "observation_space": env.observation_space,
            "action_space": env.action_space,
        },
    )
    model.policy.set_training_mode(False)

    ep_returns = []
    ep_lengths = []

    try:
        for ep in range(N_EPS):
            obs, info = env.reset()
            done = False
            ep_ret = 0.0
            ep_len = 0

            while not done:
                # get action from policy
                action, _ = model.predict(obs, deterministic=DETERMINISTIC)

                # step
                obs, reward, terminated, truncated, info = env.step(action)
                ep_ret += float(reward)
                ep_len += 1

                # cap by our own max length (independent of Unity MaxStep)
                if ep_len >= MAX_EP_LEN:
                    truncated = True

                done = bool(terminated or truncated)

            ep_returns.append(ep_ret)
            ep_lengths.append(ep_len)
            print(f"[Episode {ep+1:02d}] return={ep_ret:.3f} len={ep_len}")

        mean_r = float(np.mean(ep_returns)) if ep_returns else 0.0
        std_r = float(np.std(ep_returns)) if ep_returns else 0.0
        mean_len = float(np.mean(ep_lengths)) if ep_lengths else 0.0

        print(f"\nMean reward over {N_EPS} episodes: {mean_r:.2f} ± {std_r:.2f}")
        print(f"Mean episode length: {mean_len:.1f} steps")

    finally:
        env.close()


if __name__ == "__main__":
    eval()
