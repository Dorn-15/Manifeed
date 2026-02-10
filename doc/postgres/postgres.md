# Postgres Service

## Purpose
Primary PostgreSQL database for Manifeed.

## Image
- `postgres:15`

## Container
- `manifeed_postgres`

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
- Not exposed to host by default
- To expose: add `5432:5432` under the service in `docker-compose.yml`

## Useful Commands
- `make logs SERVICE=postgres`

## Schema Documentation
- `doc/postgres/schema.md`: tables, columns, types, defaults, constraints and indexes.
- `doc/postgres/relations.md`: relationship graph between tables.
