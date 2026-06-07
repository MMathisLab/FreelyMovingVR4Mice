#!/usr/bin/env bash
# Warn or block when this stack would collide with an existing vr4mice deployment.
# Usage: check_compose_conflict.sh [COMPOSE_PROJECT]
# Proceed despite conflicts: VR4MICE_COMPOSE_FORCE=1

set -euo pipefail

COMPOSE_PROJECT="${1:-vr4mice}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_DIR}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
DB_NAME="${DB_CONTAINER_NAME:-vr4mice_db}"
CLIENT_NAME="${CLIENT_CONTAINER_NAME:-vr4mice_${USER}}"
CLIENT_NAME="${CLIENT_NAME//\$\{USER\}/${USER:-unknown}}"
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
      hint "Then set a unique COMPOSE_PROJECT in .env before make up_all (required if other vr4mice_* projects exist on this host)."
    fi
    conflicts=1
  fi
}

check_named_container "${DB_NAME}" "Database"
check_named_container "${CLIENT_NAME}" "Client"

if command -v ss >/dev/null 2>&1; then
  if ss -ltn | awk '{print $4}' | grep -q ":${DB_PORT}$"; then
    ours="$(${DOCKER_COMPOSE} -p "${COMPOSE_PROJECT}" ps -q db 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${ours}" = "0" ]; then
      warn "Port ${DB_PORT} is already in use on this host."
      hint "Another MySQL/vr4mice stack may be running. Use a different DB_PORT and COMPOSE_PROJECT in .env."
      conflicts=1
    fi
  fi
fi

other_projects="$(docker ps -a \
  --filter 'label=com.docker.compose.project' \
  --format '{{.Label "com.docker.compose.project"}}' 2>/dev/null \
  | grep -E '^vr4mice' | sort -u | grep -vx "${COMPOSE_PROJECT}" || true)"
if [ -n "${other_projects}" ] && [ "${COMPOSE_PROJECT}" = "vr4mice" ]; then
  warn "Other vr4mice compose project(s) already on this server:"
  while IFS= read -r p; do
    [ -n "${p}" ] && hint "'${p}'"
  done <<< "${other_projects}"
  hint "If this is a second deployment, set in .env before make up_all:"
  hint "  COMPOSE_PROJECT=vr4mice_<yourname>"
  hint "  DB_CONTAINER_NAME=vr4mice_db_<yourname>"
  hint "  CLIENT_CONTAINER_NAME=vr4mice_\${USER}_<yourname>"
  hint "  DB_PORT=<free port>"
  conflicts=1
fi

if [ "${conflicts}" -eq 0 ]; then
  exit 0
fi

echo >&2
if [ "${VR4MICE_COMPOSE_FORCE:-}" = "1" ]; then
  warn "VR4MICE_COMPOSE_FORCE=1 set — continuing despite conflicts."
  exit 0
fi

warn "Aborting. To override: VR4MICE_COMPOSE_FORCE=1 make up_all"
exit 1
