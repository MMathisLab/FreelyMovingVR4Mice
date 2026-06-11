#!/usr/bin/env bash
# Expose python/pip on /usr/local/bin so compose PATH finds them without conda activate.
ensure_python_shims() {
  if [ -x /usr/local/bin/python ] || command -v python >/dev/null 2>&1; then
    return 0
  fi

  local py="" candidate pip_bin
  for candidate in \
    "$(PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" command -v python 2>/dev/null || true)" \
    /usr/bin/python3 \
    /usr/bin/python; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
      py="${candidate}"
      break
    fi
  done

  # DeepLabCut base images install Python outside the default runtime PATH.
  if [ -z "${py}" ]; then
    for candidate in /opt/conda/bin/python; do
      if [ -x "${candidate}" ]; then
        py="${candidate}"
        break
      fi
    done
  fi

  if [ -z "${py}" ]; then
    echo "ensure_python_shims: python not found" >&2
    return 1
  fi

  ln -sf "${py}" /usr/local/bin/python
  ln -sf "${py}" /usr/local/bin/python3

  pip_bin="$(dirname "${py}")/pip"
  if [ -x "${pip_bin}" ]; then
    ln -sf "${pip_bin}" /usr/local/bin/pip
    ln -sf "${pip_bin}" /usr/local/bin/pip3
  fi
}
