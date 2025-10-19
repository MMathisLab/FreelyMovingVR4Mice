# RL Task (Active Sensing) — Docker + Makefile Guide

This folder contains the reinforcement learning stack for training agents on the Unity `Active Sensing` task. It includes:

- Dockerfile and Compose setup for a reproducible, GPU-enabled environment
- A Makefile with convenience targets to build, run, and manage containers
- Training/evaluation scripts (`PPO.py`, `RecurrentPPO.py`, `inference.py`)
- A Compatibility wrapper around the active sensing class, yielding a new `ActiveSensingTaskRL` class
- A Gymnasium wrapper around the rl task allowing training of reinforcement learning agents using common libraries and frameworks such as `stable baselines 3`, `RLlib`, and `CleanRL`

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU + drivers and `nvidia-container-toolkit` installed (for GPU training)
- Unity build present at `rl_task/AR_build/augmented_reality.x86_64`

## Required Environment Variables

Place runtime settings used by the scripts in `rl_task/.env`:

- `VR4MICE_PATH=/path/to/FreelyMovingVR4Mice` (used as mounted volume for container to have access to all necessary components)
- `UNITY_ENV_PATH=/app/rl_task/AR_build/augmented_reality.x86_64` (default used in scripts)
- `MODEL_DIR=/app/rl_task/models`
- `CHECKPOINT_PATH=/app/rl_task/models/.../model.zip` (if resuming)
- `LOAD_CHECKPOINT=true|false`
- Optional: `WANDB_API_KEY=<your-key>` (or run `wandb login` inside the container)

Disclaimer: the above paths are relative the container's file structure.

Your `.env` file inside the `rl_task/` directory should look something like the following:

```
# .env

VR4MICE_PATH=...      # path to the FreelyMovingVR4Mice repo
UNITY_ENV_PATH=...    # path to the Unity executable
MODEL_DIR=...         # location where to save model checkpoints
CHECKPOINT_PATH=...   # location of checkpoint from which to resume training
LOAD_CHECKPOINT=...   # whether to load a checkpoint or start fresh
WANDB_API_KEY=...     # allows easier integration with wandb
```

Notes:

- When running via Compose, `/app` is a bind mount of `VR4MICE_PATH`, so model outputs under `/app/rl_task/models` persist on the host.
- Ensure the Unity executable has the executable bit set (`chmod +x`).


## Contents

- `Dockerfile`: CUDA‑based image with Python, PyTorch, SB3, and dependencies
- `docker-compose.yaml`: Two services — `trainer` (heavier GPU training) and `developer` (light, interactive work)
- `Makefile`: Shortcuts for build, start/stop, scaling, logs, and launching scripts
- `requirements.txt`: Python dependencies for the RL stack
- `AR_build/`: Unity build folder; expected to contain `augmented_reality.x86_64` [*]
- `scripts/`: Entry points for training and evaluation
  - `PPO_trainer.py`, `RecurrentPPO_trainer.py`, `inference.py`
- `task/`: Python package
  - `envs/rl_task_active_sensing.py`: RL‑friendly facade over the active sensing task process
  - `envs/rl_task_gym_wrapper.py`: Gymnasium adapter with reward shaping and episode tracking
  - `utils/env_factory.py`: Builds Dummy/Subproc vectorized envs + `VecMonitor`
  - `extractors/`: SB3-compatible feature extractors
- `config/`: Config presets and loader
  - `rl_experiments.yaml`: Defaults and named presets (e.g. `shape_discrim`, `*_occluders`)
  - `config.py`: Typed config + `load_config(...)` merger
- `models/`: Output directory for saved models and evaluation `.npz` files [*]
- `logs/` : Output directory for training logs [*]

[*] : Need to be added by the user. Not available by default.

## Build the Image

The Makefile wraps Docker Compose and injects your user/uid/gid for correct file permissions inside containers.

- Build services: `make build`
- Build without cache: `make build_nc`

Note: both of the above commands only build the `trainer` service since the `developer` relies on the same Dockerfile.

Under the hood this runs: `docker compose -p <project> build` with build args:

