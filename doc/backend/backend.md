# Backend Service

## Purpose

`backend` is the FastAPI API manager.

It owns:
- HTTP endpoints for admin and internal worker auth
- RSS catalog sync from the Git repository
- Scrape job creation and enqueueing to Redis
- Job status read models from PostgreSQL

It does not parse RSS feeds directly anymore.

## Image and Container

- Image: built from `backend/Dockerfile`
- Container: `manifeed_backend`

## Runtime Dependencies

- `postgres` (job metadata, feeds, sources, scraping state)
- `redis` (request stream publisher)

## Environment Variables

- `DATABASE_URL` (default: `postgresql://manifeed:manifeed@localhost:5432/manifeed`)
- `REDIS_URL` (default: `redis://localhost:6379/0`)
- `REDIS_QUEUE_REQUESTS` (default: `rss_scrape_requests`)
- `RSS_SCRAPE_QUEUE_BATCH_SIZE` (default: `50`)
- `CORS_ORIGINS` (default: `*`)
- `RSS_FEEDS_REPOSITORY_URL` (default: `https://github.com/Dorn-15/rss_feeds`)
- `RSS_FEEDS_REPOSITORY_BRANCH` (default: `main`)
- `RSS_FEEDS_REPOSITORY_PATH` (default: `/tmp/rss_feeds` in code, `/rss_feeds` in compose)
- `WORKER_ID`, `WORKER_SECRET` (fallback worker credentials)
- `WORKER_CREDENTIALS` (optional multi-worker credential map: `worker_a:secret_a,worker_b:secret_b`)
- `WORKER_TOKEN_SECRET` (JWT signing secret)
- `WORKER_TOKEN_TTL_SECONDS` (default: `3600`)

## Ports and Volumes

- Internal port: `8000`
- Host mapping: `${BACKEND_PORT:-8000}:8000`
- Volumes:
  - `./backend:/app`
  - `../rss_feeds:/rss_feeds`

## Endpoint Catalog

### Health

- `GET /health/`
  - Returns: `{"status": "ok|degraded", "database": "ok|unavailable"}`

### RSS Catalog and Toggles

- `GET /rss/`
  - Returns feeds with company metadata and effective `fetchprotection`.

- `PATCH /rss/feeds/{feed_id}/enabled`
  - Request body: `{"enabled": true|false}`
  - Returns: `{"feed_id": <int>, "enabled": <bool>}`

- `PATCH /rss/companies/{company_id}/enabled`
  - Request body: `{"enabled": true|false}`
  - Returns: `{"company_id": <int>, "enabled": <bool>}`

- `POST /rss/sync`
  - Optional query: `force=true`
  - Returns: `{"repository_action": "cloned|update|up_to_date"}`

- `GET /rss/img/{icon_url:path}`
  - Serves icon files from local RSS repository clone.

### Async Scrape Job Entry Points

- `POST /rss/feeds/check`
  - Optional query params: `feed_ids`
  - Enqueues check jobs with `ingest=false`.
  - Returns: `{"job_id": "...", "status": "queued|completed"}`

- `POST /sources/ingest`
  - Optional query params: `feed_ids`
  - Enqueues ingest jobs with `ingest=true`.
  - Returns: `{"job_id": "...", "status": "queued|completed"}`

### Sources Read Endpoints

- `GET /sources/?limit=...&offset=...`
- `GET /sources/feeds/{feed_id}?limit=...&offset=...`
- `GET /sources/companies/{company_id}?limit=...&offset=...`
- `GET /sources/{source_id}`

### Sources Maintenance

- `POST /sources/partitions/repartition-default`
  - Repartitions default source partitions into weekly partitions.

### Job Tracking

- `GET /jobs/{job_id}`
  - Returns aggregate job counters (`feeds_total`, `feeds_processed`, `feeds_success`, `feeds_not_modified`, `feeds_error`) and status.

- `GET /jobs/{job_id}/feeds`
  - Returns per-feed processing status and result metadata.

### Internal Worker Auth

- `POST /internal/workers/token`
  - Request body: `{"worker_id": "...", "worker_secret": "..."}`
  - Returns: `{"access_token": "...", "expires_at": "..."}`

## Redis Queue Publishing Behavior

When enqueueing a job (`/rss/feeds/check` or `/sources/ingest`):

1. Backend creates rows in `rss_scrape_jobs` and `rss_scrape_job_feeds`.
2. Feeds are mixed by company and split into batches (`RSS_SCRAPE_QUEUE_BATCH_SIZE`).
3. Each batch is published as a message to Redis stream `rss_scrape_requests`.
4. If publish fails after DB commit, backend marks the job as `failed`.

## Error Mapping

Custom exception handlers:

- `RssRepositorySyncError` -> `502 Bad Gateway`
- `RssCatalogParseError` -> `422 Unprocessable Entity`
- `RssIconNotFoundError` -> `404 Not Found`
- `RssFeedNotFoundError` -> `404 Not Found`
- `RssCompanyNotFoundError` -> `404 Not Found`
- `RssFeedToggleForbiddenError` -> `409 Conflict`
- `RssJobAlreadyRunningError` -> `409 Conflict`
- `RssJobQueuePublishError` -> `502 Bad Gateway`

## Tests

- `make test-backend`
- `backend/tests/integration_tests/` contains HTTP-level integration tests.
