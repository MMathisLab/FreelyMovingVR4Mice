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

# Docker exit 125 (and friends) used to abort make with no message when set -e
# hit a failed `docker ps` (usually not in the docker group / bad socket).
docker_names=""
if ! docker_names="$(docker ps -a --format '{{.Names}}' 2>&1)"; then
  warn "Cannot talk to Docker (needed for compose conflict check)."
  hint "Command failed: docker ps -a"
  hint "${docker_names}"
  hint "As user $(id -un): groups=$(id -Gn)"
  hint "Fix: sudo usermod -aG docker $(id -un) && newgrp docker   # then retry"
  hint "Or run: newgrp docker   # if already in group but shell is stale"
  exit 125
fi

conflicts=0

compose_project_of() {
  docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$1" 2>/dev/null || true
}

check_named_container() {
  local name="$1"
  local kind="$2"
  if ! printf '%s\n' "${docker_names}" | grep -qx "${name}"; then
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
    # Do not let a failed `docker compose` abort this script under set -e
    # (was a silent make Error 125 with stderr discarded).
    compose_ps_err=""
    if ! ours_ids="$(bash docker/compose_env.sh compose ps -q db 2>/dev/null)"; then
      compose_ps_err=1
      ours_ids=""
    fi
    ours="$(printf '%s\n' "${ours_ids}" | sed '/^$/d' | wc -l | tr -d ' ')"
    if [ -n "${compose_ps_err}" ]; then
      warn "Port ${DB_PORT} is in use, but 'docker compose ps' failed — cannot tell if it is this project."
      hint "As $(id -un): try  docker compose version  and  newgrp docker"
      hint "If this is the existing vr4mice DB and you only need a new client: VR4MICE_COMPOSE_FORCE=1 make client_up"
      conflicts=1
    elif [ "${ours}" = "0" ]; then
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
