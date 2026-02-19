# Backend Service

## Purpose
FastAPI API server and database access layer for health and RSS workflows.

## Image
- Built from `backend/Dockerfile`

## Container
- `manifeed_backend`

## Environment
- `DATABASE_URL` (default in code: `postgresql://manifeed:manifeed@localhost:5432/manifeed`)
- `CORS_ORIGINS` (default `*`; supports comma-separated origins)
- `RSS_FEEDS_REPOSITORY_URL` (default `https://github.com/Dorn-15/rss_feeds`)
- `RSS_FEEDS_REPOSITORY_BRANCH` (default `main`)
- `RSS_FEEDS_REPOSITORY_PATH` (default `/tmp/rss_feeds`)

## Ports
- `8000` inside container
- Host mapping: `BACKEND_PORT` (default `8000`)

## Volumes
- `./backend:/app`

## Dependencies
- `postgres` (waits for healthcheck)

## Endpoints
- `GET /health/`
  - Returns `{"status": "ok|degraded", "database": "ok|unavailable"}`
- `GET /rss/`
  - Returns a list of RSS feeds (`id`, `url`, `company_name`, `section`, `enabled`, `status`, `trust_score`, `country`, `icon_url`)
- `POST /rss/sync`
  - Syncs RSS catalog from git repository and returns counters (`processed_files`, `processed_feeds`, `created_*`, `updated_feeds`, `deleted_feeds`)
- `GET /rss/img/{icon_url:path}`
  - Serves local SVG icon files from the synced RSS repository

## RSS Sync Behavior
- Clones or updates the configured RSS git repository
- Processes only changed `.json` catalog files on pull (all `.json` files on first clone)
- Upserts companies, tags and feeds
- Deletes stale feeds not present in a company's source catalog
- Wraps sync in a DB transaction (`commit` on success, `rollback` on error)

## RSS Error Mapping
- `RssRepositorySyncError` -> `502 Bad Gateway`
- `RssCatalogParseError` -> `422 Unprocessable Entity`
- `RssIconNotFoundError` -> `404 Not Found`

## Migrations
- `make db-migrate` runs `alembic upgrade head`
- `make db-reset` downgrades to `base` then upgrades to `head`
- Manual: `docker compose exec backend alembic upgrade head`
