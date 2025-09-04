# ---- Config ----
PROJECT ?= ar_rl_proj
COMPOSE := docker compose -p $(PROJECT)

BUILD_ARGS := \
	--build-arg uid=$(shell id -u) \
	--build-arg gid=$(shell id -g) \
	--build-arg user_name=$(shell id -un)

N ?= 1           # number of trainer replicas to run with `make up`
INDEX ?= 1       # trainer replica index for exec/bash (1..N)
SCRIPT ?=        # e.g. SCRIPT=PPO_trainer.py

# ---- Phony targets ----
.PHONY: help build build_nc up scale down stop ps logs exec run bash

help:
	@echo "Targets:"
	@echo "  build [service=trainer|developer]             Build images (service-specific or all)"
	@echo "  build_nc                                      Build with --no-cache"
	@echo "  start [N=2] [service=trainer|developer]       Up services; scales trainer to N"
	@echo "  scale N=3                                     Scale trainer to N replicas"
	@echo "  terminate                                     Stop & remove all"
	@echo "  stop [service=trainer|developer]              Stop a service"
	@echo "  ps                                            Show containers"
	@echo "  logs [service=trainer|developer]              Tail logs"
	@echo "  exec service=trainer [INDEX=1] SCRIPT=foo.py  Run a script in an existing container"
	@echo "  run service=trainer SCRIPT=foo.py             One-off run (new ephemeral container)"
	@echo "  bash service=trainer [INDEX=1]                Shell into a running container"

# ---- Build ----
build:
	@if [ -n "$(service)" ]; then \
		$(COMPOSE) build $(BUILD_ARGS) $(service); \
	else \
		$(COMPOSE) build $(BUILD_ARGS); \
	fi

build_nc:
	@$(COMPOSE) build $(BUILD_ARGS) --no-cache

# ---- Up / Scale ----
start:
	@if [ "$(service)" = "trainer" ]; then \
		$(COMPOSE) up -d --scale trainer=$(N) trainer; \
	elif [ "$(service)" = "developer" ]; then \
		$(COMPOSE) up -d developer; \
	else \
		$(COMPOSE) up -d --scale trainer=$(N) trainer developer; \
	fi

scale:
	@if [ -z "$(N)" ]; then echo "Usage: make scale N=<replicas>"; exit 1; fi
	@$(COMPOSE) up -d --scale trainer=$(N) trainer

terminate:
	@$(COMPOSE) down

stop:
	@if [ -z "$(service)" ]; then echo "Usage: make stop service=trainer|developer"; exit 1; fi
	@$(COMPOSE) stop $(service)

ps:
	@$(COMPOSE) ps


stats:
	@$(COMPOSE) stats


logs:
	@if [ -n "$(service)" ]; then \
		$(COMPOSE) logs -f --tail=200 $(service); \
	else \
		$(COMPOSE) logs -f --tail=200; \
	fi

# ----  Run / Bash ----
run:
	@if [ "$(script)" = "" ]; then \
		echo "Please specify a script with 'make run service=developer script=scripts/PPO_trainer.py'"; \
		exit 1; \
	fi; \
	if [ "$(service)" != "trainer" ] && [ "$(service)" != "developer" ]; then \
		echo "Invalid service. Use 'trainer' or 'developer'."; \
		exit 1; \
	fi; \
	docker compose exec -d --index $(INDEX) $(service) bash -lc "python3 scripts/$(script)"

train:
	@$(MAKE) run service=$(service) script=$(script)

# Open a shell; for trainer, choose replica with INDEX
bash:
	@if [ -z "$(service)" ]; then echo "Usage: make bash service=trainer|developer [INDEX=1]"; exit 1; fi
	@if [ "$(service)" = "trainer" ]; then \
		$(COMPOSE) exec --index $(INDEX) $(service) bash; \
	else \
		$(COMPOSE) exec $(service) bash; \
	fi

attach:
	@if [ -z "$(service)" ]; then echo "Usage: make attach service=trainer|developer [INDEX=1]"; exit 1; fi
	@if [ "$(service)" = "trainer" ]; then \
		$(COMPOSE) attach --index $(INDEX) $(service); \
	else \
		$(COMPOSE) attach $(service); \
	fi
