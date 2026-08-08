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
# then python run_base.py recover_base / cleanup_* / sync_exp
```

**Mouse registry from parent** is **host-side** (bash `mysqldump` / `mysql`) — not
inside `make bash` — so we never open two DataJoint connections:

```bash
cd dj_pipeline
make -f mysql.mk sync-mice-from-main
make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
```

Exception: other `make -f mysql.mk …` diagnostics are also **host-side** MySQL
(`.env` `DJ_*` over TCP).
## Normal ingest (usual workflow)

When `GUI=True`, **daily populate writes `exp` / `mice`** together with `vr4mice`
(via cron / client):

```bash
# inside make bash
python run.py populate    # GUI .npy → exp/mice + vr4mice tables
python run.py analysis
# …
```

No separate base cron path. Base populate follows the `GUI` flag
(`GUI=True` ⇒ include `exp`/`mice`; `GUI=False` ⇒ `vr4mice` only).

### Recommended order (separate commands)

Each step is its own `run_base.py` mode — nothing is chained inside
`recover_base`.

```bash
# host, from dj_pipeline/ — preferred (no DataJoint dual-connect)
make -f mysql.mk sync-mice-from-main
make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale

# inside make bash — recover / cleanup / optional sync_exp only
python run_base.py recover_base
python run_base.py cleanup_orphans
python run_base.py cleanup_orphans --force   # apply deletes (local only)
python run_base.py sync_exp
python run.py fetch   # refresh GUI menu if needed
```

Requirements:

- **`sync_mice` (mysql.mk)** dumps Strain / Mouse / Surgery / score-sheet tables
  from `DJ_MAIN_*` onto local `DJ_HOST` via `mysqldump` + `mysql`. Handles main
  ``__`` vs local ``_`` table names. Optional `MOUSE=a,b` filters mouse-keyed
  tables; lookups are always copied in full (small).
- Do **not** use `python run_base.py sync_mice` for normal ops (it exits with
  instructions to run ``make -f mysql.mk sync-mice-from-main``).
- **`sync_exp` is optional** — this lab only (not collab). See §E.
---

## When you need `run_base.py`

| Mode | Purpose |
|------|---------|
| `make -f mysql.mk sync-mice-from-main` | Parent → local mice registry via **mysqldump** (preferred) |
| `recover_base` | Replication check + populate **unpopulated GUI `.npy`** into local `exp`/`mice` only |
| `cleanup_orphans` | List/delete local `exp`/`mice` with **no** `vr4mice.Dataset` (dry-run unless `--force`) |
| `cleanup_mice` | Remove **stub** mice with no local Session (narrower helper) |
| `sync_exp` | **Optional.** Local → parent missing `exp.Session` (this lab; match by doe) |

Session files for recover should exist under `/data/data` and/or `/data/processed`.

### Safety invariants

1. **Never delete on main.** mysql sync dumps only; `sync_exp` inserts missing
   rows only.
2. **Local Dataset-orphan deletes** only via `cleanup_orphans` (`--force` to
   apply). Not part of `recover_base`.
3. Prefer **host `make -f mysql.mk sync-mice-from-main`** (mysqldump). There is
   no DataJoint dual-connect path for mice sync.
4. mysql sync may **REPLACE** local Mouse/Surgery/score-sheet rows
   (`FOREIGN_KEY_CHECKS=0` during load).

---

## 1. Credentials

In `dj_pipeline/.env` (loaded into the Docker client; `make bash` sources it):

```bash
# Local DB (this rig)
DJ_HOST=local-db-host:3306
DJ_USER=your-user
DJ_PWD=your-password
GUI=True

