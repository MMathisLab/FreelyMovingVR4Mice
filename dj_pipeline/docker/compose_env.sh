#!/usr/bin/env bash
# Load .env.compose with shell expansion (${USER}, etc.) for Make, cron, and compose.
# Usage:
#   compose_env.sh get COMPOSE_PROJECT
#   compose_env.sh compose [docker compose args...]
#   compose_env.sh load   # print export statements (eval in shell)

set -euo pipefail

vr4mice_repo_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

vr4mice_load_compose_env() {
  cd "$(vr4mice_repo_dir)"

  export USER="${USER:-$(id -un)}"
  local compose_override="${COMPOSE_PROJECT:-}"

  if [[ -f .env.compose ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env.compose
    set +a
  elif [[ -f .env ]]; then
    # Migration: COMPOSE_PROJECT may still live in .env
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi

  if [[ -n "${compose_override}" ]]; then
    COMPOSE_PROJECT="${compose_override}"
  fi

  # Safety: expand ${USER} if it was not expanded during source (e.g. single-quoted values)
  for name in COMPOSE_PROJECT CLIENT_CONTAINER_NAME DB_CONTAINER_NAME; do
    if [[ -n "${!name:-}" ]]; then
      printf -v "${name}" '%s' "${!name//\$\{USER\}/${USER}}"
      export "${name}"
    fi
  done

  COMPOSE_PROJECT="${COMPOSE_PROJECT:-vr4mice}"
  export COMPOSE_PROJECT

  local detect_script
  detect_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/detect_mysql_image.sh"
  if [[ -z "${DB_IMAGE:-}" ]]; then
    DB_IMAGE="$(bash "${detect_script}" "${DB_DATA_PATH:-}")"
  fi
  export DB_IMAGE
  bash "${detect_script}" check "${DB_DATA_PATH:-}" "${DB_IMAGE}" 2>/dev/null || true
}

vr4mice_compose_exec() {
  vr4mice_load_compose_env
  local uid_val="${UID:-$(id -u)}"
  local gid_val="${GID:-$(id -g)}"
  local user_name="${USER_NAME:-$(id -un)}"
  local -a args=(-p "${COMPOSE_PROJECT}")
  if [[ -f .env.compose ]]; then
    args+=(--env-file .env.compose)
  fi
  # Export expanded values so they override literal ${USER} from --env-file.
  exec env \
    UID="${uid_val}" \
    GID="${gid_val}" \
    USER="${USER}" \
    USER_NAME="${user_name}" \
    TAG="${TAG:-}" \
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" \
    CLIENT_CONTAINER_NAME="${CLIENT_CONTAINER_NAME:-}" \
    DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-}" \
    DB_IMAGE="${DB_IMAGE:-mysql:8.0}" \
    docker compose "${args[@]}" "$@"
}

case "${1:-}" in
  get)
    vr4mice_load_compose_env
    name="${2:?variable name required}"
    echo "${!name}"
    ;;
  load)
    vr4mice_load_compose_env
    # shellcheck disable=SC2013
    for name in COMPOSE_PROJECT CLIENT_CONTAINER_NAME DB_CONTAINER_NAME DB_PORT DB_IMAGE; do
      if [[ -n "${!name:-}" ]]; then
        printf 'export %s=%q\n' "${name}" "${!name}"
      fi
    done
    printf 'export USER=%q\n' "${USER}"
    ;;
  compose)
    shift
    vr4mice_compose_exec "$@"
    ;;
  *)
    echo "Usage: compose_env.sh {get VAR|load|compose [args...]}" >&2
    exit 1
    ;;
esac
