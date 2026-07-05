(sec:install-dj-pipeline)=
# Setup & Usage

## Overview
The VR4Mice pipeline is a DataJoint-based workflow for ingesting raw rig data,
computing analysis tables, running DLC and interpolation, and generating summary outputs.
It is designed to run from the client container and can be scheduled via cron.

## End-to-end workflow (data acquisition → emails)
1. **Acquisition (rig)**: `.pickle` files (and optional `.npy` metadata via `gui_transfer/`).
2. **Ingest**: `run.py populate` → raw tables in `vr4mice`/`base`.
3. **Analysis**: `run.py analysis` → `base_analysis` tables (`DataFrame`, `BoxDataFrame`, `GitCommit`).
4. **DLC + interpolation**: `run.py dlc` then `run.py interp` (includes `session_metrics` tables).
5. **Latency**: `run.py latency` → photodiode alignment tables.
6. **Environment-specific** (manual or via `cron_scenario.py`):
   - **Local server**: `run.py inputs_videos`, then `run.py fetch` → refreshes `/shared/gui_menu.npy` for the rig GUI.
   - **AWS / remote** (`--aws`): `run.py decision` on `/data/processed`.
7. **Summaries**: `run.py summary` → `SummaryPlots` for sessions with both `DataFrame` and `BoxDataFrame`; cron also runs `summary_emails.send_pending_summary_emails` to send or retry plot notification emails (see [Emails](#emails)).

**After upgrading to DataJoint 2.x** (once per rig, before relying on cron):

```bash
python run.py maintenance
```

This rebuilds DataJoint lineage tables for all pipeline schemas (including `summary_emails`). Normal cron runs do not replace this step.

## Repository layout (dj_pipeline)
- `run.py`: manual CLI entrypoint for running pipeline modes (user mode).
- `cron_scenario.py`: scheduled runner for full pipeline execution (crontab call).
- `vr4mice/`: core schema, analysis, and action code.
- `gui_transfer/`: GUI configuration and data transfer tools.
- `base/`: base schemas and actions (full and minimal modes: mice, exp tables, connections and email functions).
- `backup/`: backup helpers (local/remote sync scripts).
- `cron_*.sh`: cron wrappers for scheduled runs (standard, reboot, AWS).
- `Dockerfile` + `requirements-docker.txt`: client image build and pinned runtime dependencies.
- `docker/entrypoint.sh`: creates runtime user (PUID/PGID) and drops privileges with `gosu`.
- `docker/cron_common.sh`: shared helpers for cron scripts and compose exec.
- `generators/`: small utilities to create helper tables/files (e.g., add mice).
- `parse_mice/`: parsing helpers for mouse metadata files.
- `mysql_access/`: SQL templates for user setup.
- `notebooks/`: analysis and figure notebooks (research use).
- Logs are written on the **server** in a local `logs/` folder and are not part of the repo.

## vr4mice module guide

See [vr4mice/README.md](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/dj_pipeline/vr4mice/README.md). Key components:

- `schema/`: DataJoint table definitions.
- `analysis/`: analysis helpers and plotting.
- `actions/`: orchestration helpers (ingest, sync, fetch).
- `utils/`: logging, schema config, bootstrap, `populate_helpers`, `maintenance`.

### `gui_transfer`
Rig GUI and transfer utilities:
- `gui.py` + `config/` for metadata capture.
- `utils/` and `modules/` for GUI logic.
- Dropdown menu file (`gui_menu.npy`) generated on the server by `fetch_data.py` and copied to the rig at GUI startup (see {ref}`GUI dropdown menu and rig setup <gui-dropdown-menu>`).

### `base` (schemas)
- `base_schemas`: full `exp` and `mice` schema definitions.
- `base_min_schemas`: minimal `exp`/`mice` for GUI + collab when full schemas are not available.

## Getting Started — For Everyday Users
This quick guide helps you connect to the database and run the pipeline without deployment experience.

### Requirements
- Bash
- Docker + Docker Compose
- GNU Make
- Database credentials (host/port, user, password)

### Quick start (recommended)
Use the interactive setup script to configure `.env`/`env.py` and start containers:
```bash
bash quick_start.sh
```

### Quick start — client mode (connect to an existing DB)
Use when the database already runs elsewhere.
```bash
bash quick_start.sh
```
Choose:
- **Mode**: `client`
- **DJ host**: `ip:port` or hostname (e.g., `127.0.0.1:3309`)
- **DJ user / DJ password**

This starts only the client container.

### Quick start — deployment mode (DB + client on server)
Use when deploying both database and client containers on a server.
```bash
bash quick_start.sh
```
Choose:
- **Mode**: `deployment`
- Provide mount paths for database, data, shared, and screen recordings
- Set DB bind IP/port and MySQL root password

Defaults shown by the script:
- `/mnt/database/vr4mice/vr4mice_database/database` → `/var/lib/mysql`
- `/mnt/database/shared` → `/shared`
- `/mnt/database/vr4mice/vr4mice_database/data` → `/data`
- `/mnt/neuropixel_data/vr4mice/raw_screen_recordings` → `/vr4mice_screen_recordings`
- repo root (`./`) → `/app`
- `./base/base_min_schemas` → `/base_schemas`
- `./base/base_actions` → `/base_actions`

### Quick start — import DB dumps
Use this when you have `restricted_dump_*.sql` files or a `.zip`/`.tar.gz` archive.
```bash
bash quick_start.sh
```
When prompted:
- **Import DB dumps now?** → `yes`
- **Dump directory or .zip/.tar.gz archive** → path to the dump folder or archive

The script creates missing databases and imports each `restricted_dump_*.sql`.
Imports stay in the foreground and show progress (via `pv` or `dd status=progress`
when available).

### Step 1 — Clone the repo
```bash
git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
cd dj_pipeline
```

### Step 2 — Configure credentials
Update your credentials in `.env` (or `env.py` for local conda runs).
```bash
vim .env
```

### Step 3 — Start the client container
```bash
make client_build
make client_up
```

### Step 4 — Connect via IPython or Jupyter
```bash
make ipython
%run run.py connect
```

Optional Jupyter:
```bash
make notebook
```

Remote Jupyter via SSH tunnel:
```bash
ssh -NL 8887:localhost:8887 <user>@<server>
```
Append `&` if you want the tunnel in the background.
You can add an SSH config alias (e.g., `wm`) and then connect with:
```bash
ssh -NL 8887:localhost:8887 wm
```

### Step 5 — Verify connection
```python
from vr4mice.schema import vr4mice
vr4mice.Dataset()
```

### Stop the client
```bash
make client_down
```


#### Jupyter / IPython access (recommended: Docker client)

Use `make notebook` or `make ipython` in the client container — dependencies match `requirements-docker.txt` (DataJoint 2.x).

#### Host Jupyter (legacy / outside Docker)

1. Install matching packages and base schemas:
   ```bash
   pip install notebook "datajoint>=2.0.1"
   pip install base/base_actions/
   pip install base/base_min_schemas/
   ```
2. Install graphviz if you want schema diagrams: `sudo apt install -y graphviz`
3. Update `env.py` (server IP, credentials from your administrator)
4. Start `jupyter notebook`, open a Python 3 kernel, then:
   ```python
   %run env.py
   %run run.py connect
   from vr4mice.schema import vr4mice
   vr4mice.Dataset()
   ```


## Deployment (server)

### Server deployment (database + client containers)
The server runs two containers:
- **Database** (MySQL/DataJoint)
- **Client** (pipeline runner)

Note: store MySQL admin credentials in `~/.my.cnf` on the server.
```bash
make build_all
make up_all
make mysql
make ipython
%run run.py connect
```

(docker-client-base-packages)=
### Docker client: base packages and user mapping

The client image is built from DeepLabCut’s Docker image. Build-time Python dependencies are pinned in `requirements-docker.txt` and installed by `Dockerfile` (`pip install -r requirements-docker.txt`). Pipeline commands use plain `python -m pip` (**no** `conda activate`). At build time and container start, `docker/ensure_python_shims.sh` symlinks the base image’s Python into `/usr/local/bin` so `make`, cron, and `docker compose exec` all find `python` on the compose `PATH`.

**`base_schemas` / `base_actions`** are bind-mounted from the repo and installed at runtime with pip:

```bash
python -m pip install --user --no-deps /base_schemas/
python -m pip install --user --no-deps /base_actions/
```

`make client_up`, `make base_install`, and the cron scripts run pip as the caller's UID/GID; packages and cache live under `/app/.local` and `/app/.cache/pip` on the bind-mounted repo (not under `/home/<username>`), so any user with access to the repo can run the client.

**Running as your host user** (file permissions on `/app`, `/data`, etc.) is handled by Docker, not conda:

| Layer | Mechanism |
|-------|-----------|
| Container start | `docker/entrypoint.sh` — `useradd` with `PUID`/`PGID`/`USERNAME`, then `gosu` |
| Compose | passes `UID`, `GID`, `USER_NAME` from the host (`Makefile` exports these) |
| `make` / cron exec | `docker compose exec --user "$(UID):$(GID)" client …` |

**Host conda** (`env.py`, `vr4mice_env` on the rig, DLCliveGUI) is a separate install path for non-Docker workflows. It is not used inside the client container.

### Mounts and storage
In `docker-compose.yml`, map host storage for database and data volumes:
- `/data` and `/data/summary_plots` must exist and be writable.
- `/shared` is used for GUI menu exports.
- Use persistent paths (e.g., `/mnt/database/...`) on the server.
Network mode:
- Default is `host`. Set `CLIENT_NETWORK_MODE=bridge` in `.env.compose` if you need bridge networking.

(deployment-defaults)=
### Deployment defaults (quick_start.sh)
When using `bash quick_start.sh` in **deployment** mode, the default host paths map to:
- `/mnt/database/vr4mice/vr4mice_database/database` → `/var/lib/mysql`
- `/mnt/database/shared` → `/shared`
- `/mnt/database/vr4mice/vr4mice_database/data` → `/data`
- `/mnt/neuropixel_data/vr4mice/raw_screen_recordings` → `/vr4mice_screen_recordings`
- repo root (`./`) → `/app`
- `./base/base_min_schemas` → `/base_schemas`
- `./base/base_actions` → `/base_actions`

### Database deployment notes (server)
- Add user to Docker group:
  ```bash
  sudo usermod -aG docker <username>
  ```
- Create host storage paths (example):
  ```bash
  mkdir -p /mnt/database/vr4mice/vr4mice_database/database
  mkdir -p /mnt/database/vr4mice/vr4mice_database/data
  mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/data
  mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/dlc_video
  mkdir -p /mnt/database/vr4mice/vr4mice_database/data/summary_plots
  mkdir -p /shared
  ```
- Add MySQL credentials in `~/.my.cnf` for `make mysql`:
  ```ini
  [client-vr4mice]
  host=127.0.0.1
  user=root
  password=simple
  port=3309
  ```
### Environment variables

**Pipeline** (`.env` — copy from `.env.example`; loaded into the client container):

- `DJ_HOST` (include port, e.g. `127.0.0.1:3309`), `DJ_USER`, `DJ_PWD`
- `DJ_LAB`, `GUI`, `EMAIL`, `IMG_SRC`, `VR4MICE_EMAIL_RECIPIENTS`, `VR4MICE_EMAIL_SINCE`

When using the local Docker database, `DJ_HOST` port must match `DB_PORT` in `.env.compose`.

**Docker Compose** (`.env.compose` — copy from `.env.compose.example`; used by `make`, cron, and `docker compose` only):

- `COMPOSE_PROJECT` (default `vr4mice`) — must match between `make`, cron scripts, and manual `docker compose -p …` calls
- `DB_BIND_IP`, `DB_PORT`, `MYSQL_ROOT_PASSWORD`
- `DB_DATA_PATH`, `SHARED_PATH`, `DATA_PATH`, `SCREEN_RECORDINGS_PATH`
- `DB_IMAGE` — Docker image for the local database service (see below)
- `CLIENT_IMAGE`, `CLIENT_CONTAINER_NAME`, `DB_CONTAINER_NAME`, `CLIENT_NETWORK_MODE`, `JUPYTER_PORT`

(sec:mysql-version)=
#### MySQL version (5.7 and 8.0)

The database service in `docker-compose.yml` uses `${DB_IMAGE:-mysql:8.0}`.

| Situation | What to use |
|-----------|-------------|
| New install (empty `DB_DATA_PATH`) | `mysql:8.0` (default) |
| Existing on-disk datadir from MySQL 5.7 | `mysql:5.7` |

If `DB_IMAGE` is **not** set in `.env.compose`, `docker/compose_env.sh` (used by `make` and cron) auto-detects the image from `DB_DATA_PATH` via `docker/detect_mysql_image.sh`. `quick_start.sh` writes the detected value into `.env.compose`.

Manual override in `.env.compose`:

```bash
DB_IMAGE=mysql:5.7   # legacy datadir
# DB_IMAGE=mysql:8.0 # new installs
```

Check what Compose will use:

```bash
bash docker/compose_env.sh get DB_IMAGE
```

**Upgrading 5.7 → 8.0** (keep data): run MySQL 5.7 against the datadir, shut down cleanly, then switch to 8.0:

```bash
docker compose exec db mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" \
  -e "SET GLOBAL innodb_fast_shutdown=0; SHUTDOWN;"
# set DB_IMAGE=mysql:8.0 in .env.compose, then:
make up_all
```

**Fresh start** (discard local datadir): stop the stack, move or delete `DB_DATA_PATH`, then start with `DB_IMAGE=mysql:8.0`.

If the `db` container exits immediately with code 1 and logs mention a failed upgrade from MySQL 5.7, the datadir version likely does not match `DB_IMAGE` — set `DB_IMAGE=mysql:5.7` or wipe the datadir for a new 8.0 install.

Remote/AWS DB credentials for scheduled AWS runs live in `.env-aws` (copy from `.env-aws.example`); this file is **not** committed.

If you still have Docker settings in `.env` from an older setup, move them to `.env.compose` (Makefile falls back to `.env` for `COMPOSE_PROJECT` only during migration).

Notes:
- `VR4MICE_EMAIL_RECIPIENTS` is required if base schemas (exp/mice) are not in use,
  because experimenter names are otherwise missing from GUI metadata.
- `VR4MICE_EMAIL_SINCE` (format `YYYY-MM-DD`) limits automatic summary emails to **new**
  sessions on or after that date. If unset, cron does not send summary emails (avoids
  emailing the full backlog). Set this on the rig when enabling `EMAIL=true`.

### Schemas (what they do)
- `vr4mice`: core tables for datasets, raw signals, metadata, and derived features.
- `base`: links datasets to `exp` and `mice` schema information.
- `base_analysis`: analysis outputs and summary plots.
- `summary_emails`: tracks summary plot notification emails (`SummaryPlotEmail`).
- `dlc`, `interpolated_trajectories`, `latency_tests`, `decision`, `inputs_videos`: downstream analysis modules.

### Schema modes
Two base schema modes are supported:
- **Full base schemas**: `base_schemas` (exp/mice full definitions).
- **Minimal schemas**: `base_min_schemas` (minimal exp/mice for collab + basic metadata).

Both modes work; choose minimal when only GUI dropdowns and basic metadata are needed.

### Data import/export (restricted dumps)
See {ref}`Data import/export <sec:data-import-export>` for export/import workflows, or:

- Exporting restricted dumps (`export_restricted_dump.sh`)
- Importing dumps with `quick_start.sh`
- Manual mysql import

See {ref}`Deploy the DataJoint database locally <sec:import-sql-dump>` for a full local deploy workflow that clones the data archive, runs quickstart, and connects Jupyter.


## GUI vs non-GUI mode
- **GUI mode** (`GUI=true`): expects `.pickle` + `.npy` inputs.
- **Non-GUI** (`GUI=false`): uses `.pickle` only; metadata is reconstructed as needed.
Use GUI mode when experiment metadata is collected via the rig GUI.

(gui-dropdown-menu)=
## GUI dropdown menu and rig setup

The rig GUI (`gui_transfer/`) uses a DataJoint-exported `.npy` file for dropdown menus (mice, experimenters, rigs, tasks, etc.). The file is generated on the **pipeline server** and copied to the **rig** when the GUI starts.

### Server: generate the menu file

| Item | Default path / value |
|------|----------------------|
| Menu output (in container) | `/shared/gui_menu.npy` |
| Host mount | `SHARED_PATH` in `.env.compose` → `/shared` in the client container |
| Generator script | `vr4mice/actions/fetch_data.py` |
| CLI entrypoint | `run.py fetch` |

Generate or refresh the menu manually (inside the client container or via Jupyter):

```bash
python run.py fetch
```

This queries `exp` / `mice` tables and writes `/shared/gui_menu.npy`. On **local** (non-AWS) cron runs, `cron_scenario.py` executes this as the **final** step after populate, analysis, DLC, and `inputs_videos` tables. AWS cron runs do not export the GUI menu.

Ensure the shared directory exists on the host (see {ref}`Deployment defaults <deployment-defaults>`):

```bash
mkdir -p /mnt/database/shared   # or your SHARED_PATH
```

### Rig: configure paths and fetch the menu

1. Copy `gui_transfer/` to the rig computer.
2. Install Python 3 + PyQt5 (`make env` from `gui_transfer/`).
3. Create the GUI config from the template (do not commit the result):
   ```bash
   cp gui_transfer/config/local_config.json.example gui_transfer/config/config.json
   ```
4. Edit `gui_transfer/config/config.json`. Key fields for the dropdown menu:

   | Key | Purpose | Example |
   |-----|---------|---------|
   | `ip` | Pipeline server IP (`localhost` for local testing) | `192.168.1.10` |
   | `host` | SSH user on the server (empty if not needed for `localhost`) | `vr4mice` |
   | `remote_dropdown_menu` | Path to menu file **on the server** | `/shared/gui_menu.npy` |
   | `host_dropdown_menu` | Local copy path on the rig | `./gui_menu.npy` |

   On startup, `config.get_menu_path` (a property on the `Config` instance) copies the menu file to the rig:
   - **`localhost`**: local file copy from `remote_dropdown_menu` to `host_dropdown_menu` (both paths must be readable on the same machine)
   - **remote server**: `scp host@ip:remote_dropdown_menu` → `host_dropdown_menu` (requires SSH access and the menu file on the server)

   Also set transfer paths (`remote_dst`, `gui_output_folder`, `teensy_path`, `processed_path`, etc.) for your rig layout. See the inline example in `gui_transfer/config/config.py`.

5. Start the GUI:
   - Linux: `make run_gui` from `gui_transfer/`
   - Windows: use the provided batch file example and adjust paths.

If the menu file is missing or `scp` fails, the GUI logs a warning and exits — fix paths/credentials and ensure `run.py fetch` has been run on the server before restarting the GUI.

Further GUI module details: `dj_pipeline/gui_transfer/README.md`.

The GUI transfers **experiment metadata** and rig files only (videos stay on the rig).

## Manual runs (run.py)

Use `--verbose` for DEBUG logging and DataJoint lineage details (cron stays quiet by default).

Typical sequence:
```bash
%run run.py populate
%run run.py analysis
%run run.py summary
%run run.py fetch    # refresh GUI dropdown menu on /shared
...
```

One-off after a DataJoint upgrade or when adding a new schema:

```bash
%run run.py maintenance
```

## Testing / quick sanity
- Populate test:
  ```python
  %run run.py populate
  from vr4mice.schema import vr4mice
  vr4mice.Dataset()
  ```
- Analysis test:
  ```python
  %run run.py analysis
  ```

(cron-and-docker)=
## Cron and Docker operations

Scheduled pipeline runs use wrapper shell scripts that call `docker compose` with project name **`vr4mice`** (override via `COMPOSE_PROJECT` in `.env.compose` or the environment). Shared logic lives in `docker/cron_common.sh`.

### Architecture

| Component | Role |
|-----------|------|
| `cron_scenario.py` | Runs populate → analysis → DLC → … with per-step logging; exits non-zero if any step fails |
| `docker/cron_common.sh` | Shared compose/exec helpers (project name, UID/GID, pip install) |
| `cron_script.sh` | Local nightly run (`/data/data`, video tables, shared export) |
| `cron_script_aws.sh` | AWS/remote run (`/data/processed`, decision tables); requires `.env-aws` |
| `cron_script_reboot.sh` | After host reboot: wait 120s, start `db` + `client`, install base packages |
| `Makefile` | Same compose project and exec pattern as cron scripts |

**Docker client vs host conda:** the client container uses system Python + pip (DeepLabCut base image). Conda on the rig or laptop (`env.py`, `vr4mice_env`, DLCliveGUI) is a separate install path and is not used inside the Docker client. Base package install and user mapping are described under {ref}`Docker client: base packages and user mapping <docker-client-base-packages>`.

### Makefile targets (common)

| Target | Purpose |
|--------|---------|
| `make client_up` | Start client, install `base_schemas` / `base_actions` |
| `make up_all` | Start `db` + `client`, install base packages |
| `make base_install` | Re-install base packages in running client |
| `make ipython` / `make notebook` | Interactive session in client |
| `make add-cron` | Install/update crontab entries (see below) |
| `make cron-local` | Manual local cron run |
| `make cron-aws` | Manual AWS cron run |
| `make cron-reboot` | Manual reboot startup script |

All compose commands use `docker compose -p vr4mice` by default (`COMPOSE_PROJECT` in `Makefile` / `.env.compose`).

### Crontab setup

From `dj_pipeline/` on the server:

```bash
make add-cron
```

This merges (does not wipe) your crontab and registers:

| Schedule | Script | Log |
|----------|--------|-----|
| `@reboot` | `cron_script_reboot.sh` | `~/vr4mice_logs/cron_reboot.log` |
| `0 2 * * *` | `cron_script.sh && cron_script_aws.sh` | `~/vr4mice_logs/cron.log` then `~/vr4mice_logs/cron_aws.log` |

The nightly job runs **local first**; **AWS runs only if local exits successfully** (`&&` chain). `cron_scenario.py` must exit 0 (no failed steps) for AWS to start.

### Prerequisites on the server

1. `.env` — pipeline / DataJoint credentials (see `.env.example`)
2. `.env.compose` — Docker Compose settings (see `.env.compose.example`)
3. `.env-aws` — remote DB credentials for AWS runs (see `.env-aws.example`)
4. Docker daemon running; cron user in the `docker` group
5. Run `make add-cron` from `dj_pipeline/` (paths are resolved from that directory)

### Manual test (before enabling cron)

```bash
cd dj_pipeline
make cron-local && make cron-aws
# or:
bash cron_script.sh && bash cron_script_aws.sh
```

### Migrating compose project name

Older setups may have containers under project `mysqltest`. After updating:

```bash
COMPOSE_PROJECT=mysqltest make down_all   # stop old stack
```

Then start with your project name in `.env.compose` (or legacy `COMPOSE_PROJECT=mysqltest make up_all` if you have not migrated yet).

### Multiple deployments on one server

Other `vr4mice_*` compose projects on the same host are **fine** for the primary stack (`COMPOSE_PROJECT=vr4mice`) as long as **container names** and **`DB_PORT`** do not clash.

`make check-compose-project` blocks only real collisions:

- container names (`vr4mice_db`, `vr4mice_${USER}`) already used by another compose project
- host port (`DB_PORT`, default `3309`) already in use by another stack

For a **second** deployment (sandbox / personal DB), use unique values in `.env.compose`:

```bash
COMPOSE_PROJECT=vr4mice_dev
DB_CONTAINER_NAME=vr4mice_db_dev
CLIENT_CONTAINER_NAME=vr4mice_${USER}_dev
DB_PORT=3310
DB_DATA_PATH=/path/to/dev/database/
DATA_PATH=/path/to/dev/data/
```

Use separate data paths so MySQL volumes do not overwrite each other.

To skip the check (not recommended): `VR4MICE_COMPOSE_FORCE=1 make up_all`.

### Shared repo checkout (another user, same server)

When the pipeline lives in a **shared folder** (e.g. `/mnt/database/shared/FreelyMovingVR4Mice/dj_pipeline`) and was first set up under someone else's account:

**Do not** run `git config --local user.*` in that tree — it is stored inside `.git/` and affects everyone using the same checkout. Prefer per-session env vars or a personal clone for heavy git work.

#### Git — use your own credentials

There is **no** `make` target that changes GitHub SSH keys (those live in `~/.ssh/`). Use:

| Command | Purpose |
|---------|---------|
| `make git-whoami` | Show remote, local/global git name, env overrides |
| `eval "$$(make git-user-env NAME='…' EMAIL='…')"` | Set identity **for this shell only** (shared checkout) |
| `make git-user-local NAME='…' EMAIL='…'` | Set `--local` config (personal clone only; affects all users on a shared tree) |

SSH remotes use **`~/.ssh/` of the logged-in user**, not the repo owner. As the new user:

```bash
cd /path/to/shared/FreelyMovingVR4Mice/dj_pipeline

make git-whoami
ssh -T git@github.com

# Shared checkout (recommended):
eval "$$(make git-user-env NAME='Your Name' EMAIL='you@example.com')"
git pull
```

Personal clone only:

```bash
make git-user-local NAME='Your Name' EMAIL='you@example.com'
```

If `git pull` / `git push` fails with permissions on `.git/`, ask the admin to fix group write access on the repo, or **clone your own copy** elsewhere:

```bash
git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git ~/FreelyMovingVR4Mice
cd ~/FreelyMovingVR4Mice/dj_pipeline
```

#### Docker — client under your username

Each user should have their **own client container** and (if needed) **compose project**. Production DB is often shared; client containers are per user.

**Client only** (connect to an existing DB — typical on a shared server):

```bash
cd /path/to/shared/FreelyMovingVR4Mice/dj_pipeline

# Per-user compose project (avoids clashing with others' containers) — in .env.compose or export:
export COMPOSE_PROJECT="vr4mice_${USER}"

# Pipeline credentials stay in .env (or export DJ_* if the shared .env is not yours)

make check-compose-project
make client_up          # container name defaults to vr4mice_${USER}
make ipython
```

**Full stack** (your own DB + client — dev / sandbox):

```bash
cd /path/to/shared/FreelyMovingVR4Mice/dj_pipeline

export COMPOSE_PROJECT="vr4mice_${USER}"
export DB_PORT=3310     # pick a free port; check with: ss -ltn | grep 3309

# Point to your own data dirs in .env.compose (or quick_start.sh), then:
make check-compose-project
make up_all
```

To persist settings, add to `.env.compose` (file is gitignored):

```bash
COMPOSE_PROJECT=vr4mice_${USER}
CLIENT_CONTAINER_NAME=vr4mice_${USER}
# DB_CONTAINER_NAME / DB_PORT / DB_DATA_PATH only if you run your own database
```

Stop **your** client without touching others:

```bash
COMPOSE_PROJECT=vr4mice_${USER} make client_down
```

### AWS mode (pipeline behaviour)
`--aws` mode uses `/data/processed` and disables moving raw files.
- `run.py --aws populate`
- `cron_scenario.py --aws`

## Backup and AWS sync
Backup helpers live in `backup/` and cron scripts:
- `backup/backup.sh`
- `cron_script_aws.sh`

These scripts are intended for **append-only** sync to AWS or remote storage.
If older versions should be replaced, manual cleanup may be required before re-populating.
Update paths and credentials to match your storage backend.

## Error handling and FailedSession
Failures are recorded in `vr4mice.FailedSession` keyed by `(dataset, failed_table_name)`:
- Used as a **per-table** skip list during `populate_pending` (a photodiode skip does not block `SummaryPlots`).
- Some entries are intentional permanent skips (e.g. no photodiode signal, no trials after excluding initialization trial 1).
- Remove entries to retry after fixing data or deploying a fix.

Example removal (one table):
```python
from vr4mice.schema import vr4mice
(vr4mice.FailedSession() & 'dataset="Grizzly_2026-01-29_1"' & 'failed_table_name="DataFrame"').delete()
```

Bulk cleanup after duplicate-key fixes:
```python
(vr4mice.FailedSession() & 'failed_table_name="SignalsPhotodiode"' & 'error_message LIKE "%Duplicate entry%"').delete()
```
## GitCommit table
`base_analysis.GitCommit` stores commit hash and modified files for provenance.

## Emails
Summary emails are sent when `EMAIL=true` **and** `VR4MICE_EMAIL_SINCE` is set.

Recipients are derived from:
1. `VR4MICE_EMAIL_RECIPIENTS` (experimenter names)
2. `exp.Session` experimenter (if available)

**Tracking and retry:** the `summary_emails` schema stores one row per send attempt in
`SummaryPlotEmail` (timestamp, recipients, error if any). After `SummaryPlots` populate,
cron calls `send_pending_summary_emails` to send or retry emails for eligible sessions
(those with a plot row, on/after `VR4MICE_EMAIL_SINCE`, and no successful send yet).

Inspect pending or sent emails:
```python
from vr4mice.schema import summary_emails
summary_emails.pending_summary_email_keys()
(summary_emails.SummaryPlotEmail() & "send_error IS NULL").fetch()
```

## Logs
Runtime logs are written to the local `logs/` folder on the server/container.
Cron logs per-step timing (`[cron] start/done …`) at INFO; routine skip and duplicate
messages are DEBUG unless you run with `--verbose`.
