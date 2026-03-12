git_repo :=FreelyMovingVR4Mice/dj_pipeline
mount :=/mnt/data_storage/vr4mice_database_dump
base_schemas_path="$(mount)/$(git_repo)/base_schemas"
base_actions_path="$(mount)/$(git_repo)/base_actions"

cron_script_path := $(mount)/$(git_repo)/cron_script.sh
cron_script_aws_path := $(mount)/$(git_repo)/cron_script_aws.sh

BUILD_ARGS := \
	--build-arg uid=$(shell id -u) \
	--build-arg gid=$(shell id -g) \
       	--build-arg user_name=$(shell id -un) \
	--build-arg mysql_config=.my.cnf_vr4mice \
	--no-cache	
	#--build-arg base_schemas_path="." \
	#--build-arg base_actions_path="." #\


build_all:
	@docker-compose build $(BUILD_ARGS)

git_info:
	@git log -n 1 | grep commit > git_commit && git status --porcelain  >> git_commit

up_all: 
	#git_info
	@docker-compose -p mysqltest up -d
	@docker-compose -p mysqltest exec client bash -c "pip install /base_schemas/ ; pip install /base_actions/" 1>/dev/null

base_install:
	@docker-compose -p mysqltest exec client bash -c "pip install --no-deps /base_schemas/ ; pip install --no-deps /base_actions/" 1>/dev/null

down_all:
	@docker-compose -p mysqltest down

client_build:
	docker-compose build $(BUILD_ARGS) client #&& \

client_up: git_info
	@docker-compose -p mysqltest up -d client
	@docker-compose -p mysqltest exec client bash -c "pip install --no-deps /base_schemas/ ; pip install --no-deps /base_actions/" 1>/dev/null

client_stop:
	@docker-compose -p mysqltest stop client

client_rm:
	@docker-compose -p mysqltest rm client

client_down: client_stop
	@docker-compose -p mysqltest rm client

ipython: git_info
	@docker-compose -p mysqltest exec client ipython

bash: git_info
	@docker-compose -p mysqltest exec client bash

mysql: git_info
	@mysql --defaults-group-suffix=-vr4mice -A

aws:
	@mysql --defaults-group-suffix=-aws_vr4mice -A

notebook:
	@docker-compose -p mysqltest exec client bash -c "jupyter notebook --ip 0.0.0.0 "

sync_build:
	cp ~/.my.cnf_vr4mice ./.my.cnf_vr4mice
	docker-compose build $(BUILD_ARGS) aws_sync

sync_up:
	docker-compose up -d aws_sync

add-cron:
	echo "0 2 * * * bash $(cron_script_path) && bash $(cron_script_aws_path) >> ~/vr4mice_logs/cron.log 2>&1" | crontab -

DUMP_DIR := /mnt/data_storage/vr4mice_database_dump/restricted_dump_20260312_090750
#/mnt/data_storage/vr4mice_database_dump/restricted_dump_20260311_141041

import-dumps:
	for f in $(DUMP_DIR)/restricted_dump_*.sql; do \
	  db=$$(basename "$$f" | sed -E 's/^restricted_dump_(.*)_[0-9]{8}_[0-9]{6}\.sql$$/\1/'); \
	  echo "Importing $$f -> $$db"; \
	  docker-compose -p mysqltest exec -T db \
	    mysql -u root -psimple -e "CREATE DATABASE IF NOT EXISTS \`$$db\`;"; \
	  docker-compose -p mysqltest exec -T db \
	    mysql -u root -psimple "$$db" < "$$f"; \
	done
