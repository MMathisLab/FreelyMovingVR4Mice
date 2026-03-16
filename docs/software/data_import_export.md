# Data Import/Export

This document covers exporting a restricted subset of the database and importing the resulting dump files into a new database.

## Export (`export_restricted_dump.sh`)

We provide an `export_restricted_dump.sh` bash script. This script exports a **restricted** set of tables, used specifically for the Benquet, Sainsbury et al. paper by selecting entries based on:
- `SESSION_LABELS` and `SET_LABELS`, corresponding to the tasks included in the paper (white and black target contrast tasks).
- an internal list of tables, used in the figure notebooks specifically
- optional per-table dataset overrides

How it works (high level):
- Reads credentials from an `.env` file (or `DJ_HOST/DJ_USER/DJ_PWD` env vars).
- Detects the schema prefix used on the server (if schemas are prefixed).
- Finds datasets by joining `vr4mice.dataset` with `decision.session_label`.
- Iterates schemas and tables, and applies the most specific restriction available:
  `dataset`, or `session_label` + `set_name`, or `session_label`, or `set_name`.
- Writes one `restricted_dump_<schema>_<timestamp>.sql` per schema.
- Emits trace files with the table list, datasets, and a run summary.

Customizing the export:
- Edit `SESSION_LABELS` and `SET_LABELS` to change which sessions sets are included.
- Adjust `INCLUDED_TABLES_DEFAULT` to control which tables are included.
- Use `TABLE_DATASET_OVERRIDES` to force specific datasets for a table.
- Set `EXPORT_ROOT=/path/to/exports` to change the output folder.

Run it from the `dj_pipeline/` folder, inside the client container or a host shell that has MySQL client tools and the correct `DJ_*` credentials loaded:
```bash
bash export_restricted_dump.sh
```

Output goes to `/app/exports/restricted_dump_<timestamp>/` inside the container (or `$EXPORT_ROOT` if you set it).

## Import (`quick_start.sh`) -- Recommended

Copy the generated `restricted_dump_*.sql` files (or a `.zip`/`.tar.gz` archive) into your dump directory and run:
```bash
bash quick_start.sh
```

When prompted:
- **Import DB dumps now?** → `yes`
- **Skip import if DB already has tables?** → `yes` for demo mode (default: `no`)
- **Dump directory or .zip/.tar.gz archive** → path to the dump folder or archive

The script creates missing databases and imports each `restricted_dump_*.sql`. If you provide an archive, it is extracted to `.../tmp_extract` under the dump dir, so make sure you have **~50GB of free space available** there. Imports stay in the foreground and show progress (via `pv` or `dd status=progress` when available). Depending on the disk speed, the import can take **up to ~1 hour**.

## Import (raw mysql)
To import a single dump manually:
```bash
docker exec -i <vr4mice_db_name> mysql -uroot -psimple < data.sql
```
`<vr4mice_db_name>` is the DB container name from your docker compose setup.
