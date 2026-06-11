git_repo :=FreelyMovingVR4Mice/dj_pipeline
mount ?= $(CURDIR)
base_schemas_path="$(mount)/$(git_repo)/base_schemas"
base_actions_path="$(mount)/$(git_repo)/base_actions"

# Docker Compose settings live in .env.compose (see .env.compose.example).
# Source via compose_env.sh so ${USER} and other shell vars expand like cron does.
COMPOSE_ENV_FILE ?= .env.compose
COMPOSE_PROJECT ?= $(shell bash docker/compose_env.sh get COMPOSE_PROJECT 2>/dev/null)
ifeq ($(strip $(COMPOSE_PROJECT)),)
COMPOSE_PROJECT := vr4mice
endif
DOCKER_COMPOSE ?= bash docker/compose_env.sh compose

UID ?= $(shell id -u)
GID ?= $(shell id -g)
USER_NAME ?= $(shell id -un)
USER ?= $(USER_NAME)
TAG ?=
export UID GID USER USER_NAME TAG COMPOSE_PROJECT

BASE_INSTALL_CMD = mkdir -p /app/.local /app/.cache/pip && python -m pip install --user --force-reinstall --no-deps /base_schemas/ && python -m pip install --user --force-reinstall --no-deps /base_actions/
CLIENT_EXEC = $(DOCKER_COMPOSE) exec --user "$(USER_NAME)" client bash -c

cron_script_path := $(CURDIR)/cron_script.sh
cron_script_aws_path := $(CURDIR)/cron_script_aws.sh
cron_script_reboot_path := $(CURDIR)/cron_script_reboot.sh
VR4MICE_LOG_DIR ?= $(HOME)/vr4mice_logs

BUILD_ARGS := \
	--build-arg mysql_config=.my.cnf_vr4mice \
	--no-cache
	#--build-arg base_schemas_path="." \
	#--build-arg base_actions_path="." #\


.PHONY: build_all git_info git-whoami git-user-env git-user-local up_all base_install down_all client_build client_up \
	client_stop client_rm client_down ipython bash mysql aws notebook sync_build \
	sync_up add-cron cron-local cron-aws cron-now cron-aws-only cron-reboot import-dumps export-dumps \
	check-compose-project

check-compose-project:
	@bash docker/check_compose_conflict.sh "$(COMPOSE_PROJECT)"

# Fail with logs if the client service is not running (common after compose project / name mismatch).
define verify_client_running
	@if [ "$$($(DOCKER_COMPOSE) ps --status running -q client 2>/dev/null | wc -l | tr -d ' ')" = "0" ]; then \
	  echo "Error: client service is not running (compose project '$(COMPOSE_PROJECT)')." >&2; \
	  $(DOCKER_COMPOSE) ps -a >&2 || true; \
	  echo "Recent client logs:" >&2; \
	  $(DOCKER_COMPOSE) logs --tail 40 client >&2 || true; \
	  if $(DOCKER_COMPOSE) logs --tail 5 client 2>&1 | grep -q 'groupadd: command not found'; then \
	    echo "Hint: pull latest repo (entrypoint is mounted from ./docker/entrypoint.sh) and run: make up_all" >&2; \
	  fi; \
	  echo "If containers belong to another compose project (e.g. mysqltest), either:" >&2; \
	  echo "  COMPOSE_PROJECT=mysqltest make up_all" >&2; \
	  echo "or remove the old stack and set a unique COMPOSE_PROJECT in .env.compose." >&2; \
	  exit 1; \
	fi
endef

build_all:
	@$(DOCKER_COMPOSE) build

up_all: check-compose-project
	#git_info
	@$(DOCKER_COMPOSE) up -d
	$(verify_client_running)
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

git_info:
	@git log -n 1 | grep commit > git_commit && git status --porcelain  >> git_commit

