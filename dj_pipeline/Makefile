git_repo :=FreelyMovingVR4Mice/dj_pipeline
mount ?= $(CURDIR)
base_schemas_path="$(mount)/$(git_repo)/base_schemas"
base_actions_path="$(mount)/$(git_repo)/base_actions"

COMPOSE_PROJECT ?= vr4mice
DOCKER_COMPOSE ?= docker compose

UID ?= $(shell id -u)
GID ?= $(shell id -g)
USER_NAME ?= $(shell id -un)
TAG ?=
export UID GID USER_NAME TAG COMPOSE_PROJECT

BASE_INSTALL_CMD = export HOME=/app; export PYTHONUSERBASE=/app/.local; export PIP_CACHE_DIR=/app/.cache/pip; mkdir -p /app/.local /app/.cache/pip; python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/
CLIENT_EXEC = $(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c

cron_script_path := $(CURDIR)/cron_script.sh
cron_script_aws_path := $(CURDIR)/cron_script_aws.sh
cron_script_reboot_path := $(CURDIR)/cron_script_reboot.sh

BUILD_ARGS := \
	--build-arg mysql_config=.my.cnf_vr4mice \
	--no-cache
	#--build-arg base_schemas_path="." \
	#--build-arg base_actions_path="." #\


.PHONY: build_all git_info up_all base_install down_all client_build client_up \
	client_stop client_rm client_down ipython bash mysql aws notebook sync_build \
	sync_up add-cron cron-local cron-aws cron-reboot import-dumps export-dumps

build_all:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) build

up_all: 
	#git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) up -d
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

git_info:
	@git log -n 1 | grep commit > git_commit && git status --porcelain  >> git_commit


base_install:
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

down_all:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) down

client_build:
	$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) build client #&& \

client_up: git_info
	@UID=$(UID) GID=$(GID) USER_NAME=$(USER_NAME) $(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) up -d client
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

client_stop:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) stop client

client_rm:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) rm client

client_down: client_stop
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) rm client

ipython: git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "ipython"

bash: git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash

mysql: git_info
	@mysql --defaults-group-suffix=-vr4mice -A

aws:
	@mysql --defaults-group-suffix=-aws_vr4mice -A

notebook:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "jupyter notebook --ip 0.0.0.0 --port=8887"

sync_build:
	cp ~/.my.cnf_vr4mice ./.my.cnf_vr4mice
	$(DOCKER_COMPOSE) build aws_sync

sync_up:
	$(DOCKER_COMPOSE) up -d aws_sync

add-cron:
	@mkdir -p ~/vr4mice_logs
	@(crontab -l 2>/dev/null | grep -vE 'cron_script(_aws|_reboot)?\.sh' || true; \
	  echo "@reboot bash $(cron_script_reboot_path) >> ~/vr4mice_logs/cron_reboot.log 2>&1"; \
	  echo "0 2 * * * bash $(cron_script_path) >> ~/vr4mice_logs/cron.log 2>&1 && bash $(cron_script_aws_path) >> ~/vr4mice_logs/cron_aws.log 2>&1") | crontab -
	@echo "Installed crontab:"
	@crontab -l

cron-local:
	@bash $(cron_script_path)

cron-aws:
	@bash $(cron_script_aws_path)

cron-reboot:
	@bash $(cron_script_reboot_path)

DUMP_DIR := /home/mariiapopova/FreelyMovingVR4Mice/dj_pipeline/local_dumps
#/mnt/data_storage/vr4mice_database_dump/restricted_dump_20260311_141041

import-dumps:
	for f in $(DUMP_DIR)/restricted_dump_*.sql; do \
	  db=$$(basename "$$f" | sed -E 's/^restricted_dump_(.*)_[0-9]{8}_[0-9]{6}\.sql$$/\1/'); \
	  echo "Importing $$f -> $$db"; \
	  $(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec -T db \
	    mysql -u root -psimple -e "CREATE DATABASE IF NOT EXISTS \`$$db\`;"; \
	  $(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec -T db \
	    mysql -u root -psimple "$$db" < "$$f"; \
	done

export-dumps:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client \
	  bash -c "cd /app && bash export_restricted_dump.sh"
