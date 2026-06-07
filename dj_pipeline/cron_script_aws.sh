#!/usr/bin/env bash
set -euo pipefail

# AWS-only pipeline run (decision tables, /data/processed).
# Uses .env-aws when present to override DB credentials for the AWS database.

source "$(dirname "$0")/docker/cron_common.sh"
vr4mice_cron_init

vr4mice_git_info
vr4mice_compose_up db client

vr4mice_run_cron_scenario aws ".env-aws"
