# VR4Mice Core (`vr4mice`)

DataJoint schemas, ingestion actions, and analysis helpers for the pipeline.

## Key components

- `schema/`: DataJoint table definitions.
- `analysis/`: analysis helpers and plotting.
- `actions/`: orchestration helpers (ingest, sync, fetch).
- `utils/`: logging, schema config, connections.

## Entry points

- **Manual runs:** `run.py` (from `dj_pipeline/`)
- **Scheduled runs:** `cron_scenario.py`

## Documentation

- Full pipeline guide: [../README.md](../README.md)
- Published book: [Setup & Usage](../../docs/software/install_dj_pipeline.md), [Architecture & Tables](../../docs/software/datajoint.md)
