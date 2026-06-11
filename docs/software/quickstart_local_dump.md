(sec:import-sql-dump)=
# Deploy the DataJoint database locally

**This guide explains how to:**
- Get a database containing the data used in the paper up and running locally.
- Replicate our analysis.

## Requirements
- Bash
- Docker + Docker Compose
- GNU Make

## Step 1 — Download the data archive

We provide a [Zenodo record](https://zenodo.org/uploads/19091270) containing all the files you need to reproduce our database locally.

```{note}
The archive should be a `.zip` file. **Keep it as-is**; the quickstart script will import it directly. The archive will be extracted to a folder inside your dump directory
(`.../tmp_extract/<archive-name>`). **Make sure you have ~50GB of free space** there.
```

The Zenodo record consists of a compressed `.zip` archive containing:
-  `restricted_dump_*.sql` files, with one file per schema (should contain 7 `.sql` files in total).
- `datasets.txt`, a list of the sessions contained in the dump (format is `{mouse_id}_{session_date}_{session_attempt}`).
- `meta.txt`, a run summary file, emitted at the end of the export.
- `tables.csv`, a per-table log of the tables and row counts exported (see below).

Exact row counts for your archive are listed in `tables.csv`. The table below summarizes exported schemas, tables, and restriction modes (10-window decision models used in the paper notebooks).

| Schema | Table | Restriction Mode | Entries count |
|---|---|---|---|
| vr4mice | #labels | unrestricted | 5 |
| vr4mice | #labs | unrestricted | 4 |
| vr4mice | __collab | dataset | 471 |
| vr4mice | dataset | dataset | 471 |
| vr4mice | groups | dataset | 221 |
| vr4mice | signals_photodiode | dataset | 0 |
| base_analysis | __box_data_frame | dataset | 453 |
| base_analysis | __data_frame | dataset | 453 |
| decision | #label | unrestricted | 14 |
| decision | #label_set | unrestricted | 8 |
| decision | #label_set__member | unrestricted | 44 |
| decision | __decision_points10_windows | dataset | 3320 |
| decision | __inclusion_status | dataset | 471 |
| decision | __prediction_model10_windows | set_name | 32 |
| decision | __prediction_model10_windows__session_prediction | dataset | 744 |
| decision | _experiment_member | dataset | 471 |
| dlc | __offline_kinematics | dataset+dataset_override | 1 |
| interpolated_trajectories | __interpolated_trials | dataset | 445 |
| interpolated_trajectories | __mean_velocities | dataset | 445 |
| interpolated_trajectories | __mean_x_y_trajectory | dataset | 445 |
| interpolated_trajectories | __y_binned_x_y_trajectory | dataset | 445 |
| latency_tests | __all_latencies | dataset | 83 |
| latency_tests | __signals_photodiode_aligned | dataset+dataset_override | 1 |
| session_metrics | __session_metrics | dataset | 453 |
| session_metrics | __trial_metrics | dataset | 453 |

## Step 2 — Clone the git repository

If you haven't already, you need to clone our GitHub repository, as it contains the code to deploy the database. To do so, move to the folder you want to clone the repository and run: 

```bash
 # Using HTTPS (recommended):
 git clone https://github.com/MMathisLab/FreelyMovingVR4Mice.git
 # Or, if you have SSH keys configured with GitHub:
 # git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git

cd FreelyMovingVR4Mice/dj_pipeline
```

## Step 3 — Run the default quickstart script (local deploy)
The default mode starts **both DB and client** containers locally.

```bash
bash quick_start.sh
```

When prompted:
- **Mode**: press Enter for `default`
- **Build with --no-cache?**: choose `no` unless you need a clean rebuild
- **Install base schemas/actions now?**: choose `yes`
- **Import DB dumps now?**: choose `yes`
- **Skip import if DB already has tables?**: choose `yes` for demo mode (default: `no`)
- **Dump directory or .zip/.tar.gz archive**: path to your dump folder or archive

The script will create databases and import `restricted_dump_*.sql`.
Imports stay in the foreground and show progress (via `pv` or `dd status=progress`
when available).

```{warning}
Depending on the disk speed, the import can take **up to ~1 hour**.
```

## Step 4 — Connect Jupyter Notebooks
First, run:
```bash
make notebook
```

After it starts, open the URL printed in the terminal (it includes a token), e.g.
`http://localhost:8887/?token=...`. If you need a fresh link, re-run `make notebook`.

Then in Jupyter:
```python
%run env.py
%run run.py connect
```

Example schema imports:
```python
from base_schemas.schemas import exp, mice
from vr4mice.schema import vr4mice
vr4mice.Dataset().fetch()
```

Now, you can either play with the data yourself or run our Figures Jupyter notebooks directly. Happy hacking! 👩‍💻👾

For ongoing pipeline use (manual runs, cron, rig GUI setup), see {ref}`Setup & Usage <sec:install-dj-pipeline>`.


## Optional — SSH tunnel (remote server)
If Jupyter runs on a remote host:
```bash
ssh -NL 8887:localhost:8887 <user>@<server>
```
Append `&` if you want the tunnel in the background.
