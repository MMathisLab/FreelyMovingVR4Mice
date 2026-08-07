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

### When new mice appear

Ingest can insert **stub** Mouse rows (`mouse_id=-1`) so `exp.Session` can be
created. Those stubs are **not** full registry records.

**Whenever new mice show up** (first session on this rig, or after recover/populate
left stubs / incomplete Mouse rows), run:

```bash
python run_base.py sync_mice   # pull full Mouse (+ Surgery, score sheets) from parent
python run.py fetch            # refresh GUI menu if needed
```

Requirements:

- Mice must already exist on the **parent** DB (`DJ_MAIN_HOST`).
- `sync_mice` only updates mice that already have a **local** `exp.Session`
  (stub or incomplete). It does not invent mice that never ran here.
- **`sync_exp` is optional.** Only run it if this rig should push missing
  sessions upstream. It must only push **this lab’s local** sessions (backed by
  `vr4mice.Dataset` with `Collab` lab == `DJ_LAB`) — **not** collaborator
  datasets. See §D.

If populate/fetch logs warn about stub or incomplete mice, treat that as a signal
to run `sync_mice` before relying on GUI metadata or parent consistency.

---

## When you need `run_base.py`

Use **`python run_base.py …`** only for **recovery and parent-DB sync**:

| Mode | Purpose |
|------|---------|
| `recover_base` | Replication check → optional orphan cleanup → rebuild base from GUI `.npy` |
| `sync_mice` | Parent → local Mouse (+ Surgery, score sheets) for stub/incomplete session mice |
| `sync_exp` | **Optional.** Local → parent missing `exp.Session` (this lab only; not collab) |
| `cleanup_mice` | Remove **stub** mice with no local Session (lighter than recover orphans) |

Session files should still exist under `/data/data` and/or `/data/processed`.

### Safety invariants (read this first)

1. **Never delete on main.** Parent `mice` / `exp` are read for `sync_mice`
   (fetch only) and may receive **inserts** of missing sessions from optional
   `sync_exp`. No mode deletes or overwrites existing parent rows.
2. **Local deletes are Dataset orphans only** (via `recover_base --force`):
   remove local `exp.Session` / `mice.Mouse` (and related score/surgery sheets)
   that have **no** matching `vr4mice.Dataset` on this rig. Rows that match a
   Dataset are kept. Recover populate only rebuilds Dataset-backed GUI files,
   so cleanup and rebuild stay consistent.
3. **`cleanup_mice` is narrower:** local **stub** `Mouse` rows with **no**
   `exp.Session` (dry-run by default). Prefer `recover_base` for Dataset-based
   orphan cleanup.
4. **`sync_mice` may replace** local Mouse/Surgery/score-sheet rows for stub
   mice (same primary key, `replace=True`) — that is metadata refresh, not
   orphan deletion, and does not cascade into Sessions.

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
| `DJ_MAIN_HOST` (+ optional user/pwd) | Parent: **pull** mice (`sync_mice`); optional **push** local sessions (`sync_exp`) |

---

## 2. Why replication must be off for cleaning

Local `mice` / `exp` are often a **MySQL replica** of the lab parent DB.

Orphan **cleanup** (`recover_base --force`) **deletes only on the local DB**:
`exp.Session` / `mice.Mouse` rows with no matching `vr4mice.Dataset` here.
It never deletes on the parent.

That is unsafe while replication is active:

1. **Replica SQL/IO still running** — parent changes can re-insert or overwrite
   rows you just deleted, or stop replication with conflicts mid-cleanup.
2. **Read-only replica** — deletes fail or leave a half-updated DB.
3. **Cleanup is a local decision** — “orphan” means “no `vr4mice.Dataset` here”,
   not “delete on the parent registry”.

**So:** stop replication before `--force` cleanup. The script **blocks** if
replica IO/SQL is `Yes` or the DB is `read_only` / `super_read_only`.

`sync_mice` / `sync_exp` use a **second** connection (`DJ_MAIN_HOST`) and do
not require replica threads stopped — but `recover_base` always checks first
because `--force` can delete.

**Check** status (does **not** stop replication):

```bash
make -f mysql.mk replication-summary
# Look at Replica_IO_Running / Replica_SQL_Running (or Slave_* on MySQL 5.7).
```

