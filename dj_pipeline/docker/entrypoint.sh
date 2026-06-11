#!/usr/bin/env bash
set -euo pipefail

: "${USERNAME:=app}"; : "${PUID:=1000}"; : "${PGID:=1000}"
: "${HOME:=/app}"
: "${PYTHONUSERBASE:=/app/.local}"
: "${PIP_CACHE_DIR:=/app/.cache/pip}"

_shims_dir="$(dirname "${BASH_SOURCE[0]}")"
if [ -f "${_shims_dir}/ensure_python_shims.sh" ]; then
  # shellcheck source=docker/ensure_python_shims.sh
  source "${_shims_dir}/ensure_python_shims.sh"
  ensure_python_shims || true
fi

export HOME PYTHONUSERBASE PIP_CACHE_DIR PATH="/app/.local/bin:${PATH}"

vr4mice_app_dirs() {
  mkdir -p /app/.local/bin "${PIP_CACHE_DIR}" /app/processed /app/.cache/matplotlib
}

passwd_has_uid() {
  grep -q "^[^:]*:[^:]*:${PUID}:" /etc/passwd 2>/dev/null
}

passwd_has_name() {
  grep -q "^${USERNAME}:" /etc/passwd 2>/dev/null
}

group_has_gid() {
  grep -q "^[^:]*:[^:]*:${PGID}:" /etc/group 2>/dev/null
}

passwd_uid_of_name() {
  getent passwd "${USERNAME}" 2>/dev/null | cut -d: -f3
}

passwd_name_of_uid() {
  getent passwd "${PUID}" 2>/dev/null | cut -d: -f1
}

runtime_user_matches() {
  local uid gid
  uid="$(passwd_uid_of_name 2>/dev/null || true)"
  gid="$(getent passwd "${USERNAME}" 2>/dev/null | cut -d: -f4 || true)"
  [ -n "${uid}" ] && [ "${uid}" = "${PUID}" ] && [ -n "${gid}" ] && [ "${gid}" = "${PGID}" ]
}

ensure_runtime_group() {
  if group_has_gid; then
    return 0
  fi
  if command -v groupadd >/dev/null 2>&1; then
    groupadd -g "${PGID}" "${USERNAME}" 2>/dev/null \
      || groupadd -g "${PGID}" "grp${PGID}" 2>/dev/null \
      || true
    return 0
  fi
  echo "${USERNAME}:x:${PGID}:" >> /etc/group
}

remove_passwd_user() {
  local account="$1"
  if command -v userdel >/dev/null 2>&1; then
    userdel -r "${account}" 2>/dev/null || userdel "${account}" 2>/dev/null || true
  fi
}

# Map host UID/GID/name so `docker compose exec --user "${USER_NAME}"` matches bind-mount ownership.
ensure_runtime_user() {
  if runtime_user_matches; then
    return 0
  fi

  if command -v getent >/dev/null 2>&1 \
    && command -v groupadd >/dev/null 2>&1 \
    && command -v useradd >/dev/null 2>&1 \
    && command -v usermod >/dev/null 2>&1; then
    ensure_runtime_group

    local uid_owner="" name_uid=""
    uid_owner="$(passwd_name_of_uid 2>/dev/null || true)"
    name_uid="$(passwd_uid_of_name 2>/dev/null || true)"

    # Dockerfile default account has our UID but a different name (e.g. user:1000 → alice:1000).
    if [ -n "${uid_owner}" ] && [ "${uid_owner}" != "${USERNAME}" ] && [ -z "${name_uid}" ]; then
      usermod -l "${USERNAME}" -g "${PGID}" -d "${HOME}" "${uid_owner}" 2>/dev/null || true
      runtime_user_matches && return 0
    fi

    # Name exists but with the wrong UID and the target UID is free (e.g. user:1000 → user:1002).
    if [ -n "${name_uid}" ] && [ "${name_uid}" != "${PUID}" ] && [ -z "${uid_owner}" ]; then
      usermod -u "${PUID}" -g "${PGID}" -d "${HOME}" "${USERNAME}" 2>/dev/null || true
      runtime_user_matches && return 0
    fi

    # Remove stale accounts blocking the desired name or UID (safe at container start).
    if [ -n "${name_uid}" ] && [ "${name_uid}" != "${PUID}" ]; then
      remove_passwd_user "${USERNAME}"
    fi
    uid_owner="$(passwd_name_of_uid 2>/dev/null || true)"
    if [ -n "${uid_owner}" ] && [ "${uid_owner}" != "${USERNAME}" ]; then
      remove_passwd_user "${uid_owner}"
    fi

    if ! getent passwd "${USERNAME}" >/dev/null 2>&1; then
      useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -M -s /bin/bash "${USERNAME}" 2>/dev/null \
        || useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -M -s /bin/sh "${USERNAME}" 2>/dev/null \
        || true
    fi

    if ! runtime_user_matches; then
      echo "entrypoint: failed to map ${USERNAME} to uid=${PUID} gid=${PGID}" >&2
    fi
    return 0
  fi

  # Prebuilt images often lack useradd/groupadd; append minimal nss entries only when free.
  ensure_runtime_group
  if ! passwd_has_name && ! passwd_has_uid; then
    echo "${USERNAME}:x:${PUID}:${PGID}:${USERNAME}:${HOME}:/bin/bash" >> /etc/passwd
  elif ! runtime_user_matches; then
    echo "entrypoint: ${USERNAME} (uid=${PUID}) conflicts with existing passwd entries and useradd is unavailable" >&2
  fi
}

run_as_user() {
  export USER="${USERNAME}" LOGNAME="${USERNAME}"
  if command -v gosu >/dev/null 2>&1; then
    if runtime_user_matches; then
      exec gosu "${USERNAME}" "$@"
    fi
    exec gosu "${PUID}:${PGID}" "$@"
  fi
  exec "$@"
}

if [ "$(id -u)" -eq 0 ]; then
  ensure_runtime_user

  vr4mice_app_dirs
  chown -R "${PUID}:${PGID}" /app/.local "${PIP_CACHE_DIR}" /app/processed /app/.cache 2>/dev/null || true

  if command -v python3 &>/dev/null || command -v python &>/dev/null; then
    checkpoint_dir=$(
      python3 -c "
import deeplabcut
import os
checkpoint_dir = os.path.join(os.path.dirname(deeplabcut.__file__), 'modelzoo', 'checkpoints')
os.makedirs(checkpoint_dir, exist_ok=True)
print(checkpoint_dir)
" 2>/dev/null || python -c "
import deeplabcut
import os
checkpoint_dir = os.path.join(os.path.dirname(deeplabcut.__file__), 'modelzoo', 'checkpoints')
os.makedirs(checkpoint_dir, exist_ok=True)
print(checkpoint_dir)
" 2>/dev/null || true
    )
    if [ -n "${checkpoint_dir}" ] && [ -d "${checkpoint_dir}" ]; then
      alt_dir="/app/processed/dlc_checkpoints"
      mkdir -p "${alt_dir}"
      chown -R "${PUID}:${PGID}" "${alt_dir}" 2>/dev/null || true
      chmod -R 775 "${alt_dir}" 2>/dev/null || true
      rm -rf "${checkpoint_dir}" 2>/dev/null || true
      ln -s "${alt_dir}" "${checkpoint_dir}" 2>/dev/null || true
      echo "Redirected checkpoints directory to: ${alt_dir}"
    fi
  fi

  run_as_user "$@"
else
  export USER="${USERNAME:-$(id -un 2>/dev/null || echo app)}" LOGNAME="${USER}"
  vr4mice_app_dirs || true
  exec "$@"
fi
