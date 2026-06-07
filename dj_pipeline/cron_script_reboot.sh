#!/usr/bin/env bash
set -euo pipefail

# Start db + client after host reboot (wait for Docker daemon).
# Install base packages once the client container is up.

sleep 120

source "$(dirname "$0")/docker/cron_common.sh"
vr4mice_cron_init

vr4mice_git_info
vr4mice_compose_up db client
vr4mice_base_install
