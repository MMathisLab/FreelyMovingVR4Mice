# ---- Config ----
PROJECT ?= ar_rl_proj
COMPOSE := docker compose -p $(PROJECT)

BUILD_ARGS := \
	--build-arg uid=$(shell id -u) \
	--build-arg gid=$(shell id -g) \
	--build-arg user_name=$(shell id -un)

N ?= 1          				# number of trainer replicas to run with `make up`
INDEX ?= 1       				# trainer replica index for exec/bash (1..N)
SCRIPT ?= PPO_trainer.py       	# e.g. SCRIPT=PPO_trainer.py

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
	$(COMPOSE) build $(BUILD_ARGS) trainer; \
build_nc:
	$(COMPOSE) build $(BUILD_ARGS) --no-cache trainer; \

# ---- Up / Down ----
start:
	@if [ "$(SERVICE)" = "trainer" ]; then \
		$(COMPOSE) up -d --scale trainer=$(N) trainer; \
	elif [ "$(SERVICE)" = "developer" ]; then \
		$(COMPOSE) up -d developer; \
	else \
		$(COMPOSE) up -d --scale trainer=$(N) trainer developer; \
	fi

scale:
	@if [ -z "$(N)" ]; then echo "Usage: make scale N=<replicas>"; exit 1; fi
	@$(COMPOSE) up -d --scale trainer=$(N) trainer

terminate:
	@$(COMPOSE) down --volumes --remove-orphans

stop:
	@if [ -z "$(SERVICE)" ]; then echo "Usage: make stop SERVICE=trainer|developer"; exit 1; fi
	@$(COMPOSE) stop $(SERVICE)

ps:
	@$(COMPOSE) ps


stats:
	@$(COMPOSE) stats


logs:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) logs -f --tail=200 $(SERVICE); \
	else \
		$(COMPOSE) logs -f --tail=200; \
	fi

# ----  Run / Bash ----

# Execute a test script inside an existing selected service container.
# Note: Only the 'trainer' service supports multiple replicas and '--index'.
run_test:
	@if [ "$(SERVICE)" = "trainer" ]; then \
		$(COMPOSE) exec -T --index $(INDEX) $(SERVICE) sh -lc pwd; \
		$(COMPOSE) exec -T --index $(INDEX) $(SERVICE) sh -lc "python3 rl_task/tests/test.py"; \
	elif [ "$(SERVICE)" = "developer" ]; then \
		$(COMPOSE) exec -T $(SERVICE) sh -lc pwd; \
		$(COMPOSE) exec -T $(SERVICE) sh -lc "python3 rl_task/tests/test.py"; \
	else \
		echo "Unknown service: '$(SERVICE)' (expected 'trainer' or 'developer')"; \
		exit 2; \
	fi; \

# Execute a chosen script inside an existing selected service container.
# Note: Only the 'trainer' service supports multiple replicas and '--index'.
run:
	@if [ "$(SCRIPT)" = "" ]; then \
		echo "Please specify a script, e.g. 'make run SERVICE=developer SCRIPT=PPO_trainer.py'"; \
		exit 1; \
	fi; \

	@if [ "$(SERVICE)" = "trainer" ]; then \
		$(COMPOSE) exec -T --index $(INDEX) $(SERVICE) sh -lc pwd; \
		$(COMPOSE) exec -T --index $(INDEX) $(SERVICE) sh -lc "python3 rl_task/scripts/$(SCRIPT)"; \
	elif [ "$(SERVICE)" = "developer" ]; then \
		$(COMPOSE) exec -T $(SERVICE) sh -lc pwd; \
		$(COMPOSE) exec -T $(SERVICE) sh -lc "python3 rl_task/scripts/$(SCRIPT)"; \
	else \
		echo "Unknown service: '$(service)' (expected 'trainer' or 'developer')"; \
		exit 2; \
	fi; \
	
# Open a shell; for trainer, choose replica with INDEX.
# Note: Only the 'trainer' service supports multiple replicas and '--index'.
bash:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make bash SERVICE=trainer|developer [INDEX=1] (trainer only)"; \
		exit 1; \
	fi
	@if [ "$(SERVICE)" = "trainer" ]; then \
		$(COMPOSE) exec --index $(INDEX) trainer bash || $(COMPOSE) exec --index $(INDEX) trainer sh; \
	elif [ "$(SERVICE)" = "developer" ]; then \
		$(COMPOSE) exec developer bash || $(COMPOSE) exec developer sh; \
	else \
		echo "Unknown service: '$(SERVICE)' (expected 'trainer' or 'developer')"; \
		exit 2; \
	fi

# Open an interactive session; for trainer, choose replica with INDEX.
# Note: Only the 'trainer' service supports multiple replicas and '--index'.
attach:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make attach SERVICE=trainer|developer [INDEX=1] (trainer only)"; \
		exit 1; \
	fi
	@if [ "$(SERVICE)" = "trainer" ]; then \
		$(COMPOSE) attach --index $(INDEX) $(SERVICE); \
	elif [ "$(SERVICE)" = "developer" ]; then \
		$(COMPOSE) attach $(SERVICE); \
	else \
		echo "Unknown service: '$(SERVICE)' (expected 'trainer' or 'developer')"; \
		exit 2; \
	fi