# Show git remote + effective identity (local config, global, env). Does not change anything.
git-whoami:
	@echo "remote:"; git remote -v 2>/dev/null | sed 's/^/  /' || true
	@echo "local user.name:  $$(git config --local --get user.name 2>/dev/null || echo '(unset)')"
	@echo "local user.email: $$(git config --local --get user.email 2>/dev/null || echo '(unset)')"
	@echo "global user.name: $$(git config --global --get user.name 2>/dev/null || echo '(unset)')"
	@echo "global user.email: $$(git config --global --get user.email 2>/dev/null || echo '(unset)')"
	@echo "GIT_AUTHOR_NAME:  $${GIT_AUTHOR_NAME:-(unset)}"
	@echo "GIT_AUTHOR_EMAIL: $${GIT_AUTHOR_EMAIL:-(unset)}"
	@echo "SSH GitHub: run  ssh -T git@github.com"

# Print shell exports for this session (safe on shared checkouts). Usage:
#   eval "$$(make git-user-env NAME='Your Name' EMAIL='you@example.com')"
git-user-env:
	@test -n "$(NAME)" -a -n "$(EMAIL)" || (echo "Usage: eval \"\$$(make git-user-env NAME='Your Name' EMAIL='you@example.com')\"" >&2; exit 1)
	@echo "export GIT_AUTHOR_NAME='$(NAME)'"
	@echo "export GIT_AUTHOR_EMAIL='$(EMAIL)'"
	@echo "export GIT_COMMITTER_NAME='$(NAME)'"
	@echo "export GIT_COMMITTER_EMAIL='$(EMAIL)'"

# Set git identity in this repo only (.git/config). Affects all users of a shared checkout.
git-user-local:
	@test -n "$(NAME)" -a -n "$(EMAIL)" || (echo "Usage: make git-user-local NAME='Your Name' EMAIL='you@example.com'" >&2; exit 1)
	@echo "WARNING: git config --local affects everyone using this shared checkout." >&2
	@git config --local user.name "$(NAME)"
	@git config --local user.email "$(EMAIL)"
	@echo "Set local git user to $(NAME) <$(EMAIL)>"

base_install:
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

down_all:
	@out=$$($(DOCKER_COMPOSE) down 2>&1); \
	 printf '%s\n' "$$out"; \
	 if printf '%s\n' "$$out" | grep -q 'No resource found to remove'; then \
	   echo "Hint: no stack for project '$(COMPOSE_PROJECT)'. Legacy name is often 'mysqltest':" >&2; \
	   echo "  COMPOSE_PROJECT=mysqltest make down_all" >&2; \
	 fi

client_build:
	$(DOCKER_COMPOSE) build client #&& \

client_up: git_info check-compose-project
	@UID=$(UID) GID=$(GID) USER_NAME=$(USER_NAME) $(DOCKER_COMPOSE) up -d client
	$(verify_client_running)
	@$(CLIENT_EXEC) "$(BASE_INSTALL_CMD)"

client_stop:
	@$(DOCKER_COMPOSE) stop client

client_rm:
	@$(DOCKER_COMPOSE) rm client

client_down: client_stop
	@$(DOCKER_COMPOSE) rm client

ipython: git_info
	@$(DOCKER_COMPOSE) exec --user "$(USER_NAME)" client bash -c "ipython"

bash: git_info
	@$(DOCKER_COMPOSE) exec --user "$(USER_NAME)" client bash

mysql: git_info
	@mysql --defaults-group-suffix=-vr4mice -A

aws:
	@mysql --defaults-group-suffix=-aws_vr4mice -A

notebook:
	@$(DOCKER_COMPOSE) exec --user "$(USER_NAME)" client bash -c "jupyter notebook --ip 0.0.0.0 --port=8887"

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

DUMP_DIR ?= $(CURDIR)/local_dumps

import-dumps:
	for f in $(DUMP_DIR)/restricted_dump_*.sql; do \
	  db=$$(basename "$$f" | sed -E 's/^restricted_dump_(.*)_[0-9]{8}_[0-9]{6}\.sql$$/\1/'); \
	  echo "Importing $$f -> $$db"; \
	  $(DOCKER_COMPOSE) exec -T db \
	    mysql -u root -psimple -e "CREATE DATABASE IF NOT EXISTS \`$$db\`;"; \
	  $(DOCKER_COMPOSE) exec -T db \
	    mysql -u root -psimple "$$db" < "$$f"; \
	done

export-dumps:
	@$(DOCKER_COMPOSE) exec --user "$(USER_NAME)" client \
	  bash -c "cd /app && bash export_restricted_dump.sh"
