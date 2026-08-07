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

---

## When you need `run_base.py`

Use **`python run_base.py …`** only for **recovery and parent-DB sync**:

| Mode | Purpose |
|------|---------|
| `recover_base` | Replication check → optional orphan cleanup → rebuild base from GUI `.npy` |
| `sync_mice` | Parent → local Mouse (+ Surgery, score sheets) for stub/incomplete session mice |
| `sync_exp` | Local → parent missing `exp.Session` (+ `SessionScoreSheet`) |
| `cleanup_mice` | Remove **stub** mice with no local Session (lighter than recover orphans) |

Session files should still exist under `/data/data` and/or `/data/processed`.

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
| `DJ_MAIN_HOST` (+ optional user/pwd) | Parent: **pull** mice (`sync_mice`), **push** sessions (`sync_exp`) |

---

## 2. Why replication must be off for cleaning

Local `mice` / `exp` are often a **MySQL replica** of the lab parent DB.

Orphan **cleanup** (`recover_base --force`) **deletes** local `exp.Session` /
`mice.Mouse` rows that have no matching `vr4mice.Dataset` on this rig.

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

```bash
make -f mysql.mk replication-summary
```

---

## 3. Step-by-step recovery

### A — credentials + replication

1. Set `DJ_HOST` and `DJ_MAIN_*` in `.env`.
2. Confirm replication is off / DB writable.

### B — preview orphans (no deletes)

```bash
python run_base.py recover_base
```

Lists Session/Mouse with no matching `vr4mice.Dataset`, then tries to populate
base from `/data/data` + `/data/processed`. **Read the “would delete …” list.**

### C — optional destructive cleanup

Only if the orphan list is OK:

```bash
python run_base.py recover_base --force
```

**Caution — future mice:** `--force` deletes any local mouse **not** referenced
by a Dataset — including mice synced for upcoming experiments. Prefer dry-run
first.

Lighter cleanup (stubs with **no** Session only):

```bash
python run_base.py cleanup_mice          # dry-run
python run_base.py cleanup_mice --force
```

### D — sync with parent

```bash
python run_base.py sync_mice   # parent → local mouse metadata (stubs → full)
python run_base.py sync_exp    # local → parent missing sessions (needs write on main exp)
```

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
4. python run_base.py sync_mice
5. python run_base.py sync_exp
6. Re-enable replication when both sides look consistent
7. Resume: python run.py populate
```

---

## 5. Tests

`tests/unit/test_base_schema_sync.py` — stubs, sync direction, replication gate,
orphan dry-run, sync_days helpers, GUI⇒base schema selection, `run_base` modes.
