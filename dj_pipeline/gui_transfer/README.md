# Transfer GUI (`gui_transfer`)

PyQt5 GUI for capturing experiment metadata on the rig and transferring session files to the pipeline server. Videos remain on the rig; the GUI queues `.pickle`, `.npy`, and related rig outputs.

**Full setup** (server menu export, SSH/`scp`, path layout): [Setup & Usage — GUI dropdown menu and rig setup](../../docs/software/install_dj_pipeline.md).

## Quick setup

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
   | `host` | SSH user on the server (empty when using `localhost`) |
   | `remote_dropdown_menu` | Menu file on the server (default `/shared/gui_menu.npy`) |
   | `host_dropdown_menu` | Local copy on the rig (default `./gui_menu.npy`) |
   | `remote_dst` | Upload destination on the server |
   | `gui_output_folder` | Where the GUI writes session metadata locally |
   | `teensy_path`, `processed_path`, … | Rig paths for file transfer (see `config/config.py` example) |

5. Start the GUI:
   ```bash
   make run_gui
   ```

On startup, `Config.get_menu_path` copies the server dropdown menu (`gui_menu.npy`) to the rig so mice, experimenters, rigs, and tasks populate from DataJoint.

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
