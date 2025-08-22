# ---- Config ----
PROJECT ?= user_leo_ar_proj               # compose project name (used in auto container names)
COMPOSE := docker compose -p $(PROJECT)

BUILD_ARGS := \
	--build-arg uid=$(shell id -u) \
	--build-arg gid=$(shell id -g) \
	--build-arg user_name=$(shell id -un)

# Defaults you can override: e.g. `make up N=3`
N ?= 1           # number of trainer replicas to run with `make up`
INDEX ?= 1       # trainer replica index for exec/bash (1..N)
SCRIPT ?=        # e.g. SCRIPT=PPO_trainer.py

# ---- Phony targets ----
.PHONY: help build build_nc up scale down stop ps logs exec run bash

help:
	@echo "Targets:"
	@echo "  build [service=trainer|developer]      Build images (service-specific or all)"
	@echo "  build_nc                               Build with --no-cache"
	@echo "  up [N=2] [service=trainer|developer]   Up services; scales trainer to N"
	@echo "  scale N=3                              Scale trainer to N replicas"
	@echo "  down                                   Stop & remove all"
	@echo "  stop [service=trainer|developer]       Stop a service"
	@echo "  ps                                     Show containers"
	@echo "  logs [service=trainer|developer]       Tail logs"
	@echo "  exec service=trainer [INDEX=1] SCRIPT=foo.py  Run a script in an existing container"
	@echo "  run service=trainer SCRIPT=foo.py      One-off run (new ephemeral container)"
	@echo "  bash service=trainer [INDEX=1]         Shell into a running container"

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
up:
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

down:
	@$(COMPOSE) down

stop:
	@if [ -z "$(service)" ]; then echo "Usage: make stop service=trainer|developer"; exit 1; fi
	@$(COMPOSE) stop $(service)

ps:
	@$(COMPOSE) ps

logs:
	@if [ -n "$(service)" ]; then \
		$(COMPOSE) logs -f --tail=200 $(service); \
	else \
		$(COMPOSE) logs -f --tail=200; \
	fi

# ---- Exec / Run / Bash ----
# Use `exec` to run inside an existing container (good for scaled trainers).
exec:
	@if [ -z "$(service)" ]; then echo "Usage: make exec service=trainer|developer [INDEX=1] SCRIPT=foo.py"; exit 1; fi
	@if [ -z "$(SCRIPT)" ]; then echo "Please set SCRIPT=... (relative to /app/scripts)"; exit 1; fi
	@if [ "$(service)" = "trainer" ]; then \
		$(COMPOSE) exec --index $(INDEX) $(service) bash -lc 'xvfb-run -a python3 scripts/$(SCRIPT)'; \
	else \
		$(COMPOSE) exec $(service) bash -lc 'xvfb-run -a python3 scripts/$(SCRIPT)'; \
	fi

# Use `run` for a fresh, ephemeral container (not tied to an existing replica).
run:
	@if [ -z "$(service)" ]; then echo "Usage: make run service=trainer|developer SCRIPT=foo.py"; exit 1; fi
	@if [ -z "$(SCRIPT)" ]; then echo "Please set SCRIPT=... (relative to /app/scripts)"; exit 1; fi
	@$(COMPOSE) run --rm $(service) bash -lc 'xvfb-run -a python3 scripts/$(SCRIPT)'

# Open a shell; for trainer, choose replica with INDEX
bash:
	@if [ -z "$(service)" ]; then echo "Usage: make bash service=trainer|developer [INDEX=1]"; exit 1; fi
	@if [ "$(service)" = "trainer" ]; then \
		$(COMPOSE) exec --index $(INDEX) $(service) bash; \
	else \
		$(COMPOSE) exec $(service) bash; \
	fi
