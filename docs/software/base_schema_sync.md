# Base schema sync / recovery (`mice` / `exp`)

(ref:base-schema-sync)=

## Run inside the Docker client (required)

`run.py` and `run_base.py` must run **inside the pipeline client container**
(`make bash` / `make ipython`), same as cron. Host `python` does not have
`base_actions` / DataJoint.

```bash
cd dj_pipeline
make client_up          # if needed
make bash               # sources .env; shell in /app
# then python run_base.py recover_base / cleanup_*
```

**Mouse registry from parent** is **host-side** (bash `mysqldump` / `mysql`) — not
inside `make bash`:

```bash
cd dj_pipeline
make -f mysql.mk sync-mice-from-main
make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
```

## Normal ingest

When `GUI=True`, **daily populate writes `exp` / `mice`** with `vr4mice`:

```bash
# inside make bash
python run.py populate
```

### Recommended order

```bash
# host, from dj_pipeline/
make -f mysql.mk sync-mice-from-main

# inside make bash
python run_base.py recover_base
python run_base.py cleanup_orphans
python run_base.py cleanup_orphans --force   # apply deletes (local only)
python run.py fetch   # refresh GUI menu if needed
```

| Mode | Purpose |
|------|---------|
| `make -f mysql.mk sync-mice-from-main` | Parent → local mice registry via **mysqldump** |
| `recover_base` | Populate unpopulated GUI `.npy` into local `exp`/`mice`, then `base.Base.populate()` |
| `cleanup_orphans` | List/delete local `exp`/`mice` with no `vr4mice.Dataset` |
| `cleanup_mice` | Remove **stub** mice with no local Session |
| `check_session_days` | Exit 1 if `exp.Session.day` ≠ doe timeline |
| `fix_session_days` | Rekey wrong `Session.day` (dry-run; `--force` applies) |

### Safety

1. **Never delete on main.** mysql sync dumps only.
2. Orphan deletes / `fix_session_days --force` need replication off.
3. mysql sync may **REPLACE** local Mouse/Surgery/score-sheet rows.

---

## Credentials

In `dj_pipeline/.env`:

```bash
DJ_HOST=local-db-host:3306
DJ_USER=your-user
DJ_PWD=your-password
GUI=True

# Parent DB (for mysql.mk sync-mice-from-main)
DJ_MAIN_HOST=main-db.example.com:3306
# DJ_MAIN_USER=...   # optional; falls back to DJ_USER
# DJ_MAIN_PWD=...
```

---

## Replication must be off for cleanup

Local `mice` / `exp` are often a MySQL replica. Stop replication before
`cleanup_orphans --force`. Check from the host:

```bash
make -f mysql.mk replication-summary
```

```sql
STOP REPLICA;   -- MySQL 8+
-- STOP SLAVE;  -- MySQL 5.7
```

---

## Step-by-step

### Sync mice (host)

```bash
make -f mysql.mk sync-mice-from-main
make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
```

`scripts/sync_mice_mysql.sh` dumps Strain / SurgeryType (INSERT IGNORE), then
Mouse / Surgery / score sheets (REPLACE) from `DJ_MAIN_*` onto local `DJ_HOST`,
maps `__`→`_` table names when needed, loads with `FOREIGN_KEY_CHECKS=0`.

### Recover base

```bash
python run_base.py recover_base
```

### Orphan cleanup (optional)

```bash
python run_base.py cleanup_orphans
python run_base.py cleanup_orphans --force
python run_base.py cleanup_mice --force   # stubs without Session only
```

### Fix wrong Session.day (PK rekey)

If `check_session_days` fails after a bad populate (day stuck at 1, etc.):

```bash
python run_base.py check_session_days
python run_base.py fix_session_days          # dry-run
python run_base.py fix_session_days --force  # replication must be off
python run_base.py check_session_days        # should pass
```

Rekeys `exp.Session`, `SessionScoreSheet`, and `base.Base` when present.
Still run `python run.py sync_days` (or recover’s sync) so on-disk `.npy`
`day` matches the DB.

### Resume

```bash
python run.py fetch
python run.py populate
```

---

## Minimal happy path

```bash
# host
make -f mysql.mk replication-summary
make -f mysql.mk sync-mice-from-main
make bash

# inside make bash
python run_base.py recover_base
python run_base.py cleanup_orphans --force   # only if dry-run looked OK
```

---

## Tests

`tests/unit/test_base_schema_sync.py` — stubs, GUI mouse discovery, recover,
orphan cleanup. Mice sync: `make -f mysql.mk sync-mice-from-main`.
