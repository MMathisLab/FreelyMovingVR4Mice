git_repo :=FreelyMovingVR4Mice/dj_pipeline
mount :=/mnt/database
base_schemas_path="$(mount)/$(git_repo)/base_schemas"
base_actions_path="$(mount)/$(git_repo)/base_actions"
#todo: add commit in docker build

BUILD_ARGS := \
	--build-arg uid=$(shell id -u) \
	--build-arg gid=$(shell id -g) \
       	--build-arg user_name=$(shell id -un) #\
	#--build-arg base_schemas_path="." \
	#--build-arg base_actions_path="." #\
	#--no-cache

git_info:
	@git log -n 1 | grep commit > git_commit && git status --porcelain  >> git_commit

build_all:
	#@cp -r $(base_schemas_path) . && \
	#cp -r $(base_actions_path) . && \

	@docker-compose build $(BUILD_ARGS)
	@docker-compose up -d

	#@cd $(mount)/DataJoint_mathis/replication && ./set_up.sh
	
	#rm -r base_schemas && \
	#rm -r base_actions

up_all: git_info
	@docker-compose up -d
	@docker-compose exec client bash -c "pip install /base_schemas/ ; pip install /base_actions/" 1>/dev/null

base_install:
	@docker-compose exec client bash -c "pip install /base_schemas/ ; pip install /base_actions/" 1>/dev/null

#@cd $(mount)/DataJoint_mathis/replication && ./restart.sh

down_all:
	@docker-compose down

replica_set_up:
	@cd $(mount)/replication && ./set_up.sh

replica_restart:
	@cd $(mount)/replication && ./restart.sh

client_build:
	#@cp -r $(base_schemas_path) . && \
	#cp -r $(base_actions_path) . && \
	
	docker-compose build $(BUILD_ARGS) client #&& \
	#rm -r base_schemas && \
	#rm -r base_actions

client_up: git_info
	@docker-compose up -d client
	@docker-compose exec client bash -c "pip install /base_schemas/ ; pip install /base_actions/" 1>/dev/null

client_up_scale: client_build
	@docker-compose up -d --scale client=2

client_stop:
	@docker-compose stop client

client_rm:
	@docker-compose rm client

client_down: client_stop
	@docker-compose rm client

ipython: git_info
	@docker-compose exec client ipython

bash: git_info
	@docker-compose exec client bash

mysql:
	@mysql --defaults-group-suffix=-vr4mice -A




