# Base schema sync / recovery (`mice` / `exp`)

(ref:base-schema-sync)=

## Normal ingest (usual workflow)

When `GUI=True`, **daily populate writes `exp` / `mice`** together with `vr4mice`:

```bash
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
# inside: make bash
# 1a. Pull Mouse rows from parent for local Dataset / GUI / Session names
python run_base.py sync_mice
# 1b. Or preload specific mice before any recordings exist
python run_base.py sync_mice --mouse Flamingo
python run_base.py sync_mice --mouse Flamingo --mouse Whale

# 2. Rebuild local exp/mice from unpopulated GUI .npy only
python run_base.py recover_base

# 3. Optional — list local exp/mice with no vr4mice.Dataset
python run_base.py cleanup_orphans
python run_base.py cleanup_orphans --force   # apply deletes (local only)

# 4. Optional — push missing local (non-collab) sessions to parent
python run_base.py sync_exp

python run.py fetch   # refresh GUI menu if needed
```

Requirements:

- `sync_mice` (default) pulls incomplete local names from ``vr4mice.Dataset``,
  GUI ``.npy``, and/or ``exp.Session``. Use ``--mouse NAME`` (repeatable) to
  preload mice from main before recordings exist.
- Main connection sets `database.use_tls=False` (assignment only; avoids SSL
  handshake failure on lab MySQL).
- **`sync_exp` is optional** — this lab only (not collab). See §D.

---

## When you need `run_base.py`

| Mode | Purpose |
|------|---------|
| `sync_mice` | Parent → local Mouse (+ Strain, Surgery, score sheets); Dataset/GUI/Session names, or `--mouse NAME` |
| `recover_base` | Replication check + populate **unpopulated GUI `.npy`** into local `exp`/`mice` only |
| `cleanup_orphans` | List/delete local `exp`/`mice` with **no** `vr4mice.Dataset` (dry-run unless `--force`) |
| `cleanup_mice` | Remove **stub** mice with no local Session (narrower helper) |
| `sync_exp` | **Optional.** Local → parent missing `exp.Session` (this lab; match by doe) |

Session files should still exist under `/data/data` and/or `/data/processed`.

### Safety invariants

1. **Never delete on main.** `sync_mice` fetches only; `sync_exp` inserts missing
   rows only.
2. **Local Dataset-orphan deletes** only via `cleanup_orphans` (`--force` to
   apply). Not part of `recover_base`.
3. **`sync_mice` may replace** local Mouse/Surgery/score-sheet rows
   (`replace=True`) — metadata refresh, not orphan deletion.

---

## 1. Credentials

In `dj_pipeline/.env` (loaded into the Docker client):

```bash
# Local DB (this rig)
DJ_HOST=local-db-host:3306
DJ_USER=your-user
DJ_PWD=your-password
GUI=True

# Parent / main lab DB (second DataJoint connection)
DJ_MAIN_HOST=main-db.example.com:3306
DJ_MAIN_USER=...          # optional; falls back to DJ_USER
DJ_MAIN_PWD=...           # optional; falls back to DJ_PWD
```

| Variable | Meaning |
|----------|---------|
| `DJ_HOST` / `DJ_USER` / `DJ_PWD` | Local database |
| `DJ_MAIN_HOST` (+ optional user/pwd) | Parent: **pull** needed mice (`sync_mice`); optional **push** sessions (`sync_exp`) |

---

## 2. Why replication must be off for cleaning

Local `mice` / `exp` are often a **MySQL replica** of the lab parent DB.

Orphan **cleanup** (`cleanup_orphans --force`) **deletes only on the local DB**:
`exp.Session` / `mice.Mouse` rows with no matching `vr4mice.Dataset` here.
It never deletes on the parent.

That is unsafe while replication is active — stop replication before `--force`.
`recover_base` also blocks if replica IO/SQL is `Yes` or the DB is read-only
(because it writes Sessions).

**Check** status (does **not** stop replication). From `dj_pipeline/`,
`mysql.mk` uses the **host** `mysql` client with `.env` `DJ_HOST` /
`DJ_USER` / `DJ_PWD` (same TCP login as the pipeline; never `DJ_MAIN_*`).
Verify with:

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

### A — credentials + replication

1. Set `DJ_HOST` and `DJ_MAIN_*` in `.env`.
2. `make -f mysql.mk replication-summary`. Stop replica if needed before
   `--force` cleanup (and preferably before `recover_base` writes).

### B — sync mice first

```bash
# inside make bash
python run_base.py sync_mice
```

Pulls Mouse (+ Strain, Surgery, score sheets) from parent for incomplete local
Dataset / GUI / Session names, or for explicit ``--mouse NAME`` (preload).

### C — recover base (populate only)

```bash
python3 run_base.py recover_base
```

Rebuilds local `exp`/`mice` from **unpopulated** GUI `.npy` under `/data/data`
+ `/data/processed`. Does **not** sync or clean.

### D — optional orphan cleanup

```bash
python3 run_base.py cleanup_orphans          # dry-run
python3 run_base.py cleanup_orphans --force  # apply
```

Deletes local sessions/mice with no `vr4mice.Dataset`. Review the dry-run list
first. **Caution:** also removes mice not referenced by any Dataset (including
ones synced for upcoming experiments).

Lighter stub-only helper:

```bash
python3 run_base.py cleanup_mice          # dry-run
python3 run_base.py cleanup_mice --force
```

### E — optional sync_exp

```bash
python3 run_base.py sync_exp
```

Push missing local (non-collab) sessions to parent. Match by
`(mouse_name, doe, attempt)`; assign `day` from parent timeline. Never deletes
on main. Requires `DJ_LAB` when Collab is populated.

### F — resume

```bash
python run.py fetch      # optional GUI menu
python run.py populate   # normal cron
```

---

## 4. Minimal happy path

```text
1. DJ_MAIN_* in .env; replication OFF for cleanup
2. python3 run_base.py sync_mice
3. python3 run_base.py recover_base
4. python3 run_base.py cleanup_orphans          # review list
5. python3 run_base.py cleanup_orphans --force  # only if OK
6. python3 run_base.py sync_exp                # optional
7. Re-enable replication; resume run.py populate
```

---

## 5. Tests

`tests/unit/test_base_schema_sync.py` — stubs, GUI mouse discovery, sync
direction, recover populate-only, orphan cleanup, `sync_exp` local-vs-collab +
doe matching.
