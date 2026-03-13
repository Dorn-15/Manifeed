# Backend Service

## Purpose

`backend` is the FastAPI API manager.

It owns:
- HTTP endpoints for admin, internal worker auth, and worker gateway
- RSS catalog sync from the Git repository
- scrape/embedding job and task creation for client-facing endpoints
- Job status read models from PostgreSQL
- worker enroll/auth/session issuance plus claim/result/fail/state persistence directly in PostgreSQL
- Alembic migrations at startup
- source embedding projection sync

It does not parse RSS feeds directly.

## Runtime Dependencies

- `postgres` (business data + worker orchestration state)

## Environment Variables

- `DATABASE_URL` (default: `postgresql://manifeed:manifeed@localhost:5432/manifeed`)
- `BACKEND_PROJECTION_POLL_SECONDS`
- `EMBEDDING_MODEL_NAME` (default: `intfloat/multilingual-e5-large`)
- `CORS_ORIGINS` (default: `*`)
- `RSS_FEEDS_REPOSITORY_URL`
- `RSS_FEEDS_REPOSITORY_BRANCH`
- `RSS_FEEDS_REPOSITORY_PATH`
- `WORKER_ENROLLMENT_TOKENS`
- `WORKER_TOKEN_SECRET`
- `WORKER_TOKEN_TTL_SECONDS`

## Orchestration Behavior

- `POST /rss/feeds/check` and `POST /sources/ingest`:
  - create exactly one `worker_jobs` row per backend request (`rss_scrape_check` or `rss_scrape_ingest`)
  - create batched `rss_scrape_tasks` rows
  - create one `rss_scrape_task_items` row per feed attached to the batch task
- `POST /sources/embeddings/enqueue`:
  - loads sources without embeddings (or model mismatches)
  - create exactly one `worker_jobs` row per backend request (`source_embedding`)
  - create batched `source_embedding_tasks` rows
  - create one `source_embedding_task_items` row per source attached to the batch task

- worker traffic never reaches PostgreSQL directly:
  - worker -> `backend`
  - `backend` -> PostgreSQL
- worker operations persisted by the backend:
  - RSS: enroll, auth challenge/verify, claim, complete, fail, state
  - embedding: enroll, auth challenge/verify, claim, complete, fail
- worker authentication is handled by machine identities (Ed25519 public keys) and short-lived bearer tokens
- this keeps workers compatible with future external/whitelisted deployment, because they only need network access to `backend`

## Tracking

Clients can poll:
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/feeds`

## Monitoring Tables

- worker liveness comes from `worker_instances`
- task state comes from `rss_scrape_tasks`, `rss_scrape_task_items`, `source_embedding_tasks`, and `source_embedding_task_items`
- execution history, metrics, and failures come from `rss_scrape_task_executions` and `source_embedding_task_executions`
- job status comes from counters stored on `worker_jobs`

## Internal Routes

- `POST /internal/workers/enroll`
- `POST /internal/workers/auth/challenge`
- `POST /internal/workers/auth/verify`
- `GET /internal/workers/me`
- `POST /internal/workers/rss/claim`
- `POST /internal/workers/rss/complete`
- `POST /internal/workers/rss/fail`
- `POST /internal/workers/rss/state`
- `POST /internal/workers/embedding/claim`
- `POST /internal/workers/embedding/complete`
- `POST /internal/workers/embedding/fail`

## Tests

- `make test-backend`
