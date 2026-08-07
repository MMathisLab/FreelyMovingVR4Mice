# Base schema sync / recovery (`mice` / `exp`)

(ref:base-schema-sync)=

## Normal ingest (usual workflow)

When `GUI=True`, **daily populate still writes `exp` / `mice`** as part of the
normal pipeline:

```bash
python run.py populate    # POPULATE_BASE defaults to True; uses GUI .npy → exp/mice
python run.py analysis
# …
```

Cron / `run.py` are unchanged in that sense: session ingest with GUI metadata
populates base tables together with `vr4mice` tables. Set `POPULATE_BASE=false`
only if you explicitly want to skip base on that path.

---

## When you need `run_base.py`

Use **`python run_base.py …`** for **recovery and parent-DB sync**, not as a
replacement for cron:

- Local `mice` / `exp` are outdated, empty, or inconsistent
- You need to clean orphans, pull mice from the parent registry, or push
  recovered sessions back to parent

Session files should still exist under `/data/data` and/or `/data/processed`.

---

## 1. Where to put credentials

Same client env file as the local DB — typically `dj_pipeline/.env`
(loaded into the Docker client via compose):

```bash
# Local DB (this rig)
DJ_HOST=local-db-host:3306
DJ_USER=your-user
DJ_PWD=your-password

# Parent / main lab DB (second DataJoint connection)
DJ_MAIN_HOST=main-db.example.com:3306
DJ_MAIN_USER=...          # optional; falls back to DJ_USER
DJ_MAIN_PWD=...           # optional; falls back to DJ_PWD

POPULATE_BASE=True
GUI=True
```

| Variable | Meaning |
|----------|---------|
| `DJ_HOST` / `DJ_USER` / `DJ_PWD` | Local database (pipeline + local `mice`/`exp`) |
| `DJ_MAIN_HOST` (+ optional user/pwd) | Parent DB: **pull** mice metadata, **push** sessions |

---

## 2. What recovery/sync automates

| Goal | Direction | How |
|------|-----------|-----|
| Daily ingest of new sessions (GUI) | disk → local `vr4mice` + `exp`/`mice` | `python run.py populate` |
| Rebuild / backfill local `exp` (+ stub `mice`) from GUI `.npy` | disk → local | `recover_base` or `run_base.py populate` |
| Full Mouse / Surgery / score sheets | parent → local | `python run_base.py sync_mice` |
| `exp.Session` (+ `SessionScoreSheet`) | local → parent | `python run_base.py sync_exp` |
| Copy `exp` from parent onto this rig | parent → local | **Not done** — local sessions come from GUI files on disk |

`sync_exp` inserts **only missing** sessions on parent (does not overwrite
existing parent rows). The mouse must already exist on main; otherwise that
session is skipped and logged.

---

## 3. Why replication must be off for cleaning

Local `mice` / `exp` are often a **MySQL replica** of the lab parent DB.

Orphan **cleanup** (`recover_base --force`) **deletes** local `exp.Session` /
`mice.Mouse` rows that have no matching `vr4mice.Dataset` on this rig.

That is unsafe while replication is active:

1. **Replica SQL/IO still running** — parent changes can re-insert or overwrite
   rows you just deleted, or stop replication with conflicts mid-cleanup.
2. **Read-only replica** — deletes fail or leave a half-updated DB.
3. **Cleanup is a local decision** — “orphan” means “no `vr4mice.Dataset` here”,
   not “delete on the parent registry”. Do not clean while the replica stream
   still treats parent as the live writer for the same tables.

**So:** stop replication before `--force` cleanup. The script **blocks** if
replica IO/SQL is `Yes` or the DB is `read_only` / `super_read_only`.

`sync_mice` / `sync_exp` use a **second** connection (`DJ_MAIN_HOST`) and do
not require replica threads to be stopped — but `recover_base` always checks
replication first, because the same command can delete when you pass `--force`.

Check status:

```bash
make -f mysql.mk replication-summary
# Replica_IO_Running / Replica_SQL_Running should not be Yes; DB not read_only
```

---

## 4. Step-by-step recovery (copy-paste)

Run inside the client container (or any env with the `.env` above loaded).

### Step A — credentials + replication

1. Edit `.env` with `DJ_HOST` and `DJ_MAIN_*` (section 1).
2. Confirm replication is off / DB writable (section 3).

