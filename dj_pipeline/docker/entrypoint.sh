#!/usr/bin/env bash
set -euo pipefail

: "${USERNAME:=app}"; : "${PUID:=1000}"; : "${PGID:=1000}"
: "${HOME:=/app}"
: "${PYTHONUSERBASE:=/app/.local}"
: "${PIP_CACHE_DIR:=/app/.cache/pip}"
export HOME PYTHONUSERBASE PIP_CACHE_DIR PATH="/app/.local/bin:${PATH}"

vr4mice_app_dirs() {
  mkdir -p /app/.local/bin "${PIP_CACHE_DIR}" /app/processed
}

passwd_has_uid() {
  grep -q "^[^:]*:[^:]*:${PUID}:" /etc/passwd 2>/dev/null
}

group_has_gid() {
  grep -q "^[^:]*:[^:]*:${PGID}:" /etc/group 2>/dev/null
}

# Map host UID/GID to a name so `make bash` / `--user UID:GID` get a normal shell (not "I have no name!").
ensure_runtime_user() {
  if passwd_has_uid; then
    return 0
  fi

  if command -v getent >/dev/null 2>&1 \
    && command -v groupadd >/dev/null 2>&1 \
    && command -v useradd >/dev/null 2>&1; then
    if ! getent group "${PGID}" >/dev/null 2>&1; then
      groupadd -g "${PGID}" "${USERNAME}" 2>/dev/null \
        || groupadd -g "${PGID}" "grp${PGID}" 2>/dev/null \
        || true
    fi
    if ! getent passwd "${PUID}" >/dev/null 2>&1; then
      useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -M -s /bin/bash "${USERNAME}" 2>/dev/null \
        || useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -M -s /bin/sh "${USERNAME}" 2>/dev/null \
        || true
    fi
    return 0
  fi

  # Prebuilt images often lack useradd/groupadd; append minimal nss entries.
  if ! group_has_gid; then
    echo "${USERNAME}:x:${PGID}:" >> /etc/group
  fi
  echo "${USERNAME}:x:${PUID}:${PGID}:${USERNAME}:${HOME}:/bin/bash" >> /etc/passwd
}

run_as_user() {
  export USER="${USERNAME}" LOGNAME="${USERNAME}"
  if command -v gosu >/dev/null 2>&1; then
    if passwd_has_uid && getent passwd "${USERNAME}" >/dev/null 2>&1; then
      exec gosu "${USERNAME}" "$@"
    fi
    exec gosu "${PUID}:${PGID}" "$@"
  fi
  exec "$@"
}

if [ "$(id -u)" -eq 0 ]; then
  ensure_runtime_user

  vr4mice_app_dirs
  chown -R "${PUID}:${PGID}" /app/.local "${PIP_CACHE_DIR}" /app/processed 2>/dev/null || true

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
