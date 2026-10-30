# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

FreelyMovingVR4Mice (MLAI lab) is the codebase for a freely-moving VR mouse rig. It spans three largely independent layers that only meet at the file system (pickle/npy/hdf5 files written by the rig, later ingested by the pipeline):

1. **Rig control** (`teensyexp/`, `mouse_task/`) — Python + Tkinter GUI that talks to a Teensy microcontroller over serial and drives a Unity ML-Agents game during a live session.
2. **Data pipeline** (`dj_pipeline/`) — a DataJoint/MySQL pipeline, run in Docker, that ingests rig output, runs DeepLabCut + kinematics analysis, and produces summary plots/emails.
3. **RL training** (`rl_task/`) — stable-baselines3 environments/models used offline, independent of the live rig.

Each layer has its own dependency set and, in the case of `dj_pipeline`, its own conda/Docker environment — do not assume a change in one layer needs anything from another.

## Environments

- Main package (`teensyexp` + `mouse_task`, the GUI/rig control stack): Python 3.10.12, installed from repo root (`pip install -e .`, entry point `vr4mice` → `teensyexp.teensy_experiment:main`). Requires `mlagents_envs==1.1.0` and a Unity build (`mouse_task/unity_ar/`, `mouse_task/visual_discrim_unity_build/`).
- `dj_pipeline/`: separate environment, normally run via Docker/Compose (see `dj_pipeline/Makefile`, `dj_pipeline/requirements-docker.txt`). Do not `pip install -e .` at repo root expecting it to cover this — it has its own `requirements-dev.txt`.
- `rl_task/`: separate offline training stack (root `requirements.txt` — torch, stable-baselines3, gymnasium).
- Recommended split from the README: a `vr4mice` env for the GUI/task runner, a separate `dlclive_gui` env for DeepLabCut-live-GUI/pose extraction.

## Tests

There are several independent, non-overlapping test suites — pick the right one for the code you're touching, don't assume one covers another.

- **`tests/`** (repo root) — the DataJoint pipeline test suite. Config in `tests/pytest.ini`. Uses auto-marking in `tests/conftest.py`: any test pulling in a DB/golden-data fixture (`mysql_container`, `dj_config`, `pipeline`, `clean_schemas`, `require_golden_data`, `golden_session_path`) is auto-marked `integration`, everything else `unit`; tests using `populated_db`/`populated_base_tables` are additionally marked `slow`. `unit/` tests mock out `vr4mice`/`base_schemas` modules so they run without a DB. `integration/` tests need a real MySQL and/or the golden dataset (`Flamingo_2026-02-05_1` in `dj_pipeline/tests/data/w_photodiode/`, pulled via `git lfs pull`) and skip gracefully when unavailable.
  - Run via Docker (matches CI): `cd dj_pipeline && docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests`
  - Fast subset (matches PR CI): `docker-compose -f docker-compose.test.yml run tests bash -c "cd tests && python -m pytest integration/ unit/ -m 'not slow' -v"`
  - Single file: `docker-compose -f docker-compose.test.yml run tests bash -c "cd tests && python -m pytest unit/test_helpers_dj.py -v"`
  - `slow` tests (full pipeline against the golden dataset) are excluded on PR CI and only run locally or via manual `workflow_dispatch` of `test-suite.yml`.
  - See `docs/docker_testing.md` for the full rundown and troubleshooting.
- **`mouse_task/tests/`** — unittest-style tests for the task-config registry (`mouse_task/_registry.py`), kinematics/trajectory helpers, and mouse-game logic. Run directly with `pytest mouse_task/tests/`.
- **`teensyexp/tasks_abc/tests/`** — tests for the Unity task base class. Run with `pytest teensyexp/tasks_abc/tests/`.

These three suites use no shared root pytest config — each is invoked by pointing pytest at its directory.

## Formatting & CI gates

- Format with **Black 22.6** on `dj_pipeline` before committing (`black dj_pipeline`); CI's `formatter.yml` fails the build on any diff. `isort` is referenced in the dev guide but currently commented out in CI.
- `security.yml` runs on every PR/push to main: gitleaks secret scanning, a check that no `.env`/`.env.compose`/`.env-aws`/`local_config.json` (or `.bak` variants) are tracked, and a grep-based check for internal host/IP patterns in tracked (non-notebook) files. Use the corresponding `*.example` file when adding new config, never commit the real one.
- Jupyter notebooks: outputs must never be committed (they can leak DB hosts/paths). Install the repo's `nbstripout` filter once per clone: `pip install -r dj_pipeline/requirements-dev.txt && nbstripout --install --attributes .gitattributes`.
- `docker-build.yml` only triggers on changes to `dj_pipeline/Dockerfile` / `dj_pipeline/requirements-docker.txt`; `test-suite.yml` only triggers on changes under `dj_pipeline/**` or `tests/**`.

## `dj_pipeline` architecture

DataJoint pipeline, run from the client Docker container, optionally scheduled via cron (`cron_scenario.py`). End-to-end flow:

