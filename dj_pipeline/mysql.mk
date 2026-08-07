# MySQL diagnostics for VR4Mice (committed; separate from the local Makefile).
#
# Usage (from dj_pipeline/):
#   make -f mysql.mk help
#   make -f mysql.mk replication-status
#   make -f mysql.mk mysql
#
# Defaults match docker-compose (.env.compose). Override on the command line, e.g.:
#   make -f mysql.mk MYSQL_HOST=db.example.com MYSQL_PORT=3306 replication-status
#
# Host access without Docker: configure ~/.my.cnf or export MYSQL_PWD, then:
#   make -f mysql.mk USE_DOCKER=0 mysql

SHELL := /bin/bash
.DEFAULT_GOAL := help

-include .env.compose

COMPOSE_PROJECT     ?= vr4mice
DB_CONTAINER_NAME   ?= vr4mice_db
DB_BIND_IP          ?= 127.0.0.1
DB_PORT             ?= 3309
MYSQL_ROOT_PASSWORD ?= simple
MYSQL_USER          ?= root
MYSQL_HOST          ?= $(DB_BIND_IP)
MYSQL_PORT          ?= $(DB_PORT)
USE_DOCKER          ?= 1

# ---------------------------------------------------------------------------
# mysql client wrappers
# ---------------------------------------------------------------------------

ifeq ($(USE_DOCKER),1)
  MYSQL = docker compose -p $(COMPOSE_PROJECT) exec db \
    mysql -uroot -p$(MYSQL_ROOT_PASSWORD)
else
  MYSQL = mysql -h $(MYSQL_HOST) -P $(MYSQL_PORT) -u $(MYSQL_USER)
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
