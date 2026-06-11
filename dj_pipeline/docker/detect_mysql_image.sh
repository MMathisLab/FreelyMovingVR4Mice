#!/usr/bin/env bash
# Infer mysql:5.7 vs mysql:8.0 from an on-disk datadir (bind-mounted to /var/lib/mysql).
# Empty or missing dirs default to mysql:8.0 (new installs).
#
# Usage:
#   detect_mysql_image.sh [datadir]
#   detect_mysql_image.sh check [datadir] [configured_image]

set -euo pipefail

vr4mice_mysql_datadir_image() {
  local datadir="${1:-}"
  datadir="${datadir%/}"

  if [[ -z "${datadir}" || ! -d "${datadir}" ]]; then
    echo "mysql:8.0"
    return 0
  fi

  # MySQL 8 redo logs live under #innodb_redo/ (or #ib_redo* during early init).
  if [[ -d "${datadir}/#innodb_redo" ]] || compgen -G "${datadir}/#ib_redo*" >/dev/null; then
    echo "mysql:8.0"
    return 0
  fi

  # Classic 5.7 layout (also present after a failed 5.7 -> 8.0 in-place upgrade).
  if [[ -f "${datadir}/ib_logfile0" || -f "${datadir}/ib_logfile1" ]]; then
    echo "mysql:5.7"
    return 0
  fi

  echo "mysql:8.0"
}

vr4mice_mysql_image_check() {
  local datadir="${1:-}"
  local configured="${2:-mysql:8.0}"
  local detected
  detected="$(vr4mice_mysql_datadir_image "${datadir}")"

  if [[ "${configured}" == "${detected}" ]]; then
    return 0
  fi

  echo "Warning: DB_IMAGE=${configured} but datadir looks like ${detected}." >&2
  if [[ "${detected}" == "mysql:5.7" ]]; then
    echo "  Set DB_IMAGE=mysql:5.7 in .env.compose for existing 5.7 data, or wipe the datadir for a fresh MySQL 8 install." >&2
    echo "  To upgrade later: start with 5.7, shut down cleanly (innodb_fast_shutdown=0), then switch to mysql:8.0." >&2
  else
    echo "  Set DB_IMAGE=${detected} in .env.compose, or point DB_DATA_PATH at the correct datadir." >&2
  fi
  return 1
}

case "${1:-}" in
  check)
    vr4mice_mysql_image_check "${2:-}" "${3:-mysql:8.0}"
    ;;
  detect)
    vr4mice_mysql_datadir_image "${2:-}"
    ;;
  -h|--help)
    echo "Usage: detect_mysql_image.sh [datadir]" >&2
    echo "       detect_mysql_image.sh check [datadir] [configured_image]" >&2
    exit 0
    ;;
  *)
    vr4mice_mysql_datadir_image "${1:-}"
    ;;
esac
