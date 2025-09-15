# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Repository orientation and architecture

- Unity + Python RL stack. The rl_task package wraps a Unity scene (ML-Agents) as a Gymnasium environment for training/evaluation with Stable-Baselines3.
- Key pieces (paths relative to repo root):
  - rl_task/: Python RL code.
    - rl_task_gym_wrapper.py: MouseTaskToGymWrapper turns the Unity task into a Gymnasium Env (action space: move/turn in [-1, 1], observation space: visual frames as uint8 C×H×W). It instantiates ActiveSensingTaskRL and bridges step/reset to Unity.
    - rl_task_active_sensing.py: ActiveSensingTaskRL extends mouse_task.task_active_sensing.ActiveSensingTask (from mouse_task/) and uses mlagents_envs.UnityEnvironment to connect to the Unity app or Editor. It maps 2D actions to Unity coordinates/rotation with simple kinematics (transform_action), sets per‑trial parameters via a side-channel, and exposes observations/rewards.
    - utils/feature_extractor.py: SB3 BaseFeaturesExtractor built on torchvision’s MobileNetV3-Small using create_feature_extractor up to the flatten node; normalizes inputs with ImageNet stats.
    - utils/utility.py: make_env creates single or vectorized (DummyVecEnv/SubprocVecEnv) Gym environments and applies TimeLimit/Monitor wrappers. Also includes save_visual_obs helper.
    - PPO_trainer.py: Container-oriented PPO training script with W&B logging, optional checkpoint resume, and virtual display (xvfb). Assumes paths under /app/rl_task in the container, reads /app/rl_task/.env, and spins up multiple parallel envs via make_env.
    - rl_task_train.py: Simpler single-env PPO training variant intended for running directly (non-container) with a macOS Unity build path.
    - inference.py: Loads a trained PPO and evaluates N episodes (prints returns/lengths). By default connects to the Unity Editor (ENV_PATH=None) unless you set a build path.
    - tests/test_rl_game_manual.py: Manual “play the environment” loop via keyboard (pygame); helpful for smoke-testing observations, rendering, and action mapping.
  - mouse_task/: Source of the base ActiveSensingTask used by rl_task (Unity task logic, Teensy integration, and test utilities live here).
  - AugmentedReality/: Unity project for the scene/assets.
- Containerization. docker-compose.yml defines two services: trainer (scaled, GPU) and developer (interactive). The Dockerfile installs Python deps, OpenCV, xvfb, etc., and copies ML-Agents from a separate additional build context. /app inside the container is the repo root mounted from the host.

Important note from README

- Project docs: <https://mmathislab.github.io/FreelyMovingVR4Mice>

Common commands
Note: run these from the repository root unless noted. On macOS, use Python 3.10.

- Local setup (without Docker)
  - Create venv and install deps:

    ```bash path=null start=null
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r rl_task/requirements.txt
    # Needed for Unity connection and manual keyboard test:
    pip install mlagents_envs pygame
    ```

  - Manual smoke test (keyboard control; connects to Unity Editor when ENV_PATH=None):

    ```bash path=null start=null
    python rl_task/tests/test_rl_game_manual.py
    ```

    Tips:
    - Start the Unity scene in the Editor first; the Python side will wait for the Editor to connect.
    - Arrow/WASD to move/turn; ESC to quit. Console logs FPS and episode stats.
  - Train (simple, single-env variant):
    - Ensure rl_task/rl_task_train.py’s ENV_PATH points to a Unity build you have on disk (e.g., AR_build/macOS/augmented_reality.app). Then run:

      ```bash path=null start=null
      python rl_task/rl_task_train.py
      ```

  - Inference (evaluate a saved PPO):
    - Edit ENV_PATH (None for Editor, or a path to a Unity build) and MODEL_PATH in rl_task/inference.py, then run:

      ```bash path=null start=null
      python rl_task/inference.py
      ```

