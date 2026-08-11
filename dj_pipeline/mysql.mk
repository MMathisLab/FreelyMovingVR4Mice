# Mice registry sync + minimal local MySQL helpers (from dj_pipeline/).
#
#   make -f mysql.mk sync-mice-from-main
#   make -f mysql.mk sync-mice-from-main MOUSE=Flamingo,Whale
#   make -f mysql.mk merge-water-restriction
#   make -f mysql.mk replication-summary
#   make -f mysql.mk creds
#
# Host mysql client via .env DJ_HOST / DJ_USER / DJ_PWD only.
# Never DJ_MAIN_* for local login (parent creds are read by the sync script).

SHELL := /bin/bash
.DEFAULT_GOAL := help

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

DB_BIND_IP ?= 127.0.0.1
DB_PORT    ?= 3309

ifneq ($(strip $(ENV_DJ_HOST)),)
  MYSQL_HOST := $(shell printf '%s' '$(ENV_DJ_HOST)' | cut -d: -f1)
  MYSQL_PORT := $(shell printf '%s' '$(ENV_DJ_HOST)' | cut -d: -f2)
else
  MYSQL_HOST ?= $(DB_BIND_IP)
  MYSQL_PORT ?= $(DB_PORT)
endif

MYSQL = mysql -h $(MYSQL_HOST) -P $(MYSQL_PORT) -u $(MYSQL_USER) -p$(MYSQL_PASSWORD)

.PHONY: help check-creds check-main-creds creds \
        replication-summary sync-mice-from-main merge-water-restriction

help: ## List targets
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make -f mysql.mk <target>\n\nTargets:\n"} \
		/^[a-zA-Z0-9_-]+:.*##/ {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-creds:
	@if [ ! -f .env ]; then \
		echo "error: .env missing — run from dj_pipeline/ with DJ_HOST, DJ_USER, DJ_PWD set"; \
		exit 1; \
	fi
	@if [ -z "$(MYSQL_USER)" ] || [ -z "$(MYSQL_PASSWORD)" ]; then \
		echo "error: need DJ_USER and DJ_PWD in .env (local only; never DJ_MAIN_*)"; \
		exit 1; \
	fi
	@if [ -z "$(ENV_DJ_HOST)" ]; then \
		echo "error: need DJ_HOST=host:port in .env for host mysql client"; \
		exit 1; \
	fi

creds: ## Show which .env credentials will be used (password masked)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) check-creds
	@echo "cwd: $$(pwd)"
	@echo "source: .env → DJ_HOST / DJ_USER / DJ_PWD only"
	@echo "client: host mysql → $(MYSQL_HOST):$(MYSQL_PORT)"
	@echo "MYSQL_USER: $(MYSQL_USER)"
	@echo "MYSQL_PASSWORD: $$(printf '%s' '$(MYSQL_PASSWORD)' | sed 's/./*/g') (len=$$(printf '%s' '$(MYSQL_PASSWORD)' | wc -c | tr -d ' '))"
	@echo "(Never reads DJ_MAIN_* or MYSQL_ROOT_PASSWORD for local login)"

# ---------------------------------------------------------------------------
# Parent → local mice registry (mysqldump; no DataJoint dual-connect)
# ---------------------------------------------------------------------------

check-main-creds: check-creds
	@if [ -z "$$(grep -E '^DJ_MAIN_HOST=' .env 2>/dev/null | tail -1 | cut -d= -f2-)" ]; then \
		echo "error: need DJ_MAIN_HOST in .env (parent host:port)"; \
		exit 1; \
	fi

# Optional: MOUSE=Flamingo,Whale  (comma-separated). Default = full registry tables.
sync-mice-from-main: check-main-creds ## Dump mice tables from DJ_MAIN_* onto local DJ_HOST
	@MOUSE="$(MOUSE)" bash "$(CURDIR)/scripts/sync_mice_mysql.sh"

# Heal SessionScoreSheet FK when both _ and __ water_restriction tables exist.
merge-water-restriction: check-creds ## INSERT IGNORE _ → __ water_restriction rows
	@$(MYSQL) -e "INSERT IGNORE INTO mice.mouse_score_sheet__water_restriction \
		SELECT * FROM mice.mouse_score_sheet_water_restriction; \
		SELECT \
		  (SELECT COUNT(*) FROM mice.mouse_score_sheet_water_restriction) AS underscore, \
		  (SELECT COUNT(*) FROM mice.mouse_score_sheet__water_restriction) AS dunder;"

# ---------------------------------------------------------------------------
# Minimal replica check (cleanup needs replication off)
# ---------------------------------------------------------------------------

replication-summary: check-creds ## Short replica health check (does NOT stop replication)
	@set -o pipefail; \
	out=$$( ($(MYSQL) -e "SHOW REPLICA STATUS\G" 2>/dev/null \
		|| $(MYSQL) -e "SHOW SLAVE STATUS\G") \
		| egrep 'Replica_(IO|SQL)_Running|Slave_(IO|SQL)_Running|Seconds_Behind|Last_(IO|SQL)_Error|Source_Host|Source_Port|Master_Host|Master_Port|Replica_SQL_Running_State|Slave_SQL_Running_State' \
		|| true); \
	if [ -z "$$out" ]; then \
		echo "No replica/slave status rows (not a replica, or empty SHOW REPLICA/SLAVE STATUS)."; \
		exit 0; \
	fi; \
	printf '%s\n' "$$out"
