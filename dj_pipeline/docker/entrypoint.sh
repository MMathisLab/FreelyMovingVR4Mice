#!/usr/bin/env bash
set -euo pipefail

: "${USERNAME:=app}"; : "${PUID:=1000}"; : "${PGID:=1000}"
: "${HOME:=/app}"
: "${PYTHONUSERBASE:=/app/.local}"
: "${PIP_CACHE_DIR:=/app/.cache/pip}"
export HOME USER PYTHONUSERBASE PIP_CACHE_DIR PATH="/app/.local/bin:${PATH}"

vr4mice_app_dirs() {
  mkdir -p /app/.local/bin "${PIP_CACHE_DIR}" /app/processed
}

if [ "$(id -u)" -eq 0 ]; then
  getent group "${PGID}" >/dev/null || groupadd -g "${PGID}" "${USERNAME}" || groupadd -g "${PGID}" "grp${PGID}"
  if ! getent passwd "${PUID}" >/dev/null; then
    useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -s /bin/bash "${USERNAME}" \
      || useradd -u "${PUID}" -g "${PGID}" -d "${HOME}" -s /bin/sh "${USERNAME}"
  fi

  vr4mice_app_dirs
  chown -R "${PUID}:${PGID}" /app/.local "${PIP_CACHE_DIR}" /app/processed

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
      chown -R "${PUID}:${PGID}" "${alt_dir}"
      chmod -R 775 "${alt_dir}"
      rm -rf "${checkpoint_dir}" 2>/dev/null || true
      ln -s "${alt_dir}" "${checkpoint_dir}" 2>/dev/null || true
      echo "Redirected checkpoints directory to: ${alt_dir}"
    fi
  fi

  exec gosu "${PUID}:${PGID}" "$@"
else
  vr4mice_app_dirs || true
  exec "$@"
fi