- Dockerized development and training (recommended for full dependency parity)
  Prereqs (environment variables used by docker-compose.yml):
  - VR4MICE_PATH: absolute path to this repo (mounted at /app)
  - MLAGENTS_PATH: absolute path to a local ML-Agents checkout (the directory that contains ml-agents-envs/)
  - USER: your system user (usually already set)
  Example setup and build:

  ```bash path=null start=null
  export VR4MICE_PATH="$(pwd)"
  export MLAGENTS_PATH="/path/to/ml-agents"
  make build             # builds images (uses BuildKit additional contexts)
  # or build without cache:
  make build_nc
  ```

  Bring services up (trainer is scalable; developer is an interactive utility container):

  ```bash path=null start=null
  make up                # starts both trainer (scaled to N=1 by default) and developer
  make up N=4 service=trainer   # scale trainer to 4 replicas
  make ps
  make logs              # tail logs from all services
  ```

  Run scripts inside containers (xvfb-run applied automatically):
  - One-off ephemeral run:

    ```bash path=null start=null
    make run service=developer SCRIPT=../rl_task/PPO_trainer.py
    ```

  - Run in an existing container replica (pick INDEX for trainer):

    ```bash path=null start=null
    make exec service=trainer INDEX=1 SCRIPT=../rl_task/PPO_trainer.py
    ```

  - Open a shell:

    ```bash path=null start=null
    make bash service=developer
    ```

  Notes:
  - Inside the container, the repo is at /app; rl_task paths are /app/rl_task/...
  - PPO_trainer.py expects /app/rl_task/.env for auth (e.g., WANDB). It uses a virtual display; no host X server is required.
  - The trainer service reserves an NVIDIA GPU in compose; on machines without GPUs, training will fall back to CPU in SB3 (device=cpu).

- Formatting and linting
  The repo’s CI runs Black and Codespell. To match it locally:

  ```bash path=null start=null
  pip install black==22.6 isort codespell
  # Format (example paths; adjust as needed):
  black rl_task
  # Optionally sort imports:
  # isort rl_task
  # Spell-check (skipping large Unity bundles similar to CI):
  codespell
  ```

- Tests
  There isn’t a formal pytest suite under rl_task at the moment. The tests/ directory contains a manual keyboard-driven script. If you add pytest tests later, you can run all tests or filter to a single test with commands like:

  ```bash path=null start=null
  pytest -q
  pytest -q path/to/test_file.py -k name_substring
  ```

Unity/ML-Agents integration notes

- Editor vs build. Passing env_path=None connects to a running Unity Editor instance on the given base_port/worker_id; otherwise, supply a path to a built player (macOS .app or Linux x86_64) and batchmode can be used for headless runs.
- Side-channel parameters are set in ActiveSensingTaskRL.set_channel (e.g., camera selection, target/distractor parameters, reward sizes). Rewards and episode info are exposed via get_info and episode vectors.
- Action transformation. The RL action [move, turn] in [-1, 1] is integrated with dt=1/fps into a virtual state (x, z, heading); this is then mapped to Unity arena coordinates before being sent as a continuous ActionTuple [x, z, heading_deg, 0.0].
- Observations. The first visual observation from Unity (C, H, W) is exported as uint8 for SB3. utils.feature_extractor normalizes to ImageNet stats before MobileNet feature extraction.

Service quick reference

```bash path=null start=null
# Build
make build              # or: make build_nc

# Up/scale/stop
make up                 # starts trainer (scaled to N) and developer
make up N=3 service=trainer
make stop service=trainer
make down
make ps; make logs

# Exec/run/bash inside containers
make run service=developer SCRIPT=../rl_task/PPO_trainer.py
make exec service=trainer INDEX=1 SCRIPT=../rl_task/PPO_trainer.py
make bash service=developer

# Local run (outside Docker)
python rl_task/tests/test_rl_game_manual.py
python rl_task/rl_task_train.py
python rl_task/inference.py
```
