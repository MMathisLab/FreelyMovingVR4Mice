#!/usr/bin/env bash
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Please run with bash: bash quick_start.sh"
  exit 1
fi

trap 'echo "${C_YELLOW}Quick start failed at line ${LINENO}.${C_RESET}"' ERR

if command -v tput >/dev/null 2>&1; then
  C_GREEN="$(tput setaf 2)"
  C_YELLOW="$(tput setaf 3)"
  C_BLUE="$(tput setaf 4)"
  C_RESET="$(tput sgr0)"
else
  C_GREEN=""
  C_YELLOW=""
  C_BLUE=""
  C_RESET=""
fi

UID_VAL="$(id -u)"
GID_VAL="$(id -g)"
USER_NAME_VAL="$(id -un)"
TAG_VAL="${TAG:-}"
export PUID="${UID_VAL}" PGID="${GID_VAL}" USER_NAME="${USER_NAME_VAL}" TAG="${TAG_VAL}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_DIR="${SCRIPT_DIR}"
DEFAULT_MOUNT="/mnt/database/vr4mice/vr4mice_database"
DEFAULT_DUMP_DIR="/mnt/data_storage/vr4mice_database_dump"

prompt() {
  local label="$1"
  local default="$2"
  local value
  read -r -p "${C_BLUE}${label}${C_RESET} [${default}]: " value
  if [ -z "${value}" ]; then
    value="${default}"
  fi
  echo "${value}"
}

prompt_yes_no() {
  local label="$1"
  local default="$2"
  local value
  value="$(prompt "${label} (yes/no)" "${default}")"
  value="$(echo "${value}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    yes|no) ;;
    *)
      echo "Please answer yes or no."
      return 1
      ;;
  esac
  echo "${value}"
}

prompt_dir() {
  local label="$1"
  local default="$2"
  local dir
  while true; do
    dir="$(prompt "${label}" "${default}")"
    if [ -d "${dir}" ]; then
      echo "${dir}"
      return
    fi
    echo "${C_YELLOW}Path not found: ${dir}${C_RESET}"
    local action
    action="$(prompt_yes_no "Create it?" "no")" || true
    if [ "${action}" = "yes" ]; then
      mkdir -p "${dir}"
      echo "${dir}"
      return
    fi
    echo "${C_YELLOW}Please re-enter the path.${C_RESET}"
  done
}

spinner_wait() {
  local pid="$1"
  local message="$2"
  local spin='|/-\'
  local i=0
  while kill -0 "${pid}" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r%s %s" "${spin:$i:1}" "${message}"
    sleep 2
  done
  wait "${pid}"
  printf "\r%s\n" "${message} done."
}

