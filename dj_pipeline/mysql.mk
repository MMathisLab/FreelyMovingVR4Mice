# MySQL diagnostics for VR4Mice (committed; separate from the local Makefile).
#
# Usage (from dj_pipeline/):
#   make -f mysql.mk help
#   make -f mysql.mk creds
#   make -f mysql.mk replication-summary
#   make -f mysql.mk mysql
#
# Login credentials: ONLY local .env DJ_USER / DJ_PWD (shell-parsed).
# Never DJ_MAIN_*, never .env.compose MYSQL_ROOT_PASSWORD, never CLI overrides.
#
# .env.compose is used only for COMPOSE_PROJECT / ports (Docker targeting).
#
# Examples:
#   make -f mysql.mk replication-summary
#   make -f mysql.mk USE_DOCKER=0 mysql

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Compose settings only (project name, ports) — not MySQL login.
-include .env.compose

# Read one KEY from local .env (never use for DJ_MAIN_*).
# Handles optional quotes and Windows CR; value may contain '='.
env_get = $(shell if [ -f .env ]; then \
	grep -E '^$(1)=' .env | tail -1 | cut -d= -f2- | \
	sed -e 's/\r$$//' -e 's/^"//' -e 's/"$$//' -e "s/^'//" -e "s/'$$//"; \
	fi)

# override: ignore MYSQL_USER=/MYSQL_PASSWORD= on the make command line
override MYSQL_USER     := $(call env_get,DJ_USER)
override MYSQL_PASSWORD := $(call env_get,DJ_PWD)
ENV_DJ_HOST             := $(call env_get,DJ_HOST)

COMPOSE_PROJECT     ?= vr4mice
DB_CONTAINER_NAME   ?= vr4mice_db
DB_BIND_IP          ?= 127.0.0.1
DB_PORT             ?= 3309
MYSQL_HOST          ?= $(DB_BIND_IP)
MYSQL_PORT          ?= $(DB_PORT)
USE_DOCKER          ?= 1

ifneq ($(USE_DOCKER),1)
  ifneq ($(strip $(ENV_DJ_HOST)),)
    # Local DJ_HOST is host:port — never DJ_MAIN_HOST
    MYSQL_HOST := $(shell printf '%s' '$(ENV_DJ_HOST)' | cut -d: -f1)
    MYSQL_PORT := $(shell printf '%s' '$(ENV_DJ_HOST)' | cut -d: -f2)
  endif
endif

# ---------------------------------------------------------------------------
# mysql client wrappers
# ---------------------------------------------------------------------------

ifeq ($(USE_DOCKER),1)
  MYSQL = docker compose -p $(COMPOSE_PROJECT) exec db \
    mysql -u$(MYSQL_USER) -p$(MYSQL_PASSWORD)
else
  MYSQL = mysql -h $(MYSQL_HOST) -P $(MYSQL_PORT) -u $(MYSQL_USER) -p$(MYSQL_PASSWORD)
endif

.PHONY: help check-creds creds mysql mysql-host mysql-docker \
        replication-status replication-status-legacy replication-summary \
        replication-variables replica-hosts server-id log-bin read-only \
        session-mice stub-mice mice-without-sessions databases

help: ## List MySQL diagnostic targets
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make -f mysql.mk <target>\n\nTargets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-creds:
	@if [ ! -f .env ]; then \
		echo "error: .env missing — run from dj_pipeline/ with DJ_USER and DJ_PWD set"; \
		exit 1; \
	fi
	@if [ -z "$(MYSQL_USER)" ] || [ -z "$(MYSQL_PASSWORD)" ]; then \
		echo "error: need DJ_USER and DJ_PWD in .env (local only; never DJ_MAIN_*)"; \
		exit 1; \
	fi

