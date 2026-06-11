#!/usr/bin/env bash
# Warn or block when this stack would collide with an existing vr4mice deployment.
# Usage: check_compose_conflict.sh [COMPOSE_PROJECT]
# Proceed despite conflicts: VR4MICE_COMPOSE_FORCE=1

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_DIR}"

if [[ -n "${1:-}" ]]; then
  export COMPOSE_PROJECT="$1"
fi
eval "$(bash docker/compose_env.sh load)"

DB_NAME="${DB_CONTAINER_NAME:-vr4mice_db}"
CLIENT_NAME="${CLIENT_CONTAINER_NAME:-vr4mice_${USER}}"
DB_PORT="${DB_PORT:-3309}"

warn() { printf 'WARNING: %s\n' "$*" >&2; }
hint() { printf '  → %s\n' "$*" >&2; }

conflicts=0

compose_project_of() {
  docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$1" 2>/dev/null || true
}

check_named_container() {
  local name="$1"
  local kind="$2"
  if ! docker ps -a --format '{{.Names}}' | grep -qx "${name}"; then
    return 0
  fi
  local other_project
  other_project="$(compose_project_of "${name}")"
  if [ -n "${other_project}" ] && [ "${other_project}" != "${COMPOSE_PROJECT}" ]; then
    warn "${kind} container '${name}' already exists (compose project '${other_project}')."
    hint "Your COMPOSE_PROJECT is '${COMPOSE_PROJECT}' — pick a new project name to avoid replacing it."
    if [ "${other_project}" = "mysqltest" ]; then
      hint "Legacy stack: stop it with  COMPOSE_PROJECT=mysqltest make down_all"
      hint "Then set COMPOSE_PROJECT in .env.compose to match your stack (or stop the legacy stack first)."
    fi
    conflicts=1
  fi
}

check_named_container "${DB_NAME}" "Database"
check_named_container "${CLIENT_NAME}" "Client"

if command -v ss >/dev/null 2>&1; then
  if ss -ltn | awk '{print $4}' | grep -q ":${DB_PORT}$"; then
    ours="$(bash docker/compose_env.sh compose ps -q db 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${ours}" = "0" ]; then
      warn "Port ${DB_PORT} is already in use on this host."
      hint "Another MySQL/vr4mice stack may be running. Use a different DB_PORT and COMPOSE_PROJECT in .env.compose."
      conflicts=1
    fi
  fi
fi

# Informational only: other vr4mice_* projects on the host are fine if container names and DB_PORT differ.
other_projects="$(docker ps -a \
  --filter 'label=com.docker.compose.project' \
  --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null \
  | grep -E '^vr4mice' | sort -u | grep -vx "${COMPOSE_PROJECT}" || true)"
if [ -n "${other_projects}" ] && [ "${COMPOSE_PROJECT}" = "vr4mice" ]; then
  warn "Other vr4mice compose project(s) on this host (OK if you reuse your own container names):"
  while IFS= read -r p; do
    [ -n "${p}" ] && hint "'${p}'"
  done <<< "${other_projects}"
  hint "For an additional deployment, use unique names in .env.compose (COMPOSE_PROJECT, DB_CONTAINER_NAME, CLIENT_CONTAINER_NAME, DB_PORT)."
fi

if [ "${conflicts}" -eq 0 ]; then
  exit 0
fi

echo >&2
if [ "${VR4MICE_COMPOSE_FORCE:-}" = "1" ]; then
  warn "VR4MICE_COMPOSE_FORCE=1 set — continuing despite conflicts."
  warn "If client/db containers belong to another compose project, up may succeed but exec will fail."
  warn "Prefer fixing .env.compose (COMPOSE_PROJECT + container names) over forcing."
  exit 0
fi

warn "Aborting. To override: VR4MICE_COMPOSE_FORCE=1 make up_all"
exit 1
