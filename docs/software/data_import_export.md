# Data Import/Export (Restricted Dumps)

This document covers exporting a restricted subset of the database and importing
the resulting dump files.

## Export (restricted, dataset-selected)
The repo includes `export_restricted_dump.sh`, which exports a **restricted** set of
tables/datasets (used for paper figures). It selects datasets based on:
- `SESSION_LABELS` and `SET_LABELS`
- an internal allowlist of tables
- optional per-table dataset overrides

How it works (high level):
- Reads credentials from `.env_aws` (or `DJ_HOST/DJ_USER/DJ_PWD` env vars).
- Detects the schema prefix used on the server (if schemas are prefixed).
- Finds datasets by joining `vr4mice.dataset` with `decision.session_label`.
- Iterates schemas and tables, and applies the most specific restriction available:
  `dataset`, or `session_label` + `set_name`, or `session_label`, or `set_name`.
- Writes one `restricted_dump_<schema>_<timestamp>.sql` per schema.
- Emits trace files with the table list, datasets, and a run summary.

Customizing the export:
- Edit `SESSION_LABELS` and `SET_LABELS` to change which datasets are included.
- Adjust `INCLUDED_TABLES_DEFAULT` to control which tables are dumped.
- Use `TABLE_DATASET_OVERRIDES` to force a specific dataset for a table.
- Set `EXPORT_ROOT=/path/to/exports` to change the output folder.

Run it from `dj_pipeline`:
```bash
bash export_restricted_dump.sh
```
Run inside the client container or a host shell that has MySQL client tools and
the correct `DJ_*` credentials loaded.

Output goes to `/app/exports/restricted_dump_<timestamp>/` inside the container (or
`$EXPORT_ROOT` if you set it).

## Import (quick_start.sh)
Copy the generated `restricted_dump_*.sql` files (or a `.zip`/`.tar.gz` archive) into
your dump directory and run:
```bash
bash quick_start.sh
```
When prompted:
- **Import DB dumps now?** → `yes`
- **Dump directory or .zip/.tar.gz archive** → path to the dump folder or archive

The script creates missing databases and imports each `restricted_dump_*.sql`.
If you provide an archive, it is extracted to `.../tmp_extract` under the dump dir,
so make sure you have ~50GB of free space available there. The archive is extracted
once into a stable folder; if that folder already exists, the script asks whether
to re-extract or reuse it. Archives may contain a nested folder; the importer will
search recursively for `restricted_dump_*.sql`.
Imports stay in the foreground and show progress (via `pv` or `dd status=progress`
when available).

## Import (raw mysql)
To import a single dump manually:
```bash
docker exec -i <vr4mice_db_name> mysql -uroot -psimple < data.sql
```
`<vr4mice_db_name>` is the DB container name from your docker compose setup.
