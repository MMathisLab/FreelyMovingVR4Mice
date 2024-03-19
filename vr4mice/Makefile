build:
	@docker-compose build --build-arg user=$(shell id -u) --build-arg usern=$(shell id -un) --no-cache
up:
	@docker-compose up  -d #--abort-on-container-exit --exit-code-from client_app
down:
	@docker-compose down

build_client:
	@docker-compose build --build-arg user=$(shell id -u) --build-arg usern=$(shell id -un) app
up_client:
	@docker-compose up -d app
ipython:
	docker-compose exec app ipython	
