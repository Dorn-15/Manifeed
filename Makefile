COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif docker-compose version >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)
SERVICE ?=
BACKEND_PYTEST_ARGS ?= tests -vv --color=yes --tb=short -ra
WORKER_PYTEST_ARGS ?= tests -vv --color=yes --tb=short -ra
DB_MANAGER_PYTEST_ARGS ?= tests -vv --color=yes --tb=short -ra

.PHONY: up build down restart logs clean clean-all db-migrate db-reset test test-backend test-worker test-db-manager

up:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) up -d $(SERVICE) --build; \
	else \
		$(COMPOSE) up -d --build; \
	fi

build:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) build $(SERVICE); \
	else \
		$(COMPOSE) build; \
	fi

down:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) stop $(SERVICE); \
	else \
		$(COMPOSE) down; \
	fi

restart:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) restart $(SERVICE); \
	else \
		$(COMPOSE) restart; \
	fi

logs:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) logs -f $(SERVICE); \
	else \
		$(COMPOSE) logs -f; \
	fi

clean:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) rm -f -s $(SERVICE); \
	else \
		$(COMPOSE) down --remove-orphans; \
	fi

clean-all:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) rm -f -s -v $(SERVICE); \
	else \
		$(COMPOSE) down -v --remove-orphans --rmi local; \
		docker system prune -af --volumes; \
	fi

db-migrate:
	$(COMPOSE) up -d postgres
	$(COMPOSE) run --rm --no-deps db_manager alembic upgrade head

db-reset:
	$(COMPOSE) up -d postgres
	$(COMPOSE) stop worker_rss_scrapper db_manager
	$(COMPOSE) run --rm --no-deps db_manager alembic downgrade base
	$(COMPOSE) run --rm --no-deps db_manager alembic upgrade head
	$(COMPOSE) up -d db_manager worker_rss_scrapper

test-backend:
	$(COMPOSE) run --rm --build backend sh -lc "PIP_ROOT_USER_ACTION=ignore python -m pip install --disable-pip-version-check --quiet pytest && python -m pytest $(BACKEND_PYTEST_ARGS)"

test-worker:
	$(COMPOSE) run --rm --build worker_rss_scrapper sh -lc "PIP_ROOT_USER_ACTION=ignore python -m pip install --disable-pip-version-check --quiet pytest && python -m pytest $(WORKER_PYTEST_ARGS)"

test-db-manager:
	$(COMPOSE) run --rm --build db_manager sh -lc "PIP_ROOT_USER_ACTION=ignore python -m pip install --disable-pip-version-check --quiet pytest && python -m pytest $(DB_MANAGER_PYTEST_ARGS)"