1. **Acquisition** (rig): `.pickle` (+ optional `.npy` metadata via `gui_transfer/`).
2. **Ingest**: `run.py populate` → raw tables in `vr4mice`/`base` schemas.
3. **Analysis**: `run.py analysis` → `base_analysis` tables (`DataFrame`, `BoxDataFrame`, `GitCommit`).
4. **DLC + interpolation**: `run.py dlc` then `run.py interp` (includes `session_metrics`).
5. **Latency**: `run.py latency` → photodiode alignment tables.
6. **Environment-specific**: local server (`run.py inputs_videos`, `run.py fetch` → refreshes rig GUI dropdown) vs AWS/remote (`run.py decision --aws`, on `/data/processed`).
7. **Summaries**: `run.py summary` → `SummaryPlots` (emails sent when `EMAIL=true`).

Key directories inside `dj_pipeline/`:
- `vr4mice/schema/` — DataJoint table definitions (`vr4mice.py`, `base_analysis.py`, `dlc.py`, `interpolated_trajectories.py`, `latency_tests.py`, `session_metrics.py`, `inputs_videos.py`, `decision.py`).
- `vr4mice/analysis/` — analysis/plotting logic (`dlc_helpers.py`, `analysis.py`, `plotting.py`, `regression.py`, `stats.py`, `summary_dj.py`).
- `vr4mice/actions/` — orchestration (`populate_rig.py`, `helpers_dj.py`, `fetch_data.py`, `sync_days.py`).
- `vr4mice/utils/` — logging, DB connection, schema config, email.
- `base/base_schemas` vs `base/base_min_schemas` — full vs minimal `exp`/`mice` schema definitions (minimal used when full schemas unavailable, e.g. GUI/collab contexts); each is its own installable package (has its own `setup.cfg`), installed with `pip install --no-deps`.
- `gui_transfer/` — rig-side GUI config/data transfer; produces `gui_menu.npy`, copied to the rig at GUI startup.
- `run.py` (manual CLI) vs `cron_scenario.py` (scheduled full-pipeline run) — two entrypoints into the same underlying actions.
- `docker/entrypoint.sh` creates the runtime user (PUID/PGID) and drops privileges via `gosu`; `docker/cron_common.sh` has shared cron helpers.

Full narrative doc: `dj_pipeline/README.md` (also published in the project book).

## `teensyexp` / `mouse_task` architecture (rig control)

- `teensyexp/teensy_experiment.py` — the Tkinter GUI (`TeensyExperimentGUI`) that drives an experiment session: loads per-rig config from `system_setup.json`, builds the task parameter form via `inspect` on the task class's `__init__`, and handles Start/Save Data callbacks.
- `teensyexp/teensy.py` — serial interface to the Teensy microcontroller.
- `teensyexp/tasks_abc/task.py` — `Task` base class (informal ABC) that every task extends: owns the teensy handle, state-tracking (`move_to_state`), and the `loop()`/`get_info()`/`get_data()` contract the GUI calls into every frame.
- `teensyexp/tasks_abc/unity_task.py` — `UnityTask(Task)`, wraps a `mlagents_envs.UnityEnvironment` (ML-Agents side channels for float properties/env params), for tasks whose "game" is a Unity build.
- `teensyexp/tasks_abc/dlc_socket.py` / `dlc_deque_socket.py` — socket-based bridges to real-time DeepLabCut pose data.
- `mouse_task/task_active_sensing.py` — `ActiveSensingTask`, the concrete `UnityTask` subclass used by essentially all current task variants (detection/discrimination, with/without occluders, shape variants).

**Task variants are config-driven, not one-Python-file-per-task.** `mouse_task/_registry.py` reads `mouse_task/configs/common.yaml` (defaults for every parameter) plus one `mouse_task/configs/tasks/<name>.yaml` per variant (just the overrides + `class_name` + `description`), deep-merges them via `mouse_task.helpers.load_task_config`, and **generates** an `ActiveSensingTask` subclass per YAML with a real, `inspect`-able `__init__` signature (required because the GUI reads args/defaults via `inspect.getargspec` to build its editable parameter form). Generated classes are re-exported as `mouse_task.<ClassName>`. To add a new task variant, add a YAML under `mouse_task/configs/tasks/` — no Python required (see `mouse_task/configs/README.md`).
- `mouse_task/dlc_utils/` — DLC processor variants (`dlc_processor_socket.py`, `dlc_processor_socket_pd.py`, `dlc_processor_socket_pd_sync.py`, plus `fake_processors/` for testing without real hardware).
- `mouse_task/teensy/` — Arduino/Teensy firmware sketches (barcodes, dual water valve, photodiode reads).
- `mouse_task/latency_tests/` — standalone scripts for measuring socket/Unity/Arduino latency, not part of the main task flow.

## Governance & workflow norms (from `docs/developer_guide.md`)

- Style: Google style guide, enforced formatting via Black/isort; docstrings in PEP 257 format; `TODO(username): ...` / `NOTE(username): ...` with actionable context, not vague notes.
- Branching: GitHub Flow, **1 feature = 1 branch = 1 PR**. When branch B depends on branch A, merge A into main first before merging/rebasing B.
- Commits: conventional-commit style, small and single-purpose.
- PRs require review from a core developer before merging; all CI checks must pass; no open review conversations at merge time.
- Decision-making is consensus-seeking among core developers, escalating to the steering council on deadlock — relevant mainly if you're asked to weigh in on a design/API discussion rather than just write code.
