# Postgres Service

## Purpose

Primary PostgreSQL database for Manifeed.

It stores:
- RSS catalog entities (companies, feeds, tags)
- Feed runtime state (`rss_feed_runtime`)
- Source identity/content/link tables (`rss_sources`, `rss_source_contents`, `rss_source_feeds`)
- Worker orchestration tables (`worker_jobs`, `worker_instances`, `rss_scrape_*`, `source_embedding_*`)
- Embedding model and vector tables (`embedding_models`, `rss_source_embeddings`)
- Embedding projection tables for the admin visualizer

## Image and Container

- Image: `postgres:15`
- Container: `manifeed_postgres`

## Environment

- `POSTGRES_DB` (default `manifeed`)
- `POSTGRES_USER` (default `manifeed`)
- `POSTGRES_PASSWORD` (default `manifeed`)

## Storage

- Volume: `pgdata:/var/lib/postgresql/data`

## Networks

- `manifeed_internal`

## Healthcheck

- `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`

## Ports

Current compose exposes PostgreSQL to host:
- `5432:5432`

## Migrations

Alembic migrations are managed from `backend/alembic`.

Common commands:
- `make db-migrate`
- `make db-reset`
- `docker compose run --rm --no-deps backend python -c "from app.services.migration_service import run_db_migrations; run_db_migrations()"`

## Useful Commands

- `make logs SERVICE=postgres`

## Schema Documentation

- `doc/postgres/schema.md`: tables, columns, constraints, indexes.
- `doc/postgres/relations.md`: relation graph and relationship notes.