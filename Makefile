COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif docker-compose version >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)
CARGO ?= $(shell if command -v cargo >/dev/null 2>&1; then command -v cargo; elif [ -x "$(HOME)/.cargo/bin/cargo" ]; then printf '%s' "$(HOME)/.cargo/bin/cargo"; else printf '%s' cargo; fi)
SERVICE ?=
BACKEND_PYTEST_ARGS ?= tests -vv --color=yes --tb=short -ra
WORKER_CARGO_TEST_ARGS ?=
EMBEDDING_WORKER_CARGO_TEST_ARGS ?=
RUST_LINUX_X86_TARGET := x86_64-unknown-linux-gnu

.PHONY: up build down restart logs clean clean-all db-migrate db-reset test test-backend test-worker test-worker-embedding download-embedding-model check-cargo build-worker-rss-native run-worker-rss-native build-worker-embedding-linux-x86 run-worker-embedding-linux-x86

up:
	@if [ -n "$(SERVICE)" ]; then \
		$(COMPOSE) up -d $(SERVICE) --build; \
	else \
		$(COMPOSE) up -d --build; \
	fi

download-embedding-model:
	./scripts/download_embedding_model.sh

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
	$(COMPOSE) run --rm --no-deps backend python -c "from app.services.migration_service import run_db_migrations; run_db_migrations()"

db-reset:
	$(COMPOSE) up -d postgres
	$(COMPOSE) stop backend
	$(COMPOSE) run --rm --no-deps backend python -c "from sqlalchemy import create_engine, text; import os; engine=create_engine(os.environ['DATABASE_URL']); conn=engine.connect(); trans=conn.begin(); conn.execute(text('DROP SCHEMA IF EXISTS public CASCADE')); conn.execute(text('CREATE SCHEMA public')); trans.commit(); conn.close()"
	$(COMPOSE) run --rm --no-deps backend python -c "from app.services.migration_service import run_db_migrations; run_db_migrations()"
	$(COMPOSE) up -d backend

test-backend:
	$(COMPOSE) run --rm --no-deps --build backend sh -lc "PIP_ROOT_USER_ACTION=ignore python -m pip install --disable-pip-version-check --quiet pytest && python -m pytest $(BACKEND_PYTEST_ARGS)"

check-cargo:
	@if [ ! -x "$(CARGO)" ] && ! command -v "$(CARGO)" >/dev/null 2>&1; then \
		echo "cargo not found. Install Rust with rustup or add cargo to PATH."; \
		echo "Expected binary at: $(CARGO)"; \
		exit 127; \
	fi

test-worker: check-cargo
	cd workers-rust && $(CARGO) test -p worker-rss $(WORKER_CARGO_TEST_ARGS)

test-worker-embedding: check-cargo
	cd workers-rust && $(CARGO) test -p worker-source-embedding $(EMBEDDING_WORKER_CARGO_TEST_ARGS)

build-worker-rss-native: check-cargo
	cd workers-rust && $(CARGO) build --release -p worker-rss

run-worker-rss-native: build-worker-rss-native
	./workers-rust/target/release/worker-rss

build-worker-embedding-linux-x86: check-cargo
	cd workers-rust && $(CARGO) build --release -p worker-source-embedding --target $(RUST_LINUX_X86_TARGET)

run-worker-embedding-linux-x86: build-worker-embedding-linux-x86
	./workers-rust/target/$(RUST_LINUX_X86_TARGET)/release/worker-source-embedding
