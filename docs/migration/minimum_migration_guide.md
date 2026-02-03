# Minimum DataJoint Migration Guide (0.14.x to 2.0)

This document describes the minimum changes required to migrate the vr4mice codebase from DataJoint 0.14.x to DataJoint 2.0.

## Overview

The migration involves changes in two main areas:
1. Schema class capitalization (`dj.schema` → `dj.Schema`)
2. Configuration key names (`database.misc.*` → `database.*`)

## 1. Schema Class Capitalization

**Files:** All schema definition files (e.g., `mice.py`, `exp.py`)

### DJ 0.x (before migration)
```python
import datajoint as dj

schema = dj.schema("mice", locals(), create_tables=True)

@schema
class Mouse(dj.Manual):
    ...
```

### DJ 2.0 (after migration)
```python
import datajoint as dj

schema = dj.Schema("mice", locals(), create_tables=True)

@schema
class Mouse(dj.Manual):
    ...
```

**Key change:**
- `dj.schema` (lowercase) → `dj.Schema` (capitalized)

**Note:** The `locals()` argument and `create_tables=True` continue to work in DJ 2.0.

## 2. Configuration Key Names

**File:** `dj_pipeline/vr4mice/utils/schema_config.py`

### DJ 0.x (before migration)
```python
import datajoint as dj

_schema_prefix = None
_create_tables = None

def configure_schema(prefix=None, create_tables=True):
    global _schema_prefix, _create_tables
    _schema_prefix = prefix
    _create_tables = create_tables

    # DJ 0.x config keys
    dj.config["database.misc.schema_prefix"] = prefix
    dj.config["database.misc.create_tables"] = create_tables
    dj.config["enable_python_native_blobs"] = True
```

### DJ 2.0 (after migration)
```python
import datajoint as dj

_schema_prefix = None
_create_tables = None

def configure_schema(prefix=None, create_tables=True):
    global _schema_prefix, _create_tables
    _schema_prefix = prefix
    _create_tables = create_tables

    # DJ 2.0 config keys (changed names)
    dj.config['database.database_prefix'] = prefix
    dj.config['database.create_tables'] = create_tables
    # Note: enable_python_native_blobs is removed in DJ 2.0
```

**Key changes:**
- `database.misc.schema_prefix` → `database.database_prefix`
- `database.misc.create_tables` → `database.create_tables`
- `enable_python_native_blobs` is removed (no longer needed)

## 3. Summary of All Changes

| Item | DJ 0.x | DJ 2.0 |
|------|--------|--------|
| Schema class | `dj.schema()` | `dj.Schema()` |
| Prefix config key | `database.misc.schema_prefix` | `database.database_prefix` |
| Create tables key | `database.misc.create_tables` | `database.create_tables` |
| Native blobs config | `enable_python_native_blobs = True` | (removed) |

## 4. Test Data Location

The golden test dataset is located at:
```
{project_root}/test_data/golden_dataset/
```

Required files:
- `Nightingale_2024-08-16_1.pickle`
- `Nightingale_2024-08-16_1.json`
- `Imagingsource_Nightingale_2024-08-16_1_DLC.hdf5`
- `Imagingsource_Nightingale_2024-08-16_1_TS.npy`
- `Imagingsource_Nightingale_2024-08-16_1_PROC`

## 5. Running Tests After Migration

```bash
# Activate virtual environment
cd /path/to/project
source venv/bin/activate

# Run unit tests (no database required)
cd tests
python -m pytest unit/ -v

# Run integration tests (requires Docker)
sg docker -c "bash -c 'source ../venv/bin/activate && python -m pytest integration/ -v'"
```
