# Manifeed

An embedding-based feed engine that clusters articles by meaning instead of keywords.

This project is licensed under the GNU AGPLv3.
Commercial hosting or closed-source usage requires a commercial license.

## Architecture

`Manifeed` is now a microservice-based stack orchestrated with Docker Compose.

| Service | Role | Exposed Port |
|---|---|---|
| `postgres` | Primary database | `5432` |
| `redis` | Queue broker (Redis Streams) | `6379` |
| `backend` | FastAPI API/orchestrator | `${BACKEND_PORT:-8000}` |
| `worker_rss_scrapper` | RSS fetch/parse worker | internal only |
| `db_manager` | Persists worker results + runs Alembic migrations | internal only |
| `frontend_admin` | Next.js admin UI | `${ADMIN_PORT:-3000}` |

## Async Scrape Flow

1. A client calls `POST /rss/feeds/check` or `POST /sources/ingest`.
2. `backend` creates a scrape job in PostgreSQL and publishes job batches to Redis stream `rss_scrape_requests`.
3. `worker_rss_scrapper` consumes requests, fetches/parses feeds, and publishes results to:
   - `rss_check_results`
   - `rss_ingest_results`
   - `error_feeds_parsing`
4. `db_manager` consumes result streams, applies DB updates, recalculates job status, then ACKs the stream entry.
5. Clients can poll:
   - `GET /jobs/{job_id}`
   - `GET /jobs/{job_id}/feeds`

## API Snapshot

- `GET /health/`
- `GET /rss/`
- `PATCH /rss/feeds/{feed_id}/enabled`
- `PATCH /rss/companies/{company_id}/enabled`
- `POST /rss/sync`
- `POST /rss/feeds/check?feed_ids=...` (returns `{job_id, status}`)
- `GET /rss/img/{icon_url:path}`
- `GET /sources/`
- `GET /sources/feeds/{feed_id}`
- `GET /sources/companies/{company_id}`
- `GET /sources/{source_id}`
- `POST /sources/ingest?feed_ids=...` (returns `{job_id, status}`)
- `POST /sources/partitions/repartition-default`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/feeds`
- `POST /internal/workers/token`

## Run

```bash
make build
make up
```

Default URLs:
- Admin: `http://localhost:3000`
- API: `http://localhost:8000/health/`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

Ports override example:

```bash
BACKEND_PORT=8001 ADMIN_PORT=3002 make up
```

## Makefile Commands

Global:
- `make build`
- `make up`
- `make down`
- `make restart`
- `make logs`
- `make clean`
- `make clean-all`
- `make db-migrate`
- `make db-reset`

Per service:
- `make up SERVICE=backend`
- `make logs SERVICE=postgres`

Tests:
- `make test-backend`
- `make test-worker`
- `make test-db-manager`

Database helpers:
- `make db-migrate` starts `postgres` then runs `alembic upgrade head` in a one-shot `db_manager` container.
- `make db-reset` stops `worker_rss_scrapper` and `db_manager`, runs `alembic downgrade base` then `upgrade head`, then starts workers again.

## Environment Variables

Compose-level defaults:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `BACKEND_PORT`, `ADMIN_PORT`
- `CORS_ORIGINS`
- `NEXT_PUBLIC_API_URL_ADMIN`

Backend:
- `DATABASE_URL`
- `REDIS_URL`
- `REDIS_QUEUE_REQUESTS`
- `RSS_SCRAPE_QUEUE_BATCH_SIZE`
- `RSS_FEEDS_REPOSITORY_URL`
- `RSS_FEEDS_REPOSITORY_BRANCH`
- `RSS_FEEDS_REPOSITORY_PATH`
- `WORKER_ID`, `WORKER_SECRET`
- `WORKER_CREDENTIALS`
- `WORKER_TOKEN_SECRET`
- `WORKER_TOKEN_TTL_SECONDS`

Worker:
- `MANIFEED_API_URL`
- `WORKER_ID`, `WORKER_SECRET`
- `WORKER_QUEUE_READ_COUNT`
- `WORKER_COMPANY_MAX_REQUESTS_PER_SECOND`
- `REDIS_URL`

DB manager:
- `DATABASE_URL`
- `REDIS_URL`

Frontend admin:
- `NEXT_PUBLIC_API_URL`

## Documentation

- `doc/backend/backend.md`
- `doc/backend/worker_rss_scrapper.md`
- `doc/db_manager/db_manager.md`
- `doc/redis/redis.md`
- `doc/frontend_admin/frontend_admin.md`
- `doc/postgres/postgres.md`
- `doc/postgres/schema.md`
- `doc/postgres/relations.md`
