# VR4Mice Core (`vr4mice`)

DataJoint schemas, ingestion actions, and analysis helpers for the pipeline.

## Layout

| Folder | Contents |
|--------|----------|
| `schema/` | Table definitions (`vr4mice`, `base_analysis`, `dlc`, `decision`, …) |
| `actions/` | Ingest, sync, GUI menu export (`populate_rig.py`, `fetch_data.py`, …) |
| `analysis/` | Session metrics, plotting, regression utilities |
| `utils/` | Logging, env loading, shared helpers |

## Entry points

- **Manual runs:** `run.py` (from `dj_pipeline/`)
- **Scheduled runs:** `cron_scenario.py`

## Documentation

- Full pipeline guide: [../README.md](../README.md)
- Published book: [Setup & Usage](../../docs/software/install_dj_pipeline.md), [Architecture & Tables](../../docs/software/datajoint.md)
