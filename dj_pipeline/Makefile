git_repo :=FreelyMovingVR4Mice/dj_pipeline
mount ?= $(CURDIR)
base_schemas_path="$(mount)/$(git_repo)/base_schemas"
base_actions_path="$(mount)/$(git_repo)/base_actions"

COMPOSE_PROJECT ?= mysqltest
DOCKER_COMPOSE ?= docker compose

UID ?= $(shell id -u)
GID ?= $(shell id -g)
USER_NAME ?= $(shell id -un)
TAG ?=
export UID GID USER_NAME TAG

cron_script_path := $(mount)/$(git_repo)/cron_script.sh
cron_script_aws_path := $(mount)/$(git_repo)/cron_script_aws.sh

BUILD_ARGS := \
	--build-arg mysql_config=.my.cnf_vr4mice \
	--no-cache
	#--build-arg base_schemas_path="." \
	#--build-arg base_actions_path="." #\


.PHONY: build_all git_info up_all base_install down_all client_build client_up \
	client_stop client_rm client_down ipython bash mysql aws notebook sync_build \
	sync_up add-cron import-dumps export-dumps

build_all:
	@$(DOCKER_COMPOSE) build

up_all: 
	#git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) up -d
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "export HOME=/app; export PYTHONUSERBASE=/app/.local; export PIP_CACHE_DIR=/app/.cache/pip; mkdir -p /app/.local /app/.cache/pip; if [ -f /opt/conda/etc/profile.d/conda.sh ]; then source /opt/conda/etc/profile.d/conda.sh && conda activate base; fi; python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/"

git_info:
	@git log -n 1 | grep commit > git_commit && git status --porcelain  >> git_commit


base_install:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "export HOME=/app; export PYTHONUSERBASE=/app/.local; export PIP_CACHE_DIR=/app/.cache/pip; mkdir -p /app/.local /app/.cache/pip; if [ -f /opt/conda/etc/profile.d/conda.sh ]; then source /opt/conda/etc/profile.d/conda.sh && conda activate base; fi; python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/"

down_all:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) down

client_build:
	$(DOCKER_COMPOSE) build client #&& \

client_up: git_info
	@UID=$(UID) GID=$(GID) USER_NAME=$(USER_NAME) $(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) up -d client
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "export HOME=/app; export PYTHONUSERBASE=/app/.local; export PIP_CACHE_DIR=/app/.cache/pip; mkdir -p /app/.local /app/.cache/pip; if [ -f /opt/conda/etc/profile.d/conda.sh ]; then source /opt/conda/etc/profile.d/conda.sh && conda activate base; fi; python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/"

client_stop:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) stop client

client_rm:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) rm client

client_down: client_stop
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) rm client

ipython: git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "if [ -f /opt/conda/etc/profile.d/conda.sh ]; then source /opt/conda/etc/profile.d/conda.sh && conda activate base; fi; ipython"

bash: git_info
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash

mysql: git_info
	@mysql --defaults-group-suffix=-vr4mice -A

aws:
	@mysql --defaults-group-suffix=-aws_vr4mice -A

notebook:
	@$(DOCKER_COMPOSE) -p $(COMPOSE_PROJECT) exec --user "$(UID):$(GID)" client bash -c "if [ -f /opt/conda/etc/profile.d/conda.sh ]; then source /opt/conda/etc/profile.d/conda.sh && conda activate base; fi; jupyter notebook --ip 0.0.0.0 --port=8887"

sync_build:
	cp ~/.my.cnf_vr4mice ./.my.cnf_vr4mice
	$(DOCKER_COMPOSE) build aws_sync

sync_up:
	$(DOCKER_COMPOSE) up -d aws_sync

add-cron:
	echo "0 2 * * * bash $(cron_script_path) && bash $(cron_script_aws_path) >> ~/vr4mice_logs/cron.log 2>&1" | crontab -

DUMP_DIR ?= $(CURDIR)/local_dumps

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
