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
  if [[ -f .env.compose ]]; then
    COMPOSE_CMD=(docker compose --env-file .env.compose)
  else
    COMPOSE_CMD=(docker compose)
  fi

  UID_VAL="${UID:-$(id -u)}"
  GID_VAL="${GID:-$(id -g)}"
  USER_NAME="${USER_NAME:-$(id -un)}"
  # UID is readonly in bash; pass via env(1) to docker compose instead of export.
  export GID="${GID_VAL}" USER_NAME COMPOSE_PROJECT

  BASE_INSTALL='mkdir -p /app/.local /app/.cache/pip /app/.cache/matplotlib && python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/'
}

vr4mice_compose_env() {
  env UID="${UID_VAL}" GID="${GID_VAL}" USER_NAME="${USER_NAME}" TAG="${TAG:-}" "$@"
}

vr4mice_git_info() {
  git log -n 1 | grep commit > git_commit && git status --porcelain >> git_commit
}

vr4mice_compose_up() {
  vr4mice_compose_env "${COMPOSE_CMD[@]}" -p "${COMPOSE_PROJECT}" up -d "$@"
}

vr4mice_exec_client() {
  "${COMPOSE_CMD[@]}" -p "${COMPOSE_PROJECT}" exec -T --user "${USER_NAME}" client bash -c "$1"
}

vr4mice_base_install() {
  vr4mice_exec_client "${BASE_INSTALL}"
}

vr4mice_check_env_file() {
  local env_file="$1"
  local example_file="$2"
  if [[ ! -f "${env_file}" ]]; then
    echo "Error: ${env_file} is required (copy from ${example_file})." >&2
    return 1
  fi
  if grep -qE '^DJ_PWD=(your-.*-password|change-me|simple)\s*$' "${env_file}" 2>/dev/null \
    && grep -qE '^DJ_HOST=your-' "${env_file}" 2>/dev/null; then
    echo "Error: set real DJ_HOST / DJ_USER / DJ_PWD in ${env_file} before running cron." >&2
    return 1
  fi
}

vr4mice_run_cron_scenario() {
  local aws_mode="${1:-local}"

  if [[ "${aws_mode}" == "aws" ]]; then
    vr4mice_check_env_file ".env-aws" ".env-aws.example"
  else
    vr4mice_check_env_file ".env" ".env.example"
  fi

  local cmd="${BASE_INSTALL} && python cron_scenario.py"
  if [[ "${aws_mode}" == "aws" ]]; then
    cmd="${cmd} --aws"
  fi
  vr4mice_exec_client "${cmd}"
}
