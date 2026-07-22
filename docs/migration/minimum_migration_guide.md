# Minimum DataJoint Migration Guide (0.14.x to 2.0)

This document describes the minimum changes required to migrate the vr4mice codebase from DataJoint 0.14.x to DataJoint 2.0, and the steps to apply the migration.

## Code Changes (already applied in this PR)

The PR updates the Python codebase in three areas:

### 1. Blob Type Annotations

**Files:** All schema definition files (`vr4mice.py`, `base_analysis.py`, `dlc.py`, etc.)

DJ 2.0 requires explicit `<blob>` type annotations instead of raw MySQL blob types.

| DJ 0.x | DJ 2.0 |
|--------|--------|
| `longblob` | `<blob>` |
| `blob` | `<blob>` |
| `mediumblob` | `<blob>` |

This is the largest change by file count: ~150+ columns across 10 schema files.

### 2. Schema Class Capitalization

**Files:** All schema definition files, `schema_config.py`

```python
# DJ 0.x
schema = dj.schema("mice", locals(), create_tables=True)

# DJ 2.0
schema = dj.Schema("mice", locals(), create_tables=True)
```

### 3. Configuration Key Names

**File:** `dj_pipeline/vr4mice/utils/schema_config.py`, `dj_pipeline/base/base_min_schemas/base_schemas/utils/add_schema.py`

| DJ 0.x | DJ 2.0 |
|--------|--------|
| `database.misc.schema_prefix` | `database.database_prefix` |
| `database.misc.create_tables` | `database.create_tables` |
| `enable_python_native_blobs = True` | (removed, native by default) |

## Migration Workflow

### Step 1: Back up the database

Before anything else, create a full backup of the production database.

```bash
mysqldump -u root -p --all-databases > backup_pre_dj2_migration.sql
```

Keep this backup until you're confident everything works.

### Step 2: Merge the migration PR

Merge the migration PR into main. This updates the Python code but does not touch the database.

### Step 3: Install DataJoint 2.0

```bash
pip install "datajoint>=2.0.1"
```

> **MySQL version note:** DataJoint 2.0.1 works with MySQL 5.7 and 8.0+.
> DataJoint 2.1 and later require MySQL 8.0.13+ (they query
> `information_schema.STATISTICS.EXPRESSION`, which only exists in 8.0.13+).
> If you're on MySQL 5.7, stay on `datajoint==2.0.1` or upgrade MySQL first.

### Step 4: Migrate the database columns

The database needs its column metadata updated so DJ 2.0 can correctly deserialize blob data. This only modifies MySQL column comments (adding `:<blob>:` prefixes), not the actual data.

```bash
# Preview changes first (dry run)
python scripts/migrate_to_dj2.py --prefix your_schema_prefix_ --dry-run

# Apply the migration
python scripts/migrate_to_dj2.py --prefix your_schema_prefix_
```

Or from Python:

```python
import datajoint as dj
from datajoint.migrate import migrate_columns

schema = dj.Schema("your_schema_name")

# Preview
migrate_columns(schema, dry_run=True)

# Apply
migrate_columns(schema, dry_run=False)
```

> **Fresh install?** If the database was created with DJ 2.x code from scratch, this
> step is usually a no-op (`No columns need migration`).

### Step 5: Rebuild lineage tables

After `migrate_to_dj2.py` (or immediately on a fresh DJ 2.x database), rebuild
DataJoint lineage tables once per rig:

```bash
cd dj_pipeline
python run.py maintenance
```

This is separate from column migration: `migrate_to_dj2.py` fixes blob column
comments; `run.py maintenance` rebuilds dependency/lineage metadata. Cron does not
run this automatically.

**What `maintenance` maintains:** each schema has a hidden `~lineage` table. DataJoint
2.x records, per attribute, where it came from in the FK dependency graph. Joins and
`populate()` use this semantic lineage so attributes match by origin, not just name.
`rebuild_lineage()` repopulates those rows from current table definitions.

**What it does not touch:** raw rig files, computed table contents (`DataFrame`,
`SummaryPlots`, etc.), or blob column comments.

**Symptoms when lineage is missing or stale:** `Semantic check disabled: ~lineage table
not found`, join errors (`lineage missing on one side`), or unexpected `populate()`
behavior on dependent tables.

### Step 6: Run the test suite

```bash
cd dj_pipeline

# Run all tests (unit + integration):
docker-compose -f docker-compose.test.yml run --rm tests bash -c "cd tests && python -m pytest integration/ unit/ -v"
```

The test infrastructure uses MySQL 8.0 with `latin1` charset (configured in
`docker-compose.test.yml`). The `latin1` setting is required to avoid
exceeding the 3072-byte index key length limit that DataJoint tables with
long composite varchar keys hit on MySQL 8.0's default `utf8mb4` charset.

The integration tests spin up a MySQL container, insert the golden dataset, populate downstream tables, and verify row counts and sample values against golden baselines.

### Step 7: Run your analysis pipelines

Run your normal analysis workflows to confirm everything produces expected results. Pay attention to:
- Tables that use blob columns (MouseState, State, DLC, etc.)
- Downstream computed tables (DataFrame, OfflineKinematics, InterpolatedTrials, SessionMetrics)
- Any custom scripts that call `fetch()` on blob columns

### Step 8: Keep the backup

Keep the database backup around for a reasonable period until you're confident everything is working correctly in production.

## What migrate_columns() Does

`migrate_columns()` is a metadata-only operation. It:
- Queries `information_schema.COLUMNS` for all columns in a schema
- Identifies blob columns missing the `:<blob>:` comment marker
- Runs `ALTER TABLE ... MODIFY COLUMN ... COMMENT ':<blob>:...'` to add the marker
- Does NOT change column types or data

DJ 2.0 uses these comment markers to know which columns to deserialize. Without them, blob columns return raw bytes instead of Python objects.

## Test Data Location

The golden test dataset lives in the repository (as Git LFS) at:
```
dj_pipeline/tests/data/w_photodiode/
```

Contains the `Flamingo_2026-02-05_1` dataset:
- `Flamingo_2026-02-05_1.pickle`
- `Flamingo_2026-02-05_1.json`
- `Flamingo_2026-02-05_1.npy`
- `Imagingsource_Flamingo_2026-02-05_1_DLC.hdf5`
- `Imagingsource_Flamingo_2026-02-05_1_TS.npy`
- `Imagingsource_Flamingo_2026-02-05_1_PROC`

## Summary of All Code Changes

| Item | DJ 0.x | DJ 2.0 |
|------|--------|--------|
| Blob annotations | `longblob` / `blob` / `mediumblob` | `<blob>` |
| Schema class | `dj.schema()` | `dj.Schema()` |
| Prefix config key | `database.misc.schema_prefix` | `database.database_prefix` |
| Create tables key | `database.misc.create_tables` | `database.create_tables` |
| Native blobs config | `enable_python_native_blobs = True` | (removed) |
