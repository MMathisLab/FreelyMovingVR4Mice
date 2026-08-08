#!/usr/bin/env bash
# Sync the mice registry from DJ_MAIN_* onto local DJ_HOST using mysqldump/mysql.
#
# Run on the host from dj_pipeline/:
#   make -f mysql.mk sync-mice-from-main
#   make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
#
# Never deletes on main. Loads with FOREIGN_KEY_CHECKS=0 and REPLACE.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

die() { echo "error: $*" >&2; exit 1; }
need() { [[ -n "${!1:-}" ]] || die "$1 is not set (put it in .env)"; }

need DJ_HOST
need DJ_USER
need DJ_PWD
need DJ_MAIN_HOST

MAIN_USER="${DJ_MAIN_USER:-$DJ_USER}"
MAIN_PWD="${DJ_MAIN_PWD:-$DJ_PWD}"

split_host_port() {
  local raw="$1"
  if [[ "$raw" == *:* ]]; then
    _HOST="${raw%%:*}"
    _PORT="${raw##*:}"
  else
    _HOST="$raw"
    _PORT="3306"
  fi
}

split_host_port "$DJ_HOST"
LOCAL_HOST="$_HOST"
LOCAL_PORT="$_PORT"

split_host_port "$DJ_MAIN_HOST"
MAIN_HOST="$_HOST"
MAIN_PORT="$_PORT"

command -v mysql >/dev/null || die "mysql client not found on PATH"
command -v mysqldump >/dev/null || die "mysqldump not found on PATH"

# Lab MySQL is usually plain TCP.
SSL_OPTS=(--ssl-mode=DISABLED)
MYSQL_LOCAL=(mysql "${SSL_OPTS[@]}" -h "$LOCAL_HOST" -P "$LOCAL_PORT" -u "$DJ_USER" -p"$DJ_PWD")
MYSQL_MAIN=(mysql "${SSL_OPTS[@]}" -h "$MAIN_HOST" -P "$MAIN_PORT" -u "$MAIN_USER" -p"$MAIN_PWD")

DUMP_BASE=(mysqldump "${SSL_OPTS[@]}" -h "$MAIN_HOST" -P "$MAIN_PORT" -u "$MAIN_USER" -p"$MAIN_PWD"
  --single-transaction --routines=false --triggers=false --events=false
  --set-gtid-purged=OFF --no-create-info --replace --complete-insert --hex-blob)
if mysqldump --help 2>/dev/null | grep -q -- '--column-statistics'; then
  DUMP_BASE+=(--column-statistics=0)
fi

echo "Local:  ${LOCAL_HOST}:${LOCAL_PORT}"
echo "Main:   ${MAIN_HOST}:${MAIN_PORT}"

if [[ "$LOCAL_HOST" == "$MAIN_HOST" && "$LOCAL_PORT" == "$MAIN_PORT" ]]; then
  die "DJ_HOST and DJ_MAIN_HOST are the same host:port (${LOCAL_HOST}:${LOCAL_PORT})"
fi

# @@port is the server's *internal* listen port (often 3306 in Docker), not the
# host-mapped TCP port — so do not use it to tell local/main apart.
local_uuid="$("${MYSQL_LOCAL[@]}" -N -e "SELECT @@server_uuid" 2>/dev/null | tr -d '\r')"
main_uuid="$("${MYSQL_MAIN[@]}" -N -e "SELECT @@server_uuid" 2>/dev/null | tr -d '\r')"
[[ -n "$local_uuid" && -n "$main_uuid" ]] || die "could not connect to local/main MySQL"
echo "server_uuid: local=${local_uuid}  main=${main_uuid}"
if [[ "$local_uuid" == "$main_uuid" ]]; then
  die "local and main hit the same MySQL instance (@@server_uuid=${local_uuid})"
fi

mapfile -t MAIN_TABLES < <("${MYSQL_MAIN[@]}" -N -e "SHOW TABLES FROM mice" 2>/dev/null | tr -d '\r')
mapfile -t LOCAL_TABLES < <("${MYSQL_LOCAL[@]}" -N -e "SHOW TABLES FROM mice" 2>/dev/null | tr -d '\r')

has_main() { printf '%s\n' "${MAIN_TABLES[@]}" | grep -Fxq -- "$1"; }
has_local() { printf '%s\n' "${LOCAL_TABLES[@]}" | grep -Fxq -- "$1"; }

# Prefer preferred name; fall back to alt (__ vs _). Require a local target.
resolve_pair() {
  local preferred="$1" alt="$2" main_t="" local_t=""
  if has_main "$preferred"; then
    main_t="$preferred"
  elif [[ -n "$alt" ]] && has_main "$alt"; then
    main_t="$alt"
  else
    return 1
  fi
  if has_local "$main_t"; then
    local_t="$main_t"
  elif [[ -n "$alt" && "$alt" != "$main_t" ]] && has_local "$alt"; then
    local_t="$alt"
  elif [[ -n "$preferred" && "$preferred" != "$main_t" ]] && has_local "$preferred"; then
    local_t="$preferred"
  else
    die "main has mice.\`${main_t}\` but no matching local table"
  fi
  echo "${main_t}|${local_t}"
}