- `uid`, `gid`, `user_name` (autodetected from the host)

## Run Containers

- Start both services (default): `make start`
  - Start with N trainer replicas: `make start N=2`

- Start a specific service:
  - `make start service=trainer N=3`
  - `make start service=developer`

Useful management commands:

- List containers: `make ps`
- Tail logs (all or specific service): `make logs` or `make logs service=trainer`
- Stop a service: `make stop service=trainer` (or `developer`)
- Stop and remove all: `make terminate`
- Resource stats: `make stats`

## Run Training and Evaluation

Execute a test run inside a running service:

- `make run_test service=trainer INDEX=...`
- `make run_test service=developer`

Run inside an existing container (good when you have scaled replicas):

- `make run service=trainer INDEX=... SCRIPT=...`
- `make run service=trainer SCRIPT=...`

Note: the scripts available to the above two commands are the ones located at `rl_task/scripts/` only. Script lookup base is `/app/scripts`, so pass just the filename via `SCRIPT=...`.

Open a shell in a running container:

- `make bash service=developer`
- `make bash service=trainer INDEX=...`

## Available scripts

- `scripts/PPO_trainer.py`: Trains a PPO agent using Stable‑Baselines3 on the Unity task. Creates vectorized envs via `utils/env_factory.make_env`, logs to W&B, and saves checkpoints under `MODEL_DIR`.
- `scripts/RecurrentPPO_trainer.py`: Same workflow using `sb3_contrib.RecurrentPPO` with custom visual feature extractors defined in `task/extractors`.
- `scripts/inference.py`: Loads a trained PPO/RecurrentPPO model and runs several evaluation episodes, printing return and length statistics.

Each trainer reads `/app/rl_task/.env` and uses presets from `config/rl_experiments.yaml`. Adjust algorithm and policy kwargs directly in the scripts for experiments.

## Python Package Overview

- `task/envs/rl_task_gym_wrapper.py`: Gymnasium wrapper that translates Unity’s ternary rewards {−1,0,+1} into shaped rewards and enforces local episode caps.
- `task/envs/rl_task_active_sensing.py`: RL‑oriented wrapper over the underlying Unity task; handles start/reset/step, action kinematics, and episode bookkeeping.
- `task/utils/env_factory.py`: Builds single or multi‑process vectorized environments (`DummyVecEnv`/`SubprocVecEnv`) and wraps with `VecMonitor`.
- `task/extractors/`: Feature extractors for visual observations (vanilla/depthwise conv stacks, MobileNetV3 features).
- `config/rl_experiments.yaml`: Defaults + named presets for different tasks (contrast/shape discrim variants, with/without occluders).
- `config/config.py`: Pydantic model and loader that merges defaults, a preset, and runtime overrides.

## Tips and Troubleshooting

- GPU access: Compose requests NVIDIA devices; install `nvidia-container-toolkit` and ensure Docker can see GPUs. If GPUs aren’t detected, training falls back to CPU.
- Unity ports: Each vectorized env uses `base_port` and increments by worker id. If you scale multiple trainer containers, avoid port collisions by modifying the scripts to offset `base_port` per replica (or run single trainer container when using many envs).
- W&B auth: Export `WANDB_API_KEY` in `rl_task/.env` or run `wandb login` inside the container before training.
- File permissions: The Makefile passes your uid/gid so that files written under the bind mount `/app` are owned by your host user.
- Unity build file: If you update `AR_build/`, ensure it is executable. You can do so by running in a terminal window the following command: `chmod +x path/to/executable.x86_64`

## Quick Start

1) Create `rl_task/.env` with:

- `UNITY_ENV_PATH=/app/rl_task/AR_build/augmented_reality.x86_64`
- `MODEL_DIR=/app/rl_task/models`
- `LOAD_CHECKPOINT=false`
- `VR4MICE_PATH=/host/path/to/FreelyMovingVR4Mice/repository`

2) Build and start:

- `make build`
- `make start service=trainer`

3) Launch training:

- `make run service=trainer INDEX=1 script=PPO_trainer.py`

4) Models and eval logs appear under `rl_task/models/` on the host.