creds: ## Show which .env credentials will be used (password masked)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) check-creds
	@echo "cwd: $$(pwd)"
	@echo "source: .env → DJ_USER / DJ_PWD only"
	@echo "MYSQL_USER: $(MYSQL_USER)"
	@echo "MYSQL_PASSWORD: $$(printf '%s' '$(MYSQL_PASSWORD)' | sed 's/./*/g') (len=$$(printf '%s' '$(MYSQL_PASSWORD)' | wc -c | tr -d ' '))"
	@echo "COMPOSE_PROJECT: $(COMPOSE_PROJECT) (from .env.compose if set)"
	@echo "(Never reads DJ_MAIN_* or MYSQL_ROOT_PASSWORD)"

mysql: check-creds ## Open interactive mysql (Docker db service by default)
	$(MYSQL)

mysql-docker: ## Interactive mysql via docker compose exec
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) USE_DOCKER=1 mysql

mysql-host: ## Interactive mysql on DJ_HOST from .env (USE_DOCKER=0)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) USE_DOCKER=0 mysql

# ---------------------------------------------------------------------------
# Replication diagnostics
# ---------------------------------------------------------------------------

replication-status: check-creds ## Full SHOW REPLICA STATUS (MySQL 8+)
	$(MYSQL) -e "SHOW REPLICA STATUS\G"

replication-status-legacy: check-creds ## Full SHOW SLAVE STATUS (MySQL 5.7)
	$(MYSQL) -e "SHOW SLAVE STATUS\G"

replication-summary: check-creds ## Short replica health check only (does NOT stop replication)
	$(MYSQL) -e "SHOW REPLICA STATUS\G" \
		| egrep 'Replica_(IO|SQL)_Running|Seconds_Behind|Last_(IO|SQL)_Error|Source_Host|Source_Port|Replica_SQL_Running_State' \
		|| $(MYSQL) -e "SHOW SLAVE STATUS\G" \
		| egrep 'Slave_(IO|SQL)_Running|Seconds_Behind|Last_(IO|SQL)_Error|Master_Host|Master_Port|Slave_SQL_Running_State'

replication-variables: check-creds ## Replication-related global variables
	$(MYSQL) -e "SHOW VARIABLES WHERE Variable_name IN ( \
		'server_id', 'log_bin', 'log_replica_updates', 'read_only', \
		'super_read_only', 'gtid_mode', 'enforce_gtid_consistency', \
		'replica_parallel_workers', 'replica_preserve_commit_order');"

replica-hosts: check-creds ## Connected replicas (MySQL 8.0.22+)
	-$(MYSQL) -e "SHOW REPLICA HOSTS;"
	-$(MYSQL) -e "SHOW SLAVE HOSTS;"

server-id: check-creds ## server_id (must differ between source and replica)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'server_id';"

log-bin: check-creds ## Binary logging (required on replication source)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'log_bin';"

read-only: check-creds ## read_only / super_read_only (usually ON on replicas)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'read_only'; SHOW VARIABLES LIKE 'super_read_only';"

# ---------------------------------------------------------------------------
# VR4Mice pipeline / mice registry checks
# ---------------------------------------------------------------------------

databases: check-creds ## List non-system databases
	$(MYSQL) -e "SHOW DATABASES;" \
		| grep -Ev '^(Database|information_schema|performance_schema|mysql|sys)$$'

session-mice: check-creds ## Distinct mouse_name values with local exp.session rows
	$(MYSQL) -e "SELECT COUNT(DISTINCT mouse_name) AS session_mice FROM exp.session; \
		SELECT DISTINCT mouse_name FROM exp.session ORDER BY mouse_name;"

stub-mice: check-creds ## Stub Mouse rows created locally (mouse_id = -1)
	$(MYSQL) -e "SELECT mouse_name, mouse_id, dob, sex, strain FROM mice.mouse WHERE mouse_id = -1 ORDER BY mouse_name;"

mice-without-sessions: check-creds ## Mouse rows with no exp.session (candidates for cleanup)
	$(MYSQL) -e "SELECT m.mouse_name, m.mouse_id FROM mice.mouse m \
		LEFT JOIN exp.session s ON m.mouse_name = s.mouse_name \
		WHERE s.mouse_name IS NULL ORDER BY m.mouse_name;"