# Parent / main lab DB (second DataJoint connection)
DJ_MAIN_HOST=main-db.example.com:3306   # include :port (main is often :3306, local :3309)
DJ_MAIN_USER=...          # optional; falls back to DJ_USER
DJ_MAIN_PWD=...           # optional; falls back to DJ_PWD
```

| Variable | Meaning |
|----------|---------|
| `DJ_HOST` / `DJ_USER` / `DJ_PWD` | Local database (host:port) |
| `DJ_MAIN_HOST` (+ optional user/pwd) | Parent host:port — **port is required if not 3306**; sync switches host and port |

---

## 2. Why replication must be off for cleaning

Local `mice` / `exp` are often a **MySQL replica** of the lab parent DB.

Orphan **cleanup** (`cleanup_orphans --force`) **deletes only on the local DB**:
`exp.Session` / `mice.Mouse` rows with no matching `vr4mice.Dataset` here.
It never deletes on the parent.

That is unsafe while replication is active — stop replication before `--force`.
`recover_base` also blocks if replica IO/SQL is `Yes` or the DB is read-only
(because it writes Sessions).

**Check** status (does **not** stop replication). From `dj_pipeline/` on the
**host**, `mysql.mk` uses the host `mysql` client with `.env` `DJ_HOST` /
`DJ_USER` / `DJ_PWD` (never `DJ_MAIN_*`):

```bash
make -f mysql.mk creds
make -f mysql.mk replication-summary
```

```sql
-- MySQL 8+
STOP REPLICA;
-- MySQL 5.7
STOP SLAVE;
```

---

## 3. Step-by-step recovery

### A — credentials + replication (host)

1. Set `DJ_HOST` and `DJ_MAIN_*` in `.env`.
2. `make -f mysql.mk replication-summary`. Stop replica if needed before
   `--force` cleanup (and preferably before `recover_base` writes).
3. Enter the client: `make client_up` (if needed), then `make bash`.

### B — sync mice (host `mysql.mk`)

```bash
# from dj_pipeline/ on the host (not make bash)
make -f mysql.mk sync-mice-from-main
make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
```

Uses `scripts/sync_mice_mysql.sh`: separate `mysql`/`mysqldump` clients for
`DJ_MAIN_*` and `DJ_HOST`, verifies live `@@port` differs, maps `__`→`_` table
names when needed, loads with `FOREIGN_KEY_CHECKS=0`.
Pulls Mouse (+ Strain, Surgery, score sheets) from parent for incomplete local
Dataset / GUI / Session names, or for explicit `--mouse NAME`.

### C — recover base (populate only)

```bash
python run_base.py recover_base
```

Rebuilds local `exp`/`mice` from **unpopulated** GUI `.npy` under `/data/data`
+ `/data/processed`. Does **not** sync or clean.

### D — optional orphan cleanup

```bash
python run_base.py cleanup_orphans          # dry-run
python run_base.py cleanup_orphans --force  # apply
```

Deletes local sessions/mice with no `vr4mice.Dataset`. Review the dry-run list
first. **Caution:** also removes mice not referenced by any Dataset (including
ones synced for upcoming experiments).

Lighter stub-only helper:

```bash
python run_base.py cleanup_mice          # dry-run
python run_base.py cleanup_mice --force
```

### E — optional sync_exp

```bash
python run_base.py sync_exp
```

Push missing local (non-collab) sessions to parent. Match by
`(mouse_name, doe, attempt)`; assign `day` from parent timeline. Never deletes
on main. Requires `DJ_LAB` when Collab is populated.

### F — resume

```bash
python run.py fetch      # optional GUI menu
python run.py populate   # or leave to cron
```

---

## 4. Minimal happy path

```bash
# host (dj_pipeline/)
# 1. DJ_MAIN_* in .env; replication OFF for cleanup
make -f mysql.mk replication-summary
make -f mysql.mk sync-mice-from-main
# optional: make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
make client_up
make bash

# inside make bash
python run_base.py recover_base
python run_base.py cleanup_orphans          # review list
python run_base.py cleanup_orphans --force  # only if OK
python run_base.py sync_exp                 # optional
python run.py fetch                        # optional
# exit

# host: re-enable replication; cron resumes run.py populate
```

---

## 5. Tests

`tests/unit/test_base_schema_sync.py` — stubs, GUI mouse discovery, recover
populate-only, orphan cleanup, `sync_exp` local-vs-collab + doe matching.
Mice registry sync from parent: `make -f mysql.mk sync-mice-from-main`
(`scripts/sync_mice_mysql.sh`).