If either is `Yes`, **you** must stop replication before cleanup (this makefile
target only reports status):

```sql
-- MySQL 8+
STOP REPLICA;
-- also ensure writable if needed:
-- SET GLOBAL read_only = OFF; SET GLOBAL super_read_only = OFF;

-- MySQL 5.7
STOP SLAVE;
```

After recover / `sync_mice` / `sync_exp` look consistent, re-enable yourself
(`START REPLICA;` / `START SLAVE;`) if that is your lab’s normal setup.

---

## 3. Step-by-step recovery

### A — credentials + replication

1. Set `DJ_HOST` and `DJ_MAIN_*` in `.env`.
2. Run `make -f mysql.mk replication-summary` to **inspect** status (it does not
   stop anything). If replica IO/SQL is `Yes`, stop replication yourself
   (`STOP REPLICA` / `STOP SLAVE`) and ensure the DB is writable before
   `--force` cleanup.

### B — preview orphans (deletes dry-run; populate still runs)

```bash
python run_base.py recover_base
```

Lists Session/Mouse with no matching `vr4mice.Dataset` (no deletes without
`--force`), then rebuilds base **only for Dataset-backed** GUI `.npy` files
under `/data/data` + `/data/processed`. This is **not** fully read-only:
`sync_days` may rewrite `.npy` day fields and populate may insert missing
Dataset-backed Sessions. **Read the “would delete …” list** before `--force`.

### C — optional destructive cleanup

Only if the orphan list is OK:

```bash
python run_base.py recover_base --force
```

**Caution — future mice:** `--force` deletes any local mouse **not** referenced
by a Dataset — including mice synced for upcoming experiments. Prefer dry-run
first.

Recover populate is Dataset-gated, so a second `--force` will not delete
Sessions it just rebuilt (they match Dataset). GUI files without Dataset are
skipped (run normal `populate` first if you need new Datasets).

Lighter cleanup (stubs with **no** Session only):

```bash
python run_base.py cleanup_mice          # dry-run
python run_base.py cleanup_mice --force
```

### D — sync with parent

```bash
python run_base.py sync_mice   # parent → local mouse metadata (stubs → full)
# optional — only if this rig should publish sessions upstream:
python run_base.py sync_exp    # local → parent missing sessions (needs write on main exp)
```

Run **`sync_mice` whenever new mice appeared** as stubs or incomplete local
records after populate/recover. Skip only if every session mouse already has a
full Mouse row (no stub warnings). `sync_mice` also pulls `Strain` rows before
Mouse replace so FK inserts succeed.

**`sync_exp` is optional** and is **not** part of normal recovery. Use it only
when you intentionally need missing sessions on the parent `exp` schema.

It is constrained to **local mice/sessions for this lab**, not collab:

- Candidate sessions must match a local `vr4mice.Dataset`
  (`mouse_name_YYYY-MM-DD_attempt`).
- If `vr4mice.Collab` is populated, only datasets whose `Labs.lab` equals
  `DJ_LAB` are pushed; collaborator labs are skipped.
- Sessions that exist only via registry/replica (no local Dataset) are never
  pushed.
- Parent existence is matched by **`(mouse_name, doe, attempt)`**, not local
  `day`. New rows get `day` from the parent mouse timeline.

Set `DJ_LAB` when Collab rows exist. Unit tests cover the local-vs-collab
filter (`tests/unit/test_base_schema_sync.py`).

### E — optional GUI menu

```bash
python run.py fetch
```

### F — resume normal cron

```bash
python run.py populate   # GUI=True still fills exp/mice for new sessions
```

---

## 4. Minimal happy path

```text
1. DJ_MAIN_* in .env; replication OFF
2. python run_base.py recover_base
3. python run_base.py recover_base --force   # only if orphan list is OK
4. python run_base.py sync_mice             # required if new/stub mice appeared
5. python run_base.py sync_exp              # optional; local non-collab only
6. Re-enable replication when both sides look consistent
7. Resume: python run.py populate
   # when new mice appear later → sync_mice again (+ fetch if GUI needs update)
```

---

## 5. Tests

`tests/unit/test_base_schema_sync.py` — stubs, sync direction, replication gate,
orphan dry-run, sync_days helpers, GUI⇒base schema selection, `run_base` modes,
and **`sync_exp` local-vs-collab filtering**.
