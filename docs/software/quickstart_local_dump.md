# Quickstart (Local Deploy + Data Dump)

This guide explains how to:
- Download the **data archive** (database dump files) from Zenodo
- Clone the **git repository**
- Run **default quickstart** for a local deployment with a data dump
- Connect **Jupyter Notebook**

## Requirements
- Bash
- Docker + Docker Compose
- GNU Make

## Step 1 — Download the data archive (DB dumps)
The data archive contains `restricted_dump_*.sql` files (in a compressed .zip archive).

If the archive is a `.zip`/`.tar.gz`, keep it as-is; quickstart can import it directly.
The archive is extracted once to a stable folder inside your dump directory
(`.../tmp_extract/<archive-name>`). If that folder already exists, the script asks
whether to re-extract or reuse it, so make sure you have ~50GB of free space there.

## Step 2 — Clone the git repository
```bash
git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
cd FreelyMovingVR4Mice/dj_pipeline
```

## Step 3 — Run default quickstart (local deploy)
The default mode starts **both DB and client** containers locally.

```bash
bash quick_start.sh
```

When prompted:
- **Mode**: press Enter for `default`
- **Build with --no-cache?**: choose `no` unless you need a clean rebuild
- **Install base schemas/actions now?**: choose `yes`
- **Import DB dumps now?**: choose `yes`
- **Dump directory or .zip/.tar.gz archive**: path to your dump folder or archive

The script will create databases and import `restricted_dump_*.sql`.
Imports stay in the foreground and show progress (via `pv` or `dd status=progress`
when available).

## Step 4 — Connect Jupyter Notebook
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

## Optional — SSH tunnel (remote server)
If Jupyter runs on a remote host:
```bash
ssh -NL 8887:localhost:8887 <user>@<server>
```
Append `&` if you want the tunnel in the background.