### Step B — preview orphans (safe: no deletes)

```bash
python run_base.py recover_base
```

This:

1. Checks replication (aborts if active).
2. **Lists** `exp.Session` / `mice.Mouse` with no matching `vr4mice.Dataset`
   (“would delete …”).
3. Still tries to populate base from `/data/data` + `/data/processed` GUI `.npy`.

**Read the “would delete …” list carefully.**

### Step C — optional destructive cleanup

Only if the orphan list is OK (see caution below):

```bash
python run_base.py recover_base --force
```

Deletes those orphans, then repopulates from `/data/data` + `/data/processed`.

**Caution — future mice:** `--force` deletes **any** local mouse **not**
referenced by a `vr4mice.Dataset` name — including real mice you synced for
upcoming experiments (no session/dataset yet).

If you need those mice:

- do **not** use `--force`, or
- note the names from the dry-run and re-sync them afterward.

Safer light cleanup (stub mice with **no** local Session only):

```bash
python run_base.py cleanup_mice          # dry-run
python run_base.py cleanup_mice --force   # delete those stubs only
```

### Step D — populate without deleting (if you skipped `--force`)

Either continue with recovery tools:

```bash
python run_base.py sync_days
python run_base.py populate
```

Or, for normal ongoing ingest after recovery, use the usual cron path:

```bash
python run.py populate
```

Both honor `POPULATE_BASE` (default on). With `GUI=True`, `.npy` metadata drives
`exp`/`mice` as in the usual workflow.

### Step E — pull full mouse metadata from parent

Needs local `exp.Session` first (steps B–D):

```bash
python run_base.py sync_mice
```

Only incomplete/stub mice that have local sessions are updated from
`DJ_MAIN_HOST`.

### Step F — push local sessions to parent

```bash
python run_base.py sync_exp
```

Requires **write access** on main `exp`. Inserts missing `exp.Session` (+
`SessionScoreSheet`) on parent. Skips mice that do not exist on main.

### Step G — optional GUI menu refresh

```bash
python run_base.py fetch
# or: python run.py fetch
```

Writes `/shared/gui_menu.npy` (mice limited to those with local sessions).

---

## 5. Minimal “happy path” (recovery)

```text
1. Put DJ_MAIN_HOST (+ USER/PWD) in .env next to DJ_HOST
2. Stop replication / ensure writable local DB
3. python run_base.py recover_base              # inspect orphans
4. python run_base.py recover_base --force      # ONLY if orphan list is OK
   # OR: sync_days + populate without deleting
5. python run_base.py sync_mice                # parent → local mouse metadata
6. python run_base.py sync_exp                 # local → parent sessions
7. (optional) fetch
8. Re-enable replication only after mice/exp look consistent on both sides
9. Resume normal cron: python run.py populate (GUI=True still fills exp/mice)
```

---

## 6. Command cheat sheet

| Command | What it does |
|---------|----------------|
| `python run.py populate` | **Usual ingest** — with `GUI=True` / `POPULATE_BASE`, writes `vr4mice` + `exp`/`mice` |
| `python run_base.py recover_base` | Replication check → list orphans → populate from data + processed |
| `python run_base.py recover_base --force` | Same, but **deletes** orphans first |
| `python run_base.py sync_days` | Fix experiment day in GUI `.npy` (data + processed together) |
| `python run_base.py populate` | Same ingest helper as above (optional `--no-populate-base`) |
| `python run_base.py sync_mice` | Parent → local Mouse (+ Surgery, score sheets) |
| `python run_base.py sync_exp` | Local → parent Session (+ SessionScoreSheet), missing only |
| `python run_base.py cleanup_mice` | Dry-run: stub mice with no local Session |
| `python run_base.py cleanup_mice --force` | Delete those stubs |
| `python run_base.py fetch` / `run.py fetch` | Export GUI menu `.npy` |
| `make -f mysql.mk replication-summary` | Replica / read-only diagnostics |

---

## 7. Tests

Unit coverage (CI, no MySQL): `tests/unit/test_base_schema_sync.py` — stubs,
`DJ_MAIN_HOST` gates, replication block, orphan dry-run, `sync_exp` helpers,
sync_days helpers, `POPULATE_BASE`, and `run_base.py` modes.
