# Postgres Service

## Purpose

Primary PostgreSQL database for Manifeed.

It stores:
- RSS catalog entities (companies, feeds, tags)
- Scraping runtime state (`feeds_scraping`)
- Source content (`rss_sources`, `rss_source_feeds`)
- Async scrape job tracking (`rss_scrape_jobs`, `rss_scrape_job_feeds`, `rss_scrape_job_results`)

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

Alembic migrations are managed from `db-manager/alembic`.

Common commands:
- `make db-migrate`
- `make db-reset`
- `docker compose run --rm --no-deps db_manager alembic upgrade head`

## Useful Commands

- `make logs SERVICE=postgres`

## Schema Documentation

- `doc/postgres/schema.md`: tables, columns, constraints, indexes.
- `doc/postgres/relations.md`: relation graph and relationship notes.
