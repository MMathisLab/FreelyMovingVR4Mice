import os, numpy as np
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecEnv


class MultiMetricEvalCallback(BaseCallback):
    def __init__(
        self,
        eval_env: VecEnv,
        eval_freq: int,
        n_eval_episodes: int = 10,
        save_dir: str = "./models/best",
        deterministic: bool = True,
        save_composite: bool = True,
        w_success: float = 1.0,
        w_reward: float = 0.1,
        w_steps: float = 0.0,
        verbose: int = 0,
    ):
        super().__init__(verbose)
        self.eval_env, self.eval_freq = eval_env, int(eval_freq)
        self.n_eval_episodes, self.deterministic = n_eval_episodes, deterministic
        self.save_dir, self.save_composite = save_dir, save_composite
        os.makedirs(self.save_dir, exist_ok=True)
        self.best_success = self.best_mean_reward = self.best_composite = -np.inf
        self.w_success, self.w_reward, self.w_steps = w_success, w_reward, w_steps
        self.path_success = os.path.join(self.save_dir, "best_by_success")
        self.path_reward = os.path.join(self.save_dir, "best_by_mean_reward")
        self.path_comp = os.path.join(self.save_dir, "best_by_composite")
        for p in [self.path_success, self.path_reward, self.path_comp]:
            os.makedirs(p, exist_ok=True)

    def _on_step(self) -> bool:
        if self.n_calls % self.eval_freq != 0:
            return True
        m = self._evaluate()
        for k, v in m.items():
            self.logger.record(f"eval/{k}", float(v))
        if m["success_rate"] > self.best_success:
            self.best_success = m["success_rate"]
            self.model.save(os.path.join(self.path_success, "model.zip"))
        if m["mean_reward"] > self.best_mean_reward:
            self.best_mean_reward = m["mean_reward"]
            self.model.save(os.path.join(self.path_reward, "model.zip"))
        if self.save_composite:
            comp = self._composite_score(m)
            self.logger.record("eval/composite_score", float(comp))
            if comp > self.best_composite:
                self.best_composite = comp
                self.model.save(os.path.join(self.path_comp, "model.zip"))
        return True

    def _composite_score(self, m) -> float:
        return (
            self.w_success * m["success_rate"]
            + self.w_reward * m["mean_reward"]
            + self.w_steps * (-m["mean_steps"])
        )

    def _evaluate(self):
        ep_rewards, ep_steps, ep_success = [], [], []
        env = self.eval_env
        for _ in range(self.n_eval_episodes):
            obs = env.reset()
            ep_rew, steps, success = 0.0, 0, 0
            while True:
                action, _ = self.model.predict(obs, deterministic=self.deterministic)
                obs, reward, done, infos = env.step(action)
                ep_rew += float(reward[0])
                steps += 1
                if done[0]:
                    success = int(bool(infos[0].get("is_success", False)))
                    break
            ep_rewards.append(ep_rew)
            ep_steps.append(steps)
            ep_success.append(success)
        import numpy as np

        ep_rewards = np.asarray(ep_rewards, float)
        ep_steps = np.asarray(ep_steps, float)
        ep_success = np.asarray(ep_success, float)
        sm = ep_success == 1
        sm_reward = float(ep_rewards[sm].mean()) if sm.any() else 0.0
        sm_steps = float(ep_steps[sm].mean()) if sm.any() else 0.0
        return {
            "mean_reward": float(ep_rewards.mean()),
            "median_reward": float(np.median(ep_rewards)),
            "mean_steps": float(ep_steps.mean()),
            "success_rate": float(ep_success.mean()),
            "success_mean_reward": sm_reward,
            "success_mean_steps": sm_steps,
        }
