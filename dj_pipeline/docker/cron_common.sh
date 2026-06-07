#!/usr/bin/env bash
# Shared helpers for vr4mice cron scripts (sourced, not executed directly).

vr4mice_cron_init() {
  CRON_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
  cd "${CRON_DIR}"

  if [[ -f .env.compose ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env.compose
    set +a
  fi

  COMPOSE_PROJECT="${COMPOSE_PROJECT:-vr4mice}"
  DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
  if [[ -f .env.compose ]]; then
    DOCKER_COMPOSE="docker compose --env-file .env.compose"
  fi
  UID_VAL="${UID:-$(id -u)}"
  GID_VAL="${GID:-$(id -g)}"
  USER_NAME="${USER_NAME:-$(id -un)}"
  export UID="${UID_VAL}" GID="${GID_VAL}" USER_NAME COMPOSE_PROJECT

  BASE_INSTALL='mkdir -p /app/.local /app/.cache/pip && python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/'
}

vr4mice_git_info() {
  git log -n 1 | grep commit > git_commit && git status --porcelain >> git_commit
}

vr4mice_compose_up() {
  UID="${UID_VAL}" GID="${GID_VAL}" USER_NAME="${USER_NAME}" \
    ${DOCKER_COMPOSE} -p "${COMPOSE_PROJECT}" up -d "$@"
}

vr4mice_exec_client() {
  ${DOCKER_COMPOSE} -p "${COMPOSE_PROJECT}" exec --user "${USER_NAME}" client bash -c "$1"
}

vr4mice_base_install() {
  vr4mice_exec_client "${BASE_INSTALL}"
}

vr4mice_source_env_file() {
  local env_file="$1"
  if [[ -f "${env_file}" ]]; then
    echo "set -a && source \"${env_file}\" && set +a &&"
  fi
}

vr4mice_run_cron_scenario() {
  local aws_mode="${1:-}"
  local env_file="${2:-}"
  if [[ "${aws_mode}" == "aws" && -n "${env_file}" && ! -f "${env_file}" ]]; then
    echo "Error: ${env_file} is required for AWS cron runs." >&2
    return 1
  fi
  local cmd="${BASE_INSTALL}"
  cmd="${cmd} $(vr4mice_source_env_file "${env_file}") python cron_scenario.py"
  if [[ "${aws_mode}" == "aws" ]]; then
    cmd="${cmd} --aws"
  fi
  vr4mice_exec_client "${cmd}"
}
