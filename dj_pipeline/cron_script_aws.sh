#!/usr/bin/env bash
set -euo pipefail

# AWS pipeline run (decision tables, /data/processed).
# DB credentials are loaded from .env-aws inside the container (see cron_scenario.py).

source "$(dirname "$0")/docker/cron_common.sh"
vr4mice_cron_init

vr4mice_git_info
vr4mice_compose_up db client

vr4mice_run_cron_scenario aws
