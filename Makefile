COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif docker-compose version >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)
SERVICE ?=

.PHONY: up build down restart logs clean clean-all db-migrate db-reset

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
	$(COMPOSE) up -d postgres backend
	$(COMPOSE) exec backend alembic upgrade head

db-reset:
	$(COMPOSE) up -d postgres backend
	$(COMPOSE) exec backend alembic downgrade base
	$(COMPOSE) exec backend alembic upgrade head
