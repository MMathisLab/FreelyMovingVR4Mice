# MySQL diagnostics for VR4Mice (committed; separate from the local Makefile).
#
# Usage (from dj_pipeline/):
#   make -f mysql.mk help
#   make -f mysql.mk replication-status
#   make -f mysql.mk mysql
#
# Credentials (first defined value wins for each variable):
#   1. Command-line override, e.g. MYSQL_PASSWORD=... MYSQL_USER=...
#   2. .env.compose — MYSQL_ROOT_PASSWORD, DB_PORT, COMPOSE_PROJECT, …
#   3. .env — local DJ_USER / DJ_PWD only (never DJ_MAIN_*)
#   4. Built-in defaults (user root, password simple)
#
# This makefile talks to the LOCAL Docker/pipeline DB only.
# It never uses DJ_MAIN_HOST / DJ_MAIN_USER / DJ_MAIN_PWD (parent sync DB).
#
# Examples:
#   make -f mysql.mk replication-summary
#   make -f mysql.mk USE_DJ_CREDS=1 replication-summary   # local DJ_USER/DJ_PWD from .env
#   make -f mysql.mk MYSQL_PASSWORD=secret replication-summary
#   make -f mysql.mk USE_DOCKER=0 mysql
#
# Note: if .env.compose already sets MYSQL_ROOT_PASSWORD, that wins over DJ_PWD
# unless you pass MYSQL_PASSWORD=... or USE_DJ_CREDS=1.

SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env.compose
-include .env

COMPOSE_PROJECT     ?= vr4mice
DB_CONTAINER_NAME   ?= vr4mice_db
DB_BIND_IP          ?= 127.0.0.1
DB_PORT             ?= 3309
# Prefer compose root password; else local pipeline DJ_PWD (not DJ_MAIN_PWD); else "simple".
MYSQL_ROOT_PASSWORD ?= $(DJ_PWD)
MYSQL_ROOT_PASSWORD ?= simple
MYSQL_USER          ?= root
MYSQL_PASSWORD      ?= $(MYSQL_ROOT_PASSWORD)
MYSQL_HOST          ?= $(DB_BIND_IP)
MYSQL_PORT          ?= $(DB_PORT)
USE_DOCKER          ?= 1
# Use LOCAL pipeline .env login (DJ_USER / DJ_PWD) — never DJ_MAIN_*.
#   make -f mysql.mk USE_DJ_CREDS=1 replication-summary
ifeq ($(USE_DJ_CREDS),1)
  MYSQL_USER := $(DJ_USER)
  MYSQL_PASSWORD := $(DJ_PWD)
  ifneq ($(USE_DOCKER),1)
    # Local DJ_HOST is host:port — never DJ_MAIN_HOST
    MYSQL_HOST := $(shell printf '%s' '$(DJ_HOST)' | cut -d: -f1)
    MYSQL_PORT := $(shell printf '%s' '$(DJ_HOST)' | cut -d: -f2)
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

.PHONY: help mysql mysql-host mysql-docker \
        replication-status replication-summary replication-variables \
        replica-hosts server-id log-bin read-only \
        session-mice stub-mice mice-without-sessions databases

help: ## List MySQL diagnostic targets
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make -f mysql.mk <target>\n\nTargets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

mysql: ## Open interactive mysql (Docker db service by default)
	$(MYSQL)

mysql-docker: ## Interactive mysql via docker compose exec
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) USE_DOCKER=1 mysql

mysql-host: ## Interactive mysql on MYSQL_HOST:MYSQL_PORT (USE_DOCKER=0)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) USE_DOCKER=0 mysql

# ---------------------------------------------------------------------------
# Replication diagnostics
# ---------------------------------------------------------------------------

replication-status: ## Full SHOW REPLICA STATUS (MySQL 8+; use replication-status-legacy on 5.7)
	$(MYSQL) -e "SHOW REPLICA STATUS\G"

replication-status-legacy: ## Full SHOW SLAVE STATUS (MySQL 5.7)
	$(MYSQL) -e "SHOW SLAVE STATUS\G"

replication-summary: ## Short replica health check only (does NOT stop replication)
	$(MYSQL) -e "SHOW REPLICA STATUS\G" \
		| egrep 'Replica_(IO|SQL)_Running|Seconds_Behind|Last_(IO|SQL)_Error|Source_Host|Source_Port|Replica_SQL_Running_State' \
		|| $(MYSQL) -e "SHOW SLAVE STATUS\G" \
		| egrep 'Slave_(IO|SQL)_Running|Seconds_Behind|Last_(IO|SQL)_Error|Master_Host|Master_Port|Slave_SQL_Running_State'

replication-variables: ## Replication-related global variables
	$(MYSQL) -e "SHOW VARIABLES WHERE Variable_name IN ( \
		'server_id', 'log_bin', 'log_replica_updates', 'read_only', \
		'super_read_only', 'gtid_mode', 'enforce_gtid_consistency', \
		'replica_parallel_workers', 'replica_preserve_commit_order');"

replica-hosts: ## Connected replicas (MySQL 8.0.22+)
	-$(MYSQL) -e "SHOW REPLICA HOSTS;"
	-$(MYSQL) -e "SHOW SLAVE HOSTS;"

server-id: ## server_id (must differ between source and replica)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'server_id';"

log-bin: ## Binary logging (required on replication source)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'log_bin';"

read-only: ## read_only / super_read_only (usually ON on replicas)
	$(MYSQL) -e "SHOW VARIABLES LIKE 'read_only'; SHOW VARIABLES LIKE 'super_read_only';"

# ---------------------------------------------------------------------------
# VR4Mice pipeline / mice registry checks
# ---------------------------------------------------------------------------

databases: ## List non-system databases
	$(MYSQL) -e "SHOW DATABASES;" \
		| grep -Ev '^(Database|information_schema|performance_schema|mysql|sys)$$'

session-mice: ## Distinct mouse_name values with local exp.session rows
	$(MYSQL) -e "SELECT COUNT(DISTINCT mouse_name) AS session_mice FROM exp.session; \
		SELECT DISTINCT mouse_name FROM exp.session ORDER BY mouse_name;"

stub-mice: ## Stub Mouse rows created locally (mouse_id = -1)
	$(MYSQL) -e "SELECT mouse_name, mouse_id, dob, sex, strain FROM mice.mouse WHERE mouse_id = -1 ORDER BY mouse_name;"

mice-without-sessions: ## Mouse rows with no exp.session (candidates for cleanup)
	$(MYSQL) -e "SELECT m.mouse_name, m.mouse_id FROM mice.mouse m \
		LEFT JOIN exp.session s ON m.mouse_name = s.mouse_name \
		WHERE s.mouse_name IS NULL ORDER BY m.mouse_name;"