table_progress_filter() {
  local enabled="${TABLE_PROGRESS:-yes}"
  enabled="$(echo "${enabled}" | tr '[:upper:]' '[:lower:]')"
  if [ "${enabled}" != "yes" ]; then
    cat
    return
  fi
  awk '
    BEGIN { last="" }
    /^INSERT INTO/ || /^CREATE TABLE/ {
      table=""
      if (match($0, /`[^`]+`(\.`[^`]+`)?/)) {
        table=substr($0, RSTART, RLENGTH)
        gsub(/`/, "", table)
        sub(/^.*\./, "", table)
      }
      if (table != "" && table != last) {
        print "Importing table " table > "/dev/stderr"
        last=table
      }
    }
    { print }
  '
}

echo "${C_BLUE}VR4Mice quick start${C_RESET}"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running or you lack permissions."
  exit 1
fi
if ! command -v make >/dev/null 2>&1; then
  echo "make is not installed."
  exit 1
fi
if command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE_CMD="docker-compose"
else
  DOCKER_COMPOSE_CMD="docker compose"
fi
MODE="$(prompt "Mode (default/client/deployment)" "default")"
MODE="$(echo "${MODE}" | tr '[:upper:]' '[:lower:]')"
case "${MODE}" in
  default|client|deployment) ;;
  *)
    echo "Unknown mode: ${MODE}. Use default/client/deployment."
    exit 1
    ;;
esac
if [ "${MODE}" = "default" ]; then
  REPO_DIR="${DEFAULT_REPO_DIR}"
  echo "${C_YELLOW}Using repo dir: ${REPO_DIR}${C_RESET}"
  if [ ! -d "${REPO_DIR}" ]; then
    echo "${C_YELLOW}Default repo dir not found. Please provide the correct path.${C_RESET}"
    REPO_DIR="$(prompt "Repo dir" "${DEFAULT_REPO_DIR}")"
  fi
else
  REPO_DIR="$(prompt "Repo dir" "${DEFAULT_REPO_DIR}")"
fi
if [ ! -d "${REPO_DIR}" ]; then
  echo "Repo dir not found: ${REPO_DIR}"
  exit 1
fi
COMPOSE_PROJECT_DEFAULT=""
if [ -f "${REPO_DIR}/Makefile" ]; then
  COMPOSE_PROJECT_DEFAULT="$(awk -F'=' '/^COMPOSE_PROJECT/ {gsub(/ /,"",$2); print $2}' "${REPO_DIR}/Makefile" | tail -n1)"
else
  echo "${C_YELLOW}Makefile not found in ${REPO_DIR}. Using default project name.${C_RESET}"
fi
COMPOSE_PROJECT_DEFAULT="${COMPOSE_PROJECT_DEFAULT:-mysqltest}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_DEFAULT}"

if [ "${MODE}" = "deployment" ]; then
  echo "${C_BLUE}Deployment defaults:${C_RESET}"
  echo "  /mnt/database/vr4mice/vr4mice_database/database -> /var/lib/mysql"
  echo "  /mnt/database/shared -> /shared"
  echo "  /mnt/database/vr4mice/vr4mice_database/data -> /data"
  echo "  /mnt/neuropixel_data/vr4mice/raw_screen_recordings -> /vr4mice_screen_recordings"
  echo "  ${REPO_DIR} -> /app"
  echo "  ${REPO_DIR}/base/base_min_schemas -> /base_schemas"
  echo "  ${REPO_DIR}/base/base_actions -> /base_actions"
  DB_ROOT="$(prompt_dir "MySQL database root (maps to /var/lib/mysql)" "/mnt/database/vr4mice/vr4mice_database/database")"
  DATA_ROOT="$(prompt_dir "Data root (maps to /data)" "/mnt/database/vr4mice/vr4mice_database/data")"
  SHARED_ROOT="$(prompt_dir "Shared root (maps to /shared)" "/mnt/database/shared")"
  SCREEN_ROOT="$(prompt_dir "Screen recordings root" "/mnt/neuropixel_data/vr4mice/raw_screen_recordings")"
  DUMP_DIR="$(prompt_dir "Dump dir (optional)" "${DEFAULT_DUMP_DIR}")"
  MOUNT_DIR="${DB_ROOT%/database}"
  DB_BIND_IP="$(prompt "DB bind IP" "0.0.0.0")"
  DB_PORT="$(prompt "DB port" "3309")"
  MYSQL_ROOT_PASSWORD="$(prompt "MySQL root password" "simple")"
  GUI_FLAG="$(prompt_yes_no "GUI mode" "yes")"
  EMAIL_FLAG="$(prompt_yes_no "EMAIL mode" "no")"
  DJ_HOST="127.0.0.1"
  DJ_USER="root"
  DJ_PWD="${MYSQL_ROOT_PASSWORD}"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -q ":${DB_PORT}$"; then
      echo "${C_YELLOW}Port ${DB_PORT} is already in use.${C_RESET}"
      DB_PORT="$(prompt "Choose a different DB port" "3310")"
      if ss -ltn | awk '{print $4}' | grep -q ":${DB_PORT}$"; then
        echo "${C_YELLOW}Port ${DB_PORT} is also in use. Please rerun and choose a free port.${C_RESET}"
        exit 1
      fi
    fi
  fi
  if [ -d "${DB_ROOT}" ] && [ "$(ls -A "${DB_ROOT}" 2>/dev/null)" ]; then
    echo "Warning: ${DB_ROOT} is not empty. Ensure this is the intended MySQL data directory."
  fi
elif [ "${MODE}" = "client" ]; then
  DB_ROOT="${REPO_DIR}/local_data/database"
  DATA_ROOT="${REPO_DIR}/local_data/data"
  SHARED_ROOT="${REPO_DIR}/shared"
  SCREEN_ROOT="${REPO_DIR}/screen_recordings"
  DUMP_DIR="${REPO_DIR}/local_dumps"
  MOUNT_DIR="${REPO_DIR}/local_data"
  DB_BIND_IP="127.0.0.1"
  DB_PORT="3309"
  MYSQL_ROOT_PASSWORD="simple"
  GUI_FLAG="no"
  EMAIL_FLAG="no"
  echo "${C_YELLOW}Client mode: please enter database credentials.${C_RESET}"
  DJ_HOST="$(prompt "DJ host (ip:port or hostname)" "127.0.0.1")"
  if [[ "${DJ_HOST}" != *":"* && "${DJ_HOST}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    DJ_HOST="${DJ_HOST}:${DB_PORT}"
  fi
  DJ_USER="$(prompt "DJ user" "root")"
  DJ_PWD="$(prompt "DJ password" "simple")"
else
  DB_ROOT="${REPO_DIR}/local_data/database"
  DATA_ROOT="${REPO_DIR}/local_data/data"
  SHARED_ROOT="${REPO_DIR}/shared"
  SCREEN_ROOT="${REPO_DIR}/screen_recordings"
  DUMP_DIR="${REPO_DIR}/local_dumps"
  MOUNT_DIR="${REPO_DIR}/local_data"
  DB_BIND_IP="127.0.0.1"
  DB_PORT="3309"
  MYSQL_ROOT_PASSWORD="simple"
  GUI_FLAG="yes"
  EMAIL_FLAG="no"
  DJ_HOST="127.0.0.1"
  DJ_USER="root"
  DJ_PWD="${MYSQL_ROOT_PASSWORD}"
fi

if [ -f "${REPO_DIR}/.env" ]; then
  CURRENT_CLIENT_NAME="$({ grep -E '^CLIENT_CONTAINER_NAME=' "${REPO_DIR}/.env" || true; } | tail -n1 | cut -d= -f2-)"
  CURRENT_DB_NAME="$({ grep -E '^DB_CONTAINER_NAME=' "${REPO_DIR}/.env" || true; } | tail -n1 | cut -d= -f2-)"
else
  CURRENT_CLIENT_NAME="vr4mice_${USER}"
  CURRENT_DB_NAME="vr4mice_db"
fi

PROJECT_RUNNING="$(${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" ps -q 2>/dev/null | wc -l | tr -d ' ')"
CLIENT_EXISTS="$(docker ps -a --format '{{.Names}}' | grep -x "${CURRENT_CLIENT_NAME}" >/dev/null 2>&1 && echo yes || echo no)"
DB_EXISTS="$(docker ps -a --format '{{.Names}}' | grep -x "${CURRENT_DB_NAME}" >/dev/null 2>&1 && echo yes || echo no)"

if [ "${PROJECT_RUNNING}" != "0" ] || [ "${CLIENT_EXISTS}" = "yes" ] || [ "${DB_EXISTS}" = "yes" ]; then
  ACTION="$(prompt "Containers already exist. Action (reuse/recreate/new)" "reuse")"
  ACTION="$(echo "${ACTION}" | tr '[:upper:]' '[:lower:]')"
  case "${ACTION}" in
    reuse) ;;
    recreate)
      ${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" down || true
      ;;
    new)
      COMPOSE_PROJECT="$(prompt "New project name" "${COMPOSE_PROJECT}_2")"
      CURRENT_CLIENT_NAME="vr4mice_${USER}_${COMPOSE_PROJECT}"
      CURRENT_DB_NAME="vr4mice_db_${COMPOSE_PROJECT}"
      ;;
    *)
      echo "Unknown action. Use reuse/recreate/new."
      exit 1
      ;;
  esac
fi

if [ "${MODE}" = "deployment" ]; then
  if [ ! -d "${DUMP_DIR}" ]; then
    echo "${C_YELLOW}Dump dir does not exist: ${DUMP_DIR}${C_RESET}"
    echo "${C_YELLOW}If you plan to import dumps, create it and place restricted_dump_*.sql files there.${C_RESET}"
  fi
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "Repo dir not found: ${REPO_DIR}"
  exit 1
fi

ENV_FILE="${REPO_DIR}/.env"
ENV_PY="${REPO_DIR}/env.py"
MAKEFILE="${REPO_DIR}/Makefile"

if [ -f "${ENV_FILE}" ]; then
  cp "${ENV_FILE}" "${ENV_FILE}.bak"
  echo "${C_YELLOW}Backed up .env to .env.bak${C_RESET}"
fi

mkdir -p "${DB_ROOT}" "${DATA_ROOT}" "${SHARED_ROOT}" "${SCREEN_ROOT}" || true
if [ ! -w "${DB_ROOT}" ]; then
  echo "${C_YELLOW}Warning: ${DB_ROOT} is not writable by the current user.${C_RESET}"
  echo "${C_YELLOW}You may see permission warnings. Consider: sudo chown -R $(id -u):$(id -g) ${DB_ROOT}${C_RESET}"
fi

cat > "${ENV_FILE}" <<EOF
DJ_HOST=${DJ_HOST}:${DB_PORT}
DJ_USER=${DJ_USER}
DJ_PWD=${DJ_PWD}
DJ_LAB=mathis-lab
GUI=$( [ "${GUI_FLAG}" = "yes" ] && echo "True" || echo "False" )
EMAIL=$( [ "${EMAIL_FLAG}" = "yes" ] && echo "True" || echo "False" )
DJ_SUPPORT_FILEPATH_MANAGEMENT=TRUE
DJ_SUPPORT_ADAPTED_TYPES=TRUE

# Docker-compose overrides (optional)
DB_BIND_IP=${DB_BIND_IP}
DB_PORT=${DB_PORT}
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
DB_DATA_PATH=${DB_ROOT}/
SHARED_PATH=${SHARED_ROOT}
DATA_PATH=${DATA_ROOT}
SCREEN_RECORDINGS_PATH=${SCREEN_ROOT}
JUPYTER_PORT=8887
CLIENT_IMAGE=mmathislab/vr4mice_app:0.1.0
CLIENT_CONTAINER_NAME=vr4mice_\${USER}
DB_CONTAINER_NAME=${CURRENT_DB_NAME}
CLIENT_CONTAINER_NAME=${CURRENT_CLIENT_NAME}
EOF

cat > "${ENV_PY}" <<EOF
import os

os.environ["DJ_HOST"] = "${DJ_HOST}:${DB_PORT}"
os.environ["DJ_USER"] = "${DJ_USER}"
os.environ["DJ_PWD"] = "${DJ_PWD}"
os.environ["DJ_LAB"] = "mathis-lab"
os.environ["GUI"] = "${GUI_FLAG}"
os.environ["EMAIL"] = "${EMAIL_FLAG}"
os.environ["VR4MICE_EMAIL_RECIPIENTS"] = "mathislab"
os.environ["IMG_SRC"] = "Imagingsource"
os.environ["DJ_SUPPORT_FILEPATH_MANAGEMENT"] = "TRUE"
os.environ["DJ_SUPPORT_ADAPTED_TYPES"] = "TRUE"
EOF

if [ -f "${MAKEFILE}" ]; then
  sed -i.bak -E "s|^mount :=.*|mount :=${MOUNT_DIR}|" "${MAKEFILE}"
  sed -i.bak -E "s|^DUMP_DIR :=.*|DUMP_DIR := ${DUMP_DIR}|" "${MAKEFILE}" || true
  echo "${C_YELLOW}Updated Makefile mount/DUMP_DIR (backup: Makefile.bak)${C_RESET}"
fi

echo "${C_BLUE}Starting containers...${C_RESET}"
cd "${REPO_DIR}"
if [ ! -f "${REPO_DIR}/Dockerfile" ] || [ ! -f "${REPO_DIR}/docker-compose.yml" ] || [ ! -f "${REPO_DIR}/docker/entrypoint.sh" ] || [ ! -f "${REPO_DIR}/Makefile" ]; then
  echo "${C_YELLOW}Repo dir looks incomplete: ${REPO_DIR}${C_RESET}"
  echo "${C_YELLOW}Expected Dockerfile, docker-compose.yml, docker/entrypoint.sh, and Makefile.${C_RESET}"
  echo "${C_YELLOW}Please rerun and set Repo dir to the FreelyMovingVR4Mice/dj_pipeline folder.${C_RESET}"
  exit 1
fi
USE_NO_CACHE="$(prompt_yes_no "Build with --no-cache?" "no")"
if [ "${MODE}" = "client" ]; then
  echo "${C_YELLOW}Building client image (this may take some time)...${C_RESET}"
  if [ "${USE_NO_CACHE}" = "yes" ]; then
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make client_build BUILD_ARGS="--no-cache"
  else
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make client_build
  fi
  COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make client_up
else
  echo "${C_YELLOW}Building images (this may take some time)...${C_RESET}"
  if [ "${USE_NO_CACHE}" = "yes" ]; then
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make build_all BUILD_ARGS="--no-cache"
  else
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make build_all
  fi
  COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make up_all
fi

INSTALL_BASE="$(prompt_yes_no "Install base schemas/actions now?" "yes")"
if [ "${INSTALL_BASE}" = "yes" ]; then
  COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make base_install
fi

IMPORT_DUMPS="$(prompt_yes_no "Import DB dumps now?" "no")"
if [ "${IMPORT_DUMPS}" = "yes" ]; then
  DUMP_PATH="$(prompt "Dump directory or .zip/.tar.gz archive" "${DUMP_DIR}")"
  WORK_DIR="${DUMP_PATH}"
  if [ -f "${DUMP_PATH}" ]; then
    TMP_BASE="${DUMP_DIR}/tmp_extract"
    mkdir -p "${TMP_BASE}"
    case "${DUMP_PATH}" in
      *.zip)
        if ! command -v unzip >/dev/null 2>&1; then
          echo "unzip is not installed. Please install it or provide a directory."
          exit 1
        fi
        WORK_DIR="$(mktemp -d -p "${TMP_BASE}")"
        echo "Extracting ${DUMP_PATH} to ${WORK_DIR}"
        unzip -q "${DUMP_PATH}" -d "${WORK_DIR}"
        ;;
      *.tar.gz|*.tgz)
        WORK_DIR="$(mktemp -d -p "${TMP_BASE}")"
        echo "Extracting ${DUMP_PATH} to ${WORK_DIR}"
        tar -xzf "${DUMP_PATH}" -C "${WORK_DIR}"
        ;;
      *)
        echo "Unsupported archive type. Provide a directory, .zip, or .tar.gz."
        exit 1
        ;;
    esac
  fi
  if [ -d "${WORK_DIR}" ]; then
    echo "${C_YELLOW}Importing dumps from ${WORK_DIR}. This can take time.${C_RESET}"
    shopt -s nullglob globstar
    dump_files=( "${WORK_DIR}"/**/restricted_dump_*.sql )
    if [ "${#dump_files[@]}" -eq 0 ]; then
      echo "${C_YELLOW}No restricted_dump_*.sql files found in ${WORK_DIR}.${C_RESET}"
      echo "${C_YELLOW}If using an archive, ensure the dumps are inside it (they can be nested).${C_RESET}"
    else
      for f in "${dump_files[@]}"; do
        [ -f "${f}" ] || continue
        db="$(basename "${f}" | sed -E 's/^restricted_dump_(.*)_[0-9]{8}_[0-9]{6}\.sql$/\1/')"
        echo "${C_BLUE}Importing ${f} -> ${db}${C_RESET}"
        ${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" exec -T db \
          env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -u root -e "CREATE DATABASE IF NOT EXISTS \`${db}\`;"
      if command -v pv >/dev/null 2>&1; then
        pv "${f}" | table_progress_filter | ${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" exec -T db \
          env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -u root "${db}"
      elif dd --help 2>&1 | grep -q "status=progress"; then
        dd if="${f}" bs=4M status=progress | table_progress_filter | ${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" exec -T db \
          env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -u root "${db}"
      else
        table_progress_filter < "${f}" | ${DOCKER_COMPOSE_CMD} -p "${COMPOSE_PROJECT}" exec -T db \
          env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -u root "${db}" &
        spinner_wait "$!" "Importing ${db}"
      fi
      done
    fi
  else
    echo "${C_YELLOW}Dump directory not found: ${DUMP_PATH}${C_RESET}"
  fi
fi

OPEN_NOTEBOOK="$(prompt_yes_no "Open Jupyter notebook now?" "no")"
if [ "${OPEN_NOTEBOOK}" = "yes" ]; then
  echo "${C_BLUE}In Jupyter/IPython, connect with:${C_RESET}"
  echo "%run env.py"
  echo "%run run.py connect"
  echo "${C_BLUE}Example schema imports:${C_RESET}"
  echo "from base_schemas.schemas import exp, mice"
  echo "from vr4mice.schema import vr4mice"
  echo "vr4mice.Dataset().fetch()"
  echo "${C_BLUE}If running remotely, open an SSH tunnel:${C_RESET}"
  echo "ssh -NL 8887:localhost:8887 <user>@<server>"
  echo "${C_YELLOW}Append '&' to run in background.${C_RESET}"
  echo "${C_YELLOW}To exit the notebook server, press Ctrl+C in the terminal or type 'exit' in the notebook.${C_RESET}"
  COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make notebook
else
  OPEN_IPYTHON="$(prompt_yes_no "Open IPython now?" "no")"
  if [ "${OPEN_IPYTHON}" = "yes" ]; then
    echo "${C_BLUE}In IPython, connect with:${C_RESET}"
    echo "%run env.py"
    echo "%run run.py connect"
    echo "${C_BLUE}Example schema imports:${C_RESET}"
    echo "from base_schemas.schemas import exp, mice"
    echo "from vr4mice.schema import vr4mice"
    echo "vr4mice.Dataset().fetch()"
    COMPOSE_PROJECT="${COMPOSE_PROJECT}" PUID="${PUID}" PGID="${PGID}" USER_NAME="${USER_NAME}" TAG="${TAG}" make ipython
  fi
fi

echo "${C_GREEN}Done.${C_RESET}"
