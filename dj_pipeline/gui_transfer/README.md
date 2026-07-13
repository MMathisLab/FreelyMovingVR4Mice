# Transfer GUI (`gui_transfer`)

PyQt5 GUI for capturing experiment metadata on the rig and transferring session files to the pipeline server. Videos remain on the rig; the GUI queues `.pickle`, `.npy`, and related rig outputs.

**Full setup** (server menu export, SSH/`scp`, path layout): [Setup & Usage — GUI dropdown menu and rig setup](../../docs/software/install_dj_pipeline.md#gui-dropdown-menu-and-rig-setup).

## Deployment checklist

Use this order on a **new rig** or when replacing an old `-aux` checkout:

| Step | Where | Action |
|------|-------|--------|
| 1 | Pipeline server | Deploy `FreelyMovingVR4Mice/dj_pipeline` (see main [install guide](../../docs/software/install_dj_pipeline.md)) |
| 2 | Pipeline server | Ensure `/shared` exists and is writable (`SHARED_PATH` in `.env.compose`) |
| 3 | Pipeline server | Refresh dropdown menu: `python run.py fetch` → writes `/shared/gui_menu.npy` |
| 4 | Rig | Copy **`dj_pipeline/gui_transfer/`** folder to the rig (not the old `-aux/vr4mice/gui_transfer` tree) |
| 5 | Rig | `make env` — installs PyQt5, numpy, moviepy |
| 6 | Rig | `cp config/local_config.json.example config/config.json` and edit paths |
| 7 | Rig | Configure SSH key access to the server user (`host@ip`) if not using `localhost` |
| 8 | Rig | `make run_gui` (Linux) or `run_gui.bat` (Windows) |

**Canonical code path:** `FreelyMovingVR4Mice/dj_pipeline/gui_transfer/`  
**Legacy (do not deploy):** `auxPipelines-DataJoint_Mathis/vr4mice/gui_transfer/` (flat layout, March 2023-era)

## Quick setup (Linux / macOS)

1. Copy this folder to the rig computer.
2. Install dependencies:
   ```bash
   make env
   ```
3. Create config (do not commit):
   ```bash
   cp config/local_config.json.example config/config.json
   ```
4. Edit `config/config.json` — key fields:

   | Key | Purpose |
   |-----|---------|
   | `ip` | Pipeline server IP (`localhost` for local testing) |
   | `host` | SSH user on the server (required for remote `scp`; empty for `localhost`) |
   | `remote_dropdown_menu` | Menu file on the server (default `/shared/gui_menu.npy`) |
   | `host_dropdown_menu` | Local copy on the rig (default `./gui_menu.npy`) |
   | `remote_dst` | Upload destination on the server |
   | `gui_output_folder` | Where the GUI writes session metadata locally |
   | `teensy_path`, `processed_path`, … | Rig paths for file transfer (see `config/config.py` example) |

5. Start the GUI:
   ```bash
   make run_gui
   ```

## Windows rig setup

VR rigs often run Windows 10/11. You do **not** need Docker or Make on the rig — only Python, the `gui_transfer/` folder, and SSH/`scp` to the pipeline server.

### Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.9+** | Install from [python.org](https://www.python.org/downloads/windows/). Enable **“Add python.exe to PATH”** during setup. |
| **OpenSSH client** | Required for `scp` to the server. Settings → Apps → Optional features → add **OpenSSH Client** (usually pre-installed on Windows 10/11). |
| **SSH key to server** | Passwordless login recommended. See step 4 below. |
| **Pipeline server menu** | Server must run `python run.py fetch` so `/shared/gui_menu.npy` exists (see **Server-side prerequisite**). |

Verify in **Command Prompt** or **PowerShell**:

```bat
python --version
scp
ssh
```

If `python` is not found, use the **Python Launcher**: `py -3 --version` and replace `python` with `py -3` below.

### Step 1 — Copy the GUI folder

Copy the whole folder from the repo to the rig, e.g.:

```
C:\vr4mice\gui_transfer\
```

Minimum contents: `main.py`, `gui.py`, `config/`, `modules/`, `utils/`, `run_gui.bat`, `check_rig_setup.py`, `check_rig_setup.bat`.

You can clone the repo on the rig or copy only `dj_pipeline/gui_transfer/` from a USB stick / shared drive.

### Step 2 — Install Python packages

Open **Command Prompt**, go to the GUI folder, and install dependencies:

```bat
cd C:\vr4mice\gui_transfer
python -m pip install --upgrade pip
python -m pip install PyQt5 numpy "moviepy>=1.0.3"
```

### Step 3 — Create `config\config.json`

Do **not** commit this file (it contains rig-specific paths).

```bat
cd C:\vr4mice\gui_transfer\config
copy local_config.json.example config.json
```

For Windows paths, you can start from the dedicated template:

```bat
copy windows_config.json.example config.json
```

Edit `config\config.json` in Notepad or VS Code. Use forward slashes in paths (`C:/vr4mice/...`) — they work reliably in JSON on Windows.

| Key | Windows example | Purpose |
|-----|-----------------|---------|
| `ip` | `192.168.1.10` | Pipeline server IP (not `localhost` on a real rig) |
| `host` | `vr4mice` | SSH username on the server (**required** when `ip` is remote) |
| `remote_dropdown_menu` | `/shared/gui_menu.npy` | Path **on the Linux server** (inside the pipeline container mount) |
| `host_dropdown_menu` | `C:/vr4mice/gui_transfer/gui_menu.npy` | Local copy updated at GUI startup |
| `remote_dst` | `/data/data` | Upload destination on the server |
| `gui_output_folder` | `C:/vr4mice/gui_output/raw` | Local metadata output |
| `teensy_path` | `C:/vr4mice/raw` | Folder with `.pickle` files |
| `dlc_path`, `camera_path`, … | `C:/vr4mice/dlc_video_raw` | Folders scanned for related session files |
| `processed_path` | `C:/vr4mice/processed_rig` | Where files move after successful submit |

Adjust every path to match your rig’s Teensy / camera / DLC layout.

### Step 4 — SSH access to the server

The GUI uses `scp` at startup (menu file) and on submit (data upload). Test from the rig:

```bat
ssh vr4mice@192.168.1.10
scp vr4mice@192.168.1.10:/shared/gui_menu.npy C:\vr4mice\gui_transfer\gui_menu.npy
```

If `scp` asks for a password every time, set up an SSH key:

```bat
ssh-keygen -t ed25519
type %USERPROFILE%\.ssh\id_ed25519.pub
```

Add the printed public key to `~/.ssh/authorized_keys` on the server (ask your admin).

### Step 5 — Preflight check (recommended)

Before the first real session, run the setup checker from the GUI folder:

```bat
cd C:\vr4mice\gui_transfer
check_rig_setup.bat
```

This verifies Python, PyQt5/moviepy, `scp`, and `config\config.json`. To test menu download from the server (uses `scp -o BatchMode=yes` — requires SSH keys, no password prompt):

```bat
check_rig_setup.bat --test-menu
```

On Linux rigs the same script works: `python check_rig_setup.py [--test-menu]`.

If preflight fails, fix the reported items before starting the GUI.

### Step 6 — Start the GUI

**Option A — double-click**

Double-click `run_gui.bat` in `C:\vr4mice\gui_transfer\`.

**Option B — Command Prompt**

```bat
cd C:\vr4mice\gui_transfer
run_gui.bat
```

**Option C — manual**

```bat
cd C:\vr4mice\gui_transfer
set config_path=default
set config_name=config.json
python main.py
```

If the window closes immediately, run from Command Prompt (not double-click) to see the error, or check `logs/` if present.

### Windows troubleshooting

| Symptom | Fix |
|---------|-----|
| `'python' is not recognized` | Reinstall Python with “Add to PATH”, or use `py -3 main.py` |
| `'scp' is not recognized` | Install **OpenSSH Client** (Windows optional feature) |
| GUI exits on start | Run `check_rig_setup.bat --test-menu`; ensure `python run.py fetch` on server |
| `ModuleNotFoundError: PyQt5` / `moviepy` | Re-run pip install (step 2) in the same Python you use to start the GUI |
| Wrong folders in file picker | Fix paths in `config\config.json` |
| Upload fails at Submit | Check `host`, `ip`, `remote_dst`, and SSH key |

More detail: [install guide — GUI dropdown menu and rig setup](../../docs/software/install_dj_pipeline.md#gui-dropdown-menu-and-rig-setup).

On startup, `config.get_menu_path` copies the server dropdown menu (`gui_menu.npy`) to the rig:
- **`localhost`**: copies `remote_dropdown_menu` → `host_dropdown_menu` locally
- **remote server**: `scp host@ip:remote_dropdown_menu` → `host_dropdown_menu`

If the copy or `scp` fails, the GUI logs a warning and exits. Run `python run.py fetch` on the server first (see **Server-side prerequisite** below).

## Local test (no rig, no SSH)

From `gui_transfer/test/`:

```bash
make menu config build_tree
make run_gui
```

This creates a fake menu and config under `/tmp/vr4mice_test_gui` and launches the GUI against `localhost`.

From the repo root, run unit tests (no display required):

```bash
cd tests && python -m pytest unit/test_gui_transfer.py -v
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| GUI exits immediately on start | Menu file missing or `scp` failed | Run `python run.py fetch` on server; check `remote_dropdown_menu` path and SSH |
| `ModuleNotFoundError: moviepy` | Dependencies not installed | Run `make env` |
| `Config not found` | Missing `config/config.json` | Copy from `config/local_config.json.example` |
| Empty dropdowns | Stale or empty `gui_menu.npy` | Re-run `python run.py fetch` on server |
| Wrong pipeline / old GUI behaviour | Deployed legacy `-aux` checkout | Replace with this folder from `FreelyMovingVR4Mice` |
| Windows: `'scp' is not recognized` | OpenSSH Client not installed | Windows Settings → Optional features → OpenSSH Client |
| Windows: GUI closes instantly | Menu/`scp`/config error | Run `python main.py` from cmd to see the message |
| Auto-fill / prefetch does not find files | Filename does not match [rig filename contract](#rig-filename-contract) | Rename files or update code (see contract section) |

## Rig filename contract

The rig GUI and the pipeline **`populate_rig`** logic share the same implicit naming rules. Auto-discovery (pick one file → find siblings), mouse/date/attempt sync, and server ingest all depend on this contract.

Patterns are defined in code (not in `config.json`). If rig output naming changes, update GUI and pipeline **in the same PR**.

### Dataset stem (session ID)

Every session file should embed:

```text
{mouse_name}_{YYYY-MM-DD}_{attempt}
```

Example stem: `Testmouse_2023-02-22_2`

Parsed by `utils/session_files.py` (`SESSION_RE`). Also used for GUI output files (`{stem}.npy`, `{stem}.json`) and the pipeline `dataset` field.

**Limitation:** mouse names must not contain underscores — the regex takes the first `_`-delimited segment as the mouse name.

### Expected files per session

With camera prefix from `IMG_SRC` (default `Imagingsource`), a full session typically looks like:

| Role | Example filename | GUI key |
|------|------------------|---------|
| Teensy / state | `Testmouse_2023-02-22_2.pickle` | `teensy_path` |
| GUI metadata (generated on submit) | `Testmouse_2023-02-22_2.npy` | `gui_output` |
| Camera timestamps | `Imagingsource_Testmouse_2023-02-22_2_TS.npy` | `camera_path` |
| DLC output | `Imagingsource_Testmouse_2023-02-22_2_DLC.hdf5` | `dlc_path` |
| Processed kinematics | `Imagingsource_Testmouse_2023-02-22_2_PROC` | `proc_path` |
| Video (metadata only; stays on rig) | `Imagingsource_Testmouse_2023-02-22_2_VIDEO.avi` | `video_path` |

The server-side mirror is `vr4mice/actions/populate_rig.py` → `get_files_paths()`.

### How the GUI classifies files

1. **Validation** — `modules/transfer.py` → `_set_path_format()` (glob patterns for the file picker).
2. **Type tag** — `get_type()` scans for keywords: `VIDEO`, `TS`, `DLC`, `PROC`; otherwise `teensy_path`.
3. **Sibling search** — `find_related_files()` lists configured rig folders and keeps files whose stem matches the selected session.

### If formats change

| Change | What breaks | Manual workaround |
|--------|-------------|-------------------|
| New suffix (e.g. `_TIMESTAMPS` instead of `_TS`) | Validation + prefetch + populate | Use file buttons to attach each file by hand |
| Different date format | Stem parsing, auto-fill | Enter mouse/date/attempt manually |
| New file category | Not shown in transfer section | Requires new GUI key + populate path |
| Mouse names with `_` | Wrong stem split | Avoid underscores in mouse names or update regex |

### Code to update (checklist)

When changing rig naming, edit **together**:

| File | What to change |
|------|----------------|
| `gui_transfer/utils/session_files.py` | `SESSION_RE`, validation helpers |
| `gui_transfer/modules/transfer.py` | `_set_path_format()`, `get_type()`, transfer keys |
| `vr4mice/actions/populate_rig.py` | `get_files_paths()` |
| `tests/unit/test_gui_transfer.py` | Golden filename examples |
| This README + [install guide](../../docs/software/install_dj_pipeline.md#rig-filename-contract) | Examples and troubleshooting |

Run tests after changes:

```bash
cd tests && python -m pytest unit/test_gui_transfer.py -v --confcutdir=unit
```

## GUI modules

The GUI has three modules (more can be added by subclassing the template in `modules/`):

1. **Mouse information** — subject metadata from dropdowns
2. **Experimental sessions** — session / rig / task fields
3. **Data transfer** — queue rig files for upload (blocks video paths)

![Screenshot](https://user-images.githubusercontent.com/43879378/234045182-c1e69d48-b6a2-4f76-b7f5-938bc3de840b.png)

Each module defines label/value dictionaries that drive PyQt widgets. On submit, values are written to a cache JSON and included in transfer metadata. See module classes under `modules/` and the template in `modules/template.py`.

## Server-side prerequisite

The pipeline server must export the menu file before dropdowns work on the rig:

```bash
python run.py fetch   # writes /shared/gui_menu.npy in the client container
```

This runs automatically at the end of local `cron_scenario.py` runs. AWS cron runs do not refresh the menu.
