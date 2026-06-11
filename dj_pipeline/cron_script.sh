#!/usr/bin/env bash
set -euo pipefail

# Nightly local pipeline (rig data -> /data/data, video tables, shared export).
# DB credentials are sourced from .env inside the client container (see cron_common.sh).

source "$(dirname "$0")/docker/cron_common.sh"
vr4mice_cron_init

vr4mice_git_info
vr4mice_compose_up db client

vr4mice_run_cron_scenario local