CANDIDATES=(
  "#strain|"
  "#surgery_type|"
  "#mouse_licensing_geneva|"
  "#mouse_score_sheet__body_condition|#mouse_score_sheet_body_condition"
  "#mouse_score_sheet__general_assay|#mouse_score_sheet_general_assay"
  "#mouse_score_sheet__housing_assesment|#mouse_score_sheet_housing_assesment"
  "mouse|"
  "surgery|"
  "mouse_score_sheet|"
  "mouse_score_sheet__water_restriction|mouse_score_sheet_water_restriction"
)

PAIRS=()
for spec in "${CANDIDATES[@]}"; do
  pref="${spec%%|*}"
  alt="${spec#*|}"
  pair="$(resolve_pair "$pref" "$alt" || true)"
  [[ -n "${pair:-}" ]] && PAIRS+=("$pair")
done

[[ ${#PAIRS[@]} -gt 0 ]] || die "no known mice tables found on main"

echo "Tables (main → local):"
for pair in "${PAIRS[@]}"; do
  echo "  ${pair%%|*}  →  ${pair##*|}"
done

WHERE=""
if [[ -n "${MOUSE:-}" ]]; then
  IFS=',' read -r -a NAMES <<< "$MOUSE"
  quoted=()
  for n in "${NAMES[@]}"; do
    n="$(echo "$n" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [[ -z "$n" ]] && continue
    n="${n//\'/\'\'}"
    quoted+=("'$n'")
  done
  [[ ${#quoted[@]} -gt 0 ]] || die "MOUSE= was set but no names parsed"
  joined="$(IFS=,; echo "${quoted[*]}")"
  WHERE="mouse_name IN (${joined})"
  echo "Filter: ${WHERE}"
fi

TMPDIR_SYNC="$(mktemp -d "${TMPDIR:-/tmp}/sync_mice.XXXXXX")"
trap 'rm -rf "$TMPDIR_SYNC"' EXIT
COMBINED="${TMPDIR_SYNC}/all.sql"

{
  echo "SET FOREIGN_KEY_CHECKS=0;"
  echo "SET UNIQUE_CHECKS=0;"
  echo "SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';"
} >"$COMBINED"

for pair in "${PAIRS[@]}"; do
  main_t="${pair%%|*}"
  local_t="${pair##*|}"
  part="${TMPDIR_SYNC}/part.sql"
  echo "Dumping mice.\`${main_t}\` ..."

  dump_cmd=("${DUMP_BASE[@]}" mice --tables "$main_t")
  if [[ -n "$WHERE" ]]; then
    case "$main_t" in
      mouse|surgery|mouse_score_sheet|mouse_score_sheet__water_restriction|mouse_score_sheet_water_restriction)
        dump_cmd+=(--where="$WHERE")
        ;;
    esac
  fi

  if ! "${dump_cmd[@]}" >"$part" 2>"${TMPDIR_SYNC}/dump.err"; then
    grep -v "Using a password" "${TMPDIR_SYNC}/dump.err" >&2 || true
    die "mysqldump failed for mice.\`${main_t}\`"
  fi
  grep -v "Using a password" "${TMPDIR_SYNC}/dump.err" >&2 || true

  if [[ "$main_t" != "$local_t" ]]; then
    python3 - "$part" "$main_t" "$local_t" <<'PY'
import sys
path, main_t, local_t = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, "r", encoding="utf-8", errors="replace").read()
for a, b in (
    (f"`mice`.`{main_t}`", f"`mice`.`{local_t}`"),
    (f"INTO `{main_t}`", f"INTO `{local_t}`"),
    (f"TABLE `{main_t}`", f"TABLE `{local_t}`"),
):
    text = text.replace(a, b)
open(path, "w", encoding="utf-8").write(text)
PY
    echo "  rewrote ${main_t} → ${local_t}"
  fi
  cat "$part" >>"$COMBINED"
done

{
  echo "SET UNIQUE_CHECKS=1;"
  echo "SET FOREIGN_KEY_CHECKS=1;"
} >>"$COMBINED"

echo "Loading into local mice ..."
"${MYSQL_LOCAL[@]}" mice <"$COMBINED"

# SessionScoreSheet FKs to mouse_score_sheet__water_restriction. Local DJ may
# also write mouse_score_sheet_water_restriction — keep __ complete.
if has_local "mouse_score_sheet__water_restriction" \
  && has_local "mouse_score_sheet_water_restriction"; then
  echo "Merging water_restriction _ → __ (SessionScoreSheet FK target) ..."
  "${MYSQL_LOCAL[@]}" -e \
    "INSERT IGNORE INTO mice.mouse_score_sheet__water_restriction
     SELECT * FROM mice.mouse_score_sheet_water_restriction;"
fi

echo "Done."
if [[ -n "$WHERE" ]]; then
  "${MYSQL_LOCAL[@]}" -e \
    "SELECT mouse_name, mouse_id, strain FROM mice.mouse WHERE ${WHERE} ORDER BY mouse_name;"
else
  "${MYSQL_LOCAL[@]}" -N -e "SELECT COUNT(*) AS local_mice FROM mice.mouse;"
fi
