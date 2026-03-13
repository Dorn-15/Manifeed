# Manifeed

An embedding-based feed engine that clusters articles by meaning instead of keywords.

This project is licensed under the GNU AGPLv3.
Commercial hosting or closed-source usage requires a commercial license.

## Architecture

`Manifeed` uses Docker Compose for the database, backend, and admin UI. Rust workers run as native executables.

| Service | Role | Exposed Port |
|---|---|---|
| `postgres` | Primary database | `5432` |
| `backend` | FastAPI API, worker auth, worker gateway, DB orchestration, migrations, projection sync | `${BACKEND_PORT:-8000}` |
| `frontend_admin` | Next.js admin UI | `${ADMIN_PORT:-3000}` |

## Async Scrape Flow

1. A client calls `POST /rss/feeds/check` or `POST /sources/ingest`.
2. `backend` creates the initial `worker_jobs` row plus task rows in PostgreSQL.
3. Workers enroll/authenticate against `POST /internal/workers/enroll`, `POST /internal/workers/auth/challenge`, and `POST /internal/workers/auth/verify`.
4. Workers only talk to `backend` and use signed Ed25519 machine identities plus short-lived JWT sessions.
5. Workers claim / complete / fail directly against `backend`; the RSS worker also publishes state through `POST /internal/workers/rss/state`.
6. `backend` persists worker results, updates runtime/job state, ingests RSS sources, stores embeddings, runs Alembic migrations at startup, and keeps embedding projections synchronized for the admin visualizer.
7. Workers poll every 30 seconds when idle, and immediately claim again after each completed batch while tasks remain.
8. Clients can poll:
   - `GET /jobs/{job_id}`
   - `GET /jobs/{job_id}/feeds`

Workers are therefore deployable outside the local network later, as long as they are allowed to reach `backend` and present a valid enrolled machine identity. They do not need direct database access.

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
- `POST /sources/embeddings/enqueue` (returns `{queued_sources}`)
- `POST /sources/partitions/repartition-default`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/feeds`
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

## Run

```bash
make build
make up
make build-worker-rss-native
make run-worker-rss-native
make build-worker-embedding-linux-x86
make run-worker-embedding-linux-x86
```

Default URLs:
- Admin: `http://localhost:3000`
- API: `http://localhost:8000/health/`
- PostgreSQL: `localhost:5432`

Ports override example:

```bash
BACKEND_PORT=8001 ADMIN_PORT=3002 make up
```

The Rust embedding worker expects ONNX artifacts to already exist under `./models/multilingual-e5-large/` by default:
- `model.onnx`
- `tokenizer.json`
- `config.json`

Bootstrap those artifacts with:

```bash
make download-embedding-model
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
- `make download-embedding-model`
- `make build-worker-rss-native`
- `make run-worker-rss-native`
- `make build-worker-embedding-linux-x86`
- `make run-worker-embedding-linux-x86`

Per service:
- `make up SERVICE=backend`
- `make logs SERVICE=postgres`

Tests:
- `make test-backend`
- `make test-worker`
- `make test-worker-embedding`
The worker test targets now use the local Rust toolchain directly.

Database helpers:
- `make db-migrate` starts `postgres` then runs migrations in a one-shot `backend` container.
- `make db-reset` recreates the `public` schema, runs migrations again, then restarts `backend`.

## Environment Variables

Compose-level defaults:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `BACKEND_PORT`, `ADMIN_PORT`
- `CORS_ORIGINS`
- `NEXT_PUBLIC_API_URL_ADMIN`
- `EMBEDDING_MODEL_NAME`
- `WORKER_ENROLLMENT_TOKENS`
- `RSS_WORKER_ENROLLMENT_TOKEN`

Backend:
- `DATABASE_URL`
- `BACKEND_PROJECTION_POLL_SECONDS`
- `RSS_FEEDS_REPOSITORY_URL`
- `RSS_FEEDS_REPOSITORY_BRANCH`
- `RSS_FEEDS_REPOSITORY_PATH`
- `WORKER_ENROLLMENT_TOKENS`
- `WORKER_TOKEN_SECRET`
- `WORKER_TOKEN_TTL_SECONDS`

Workers:
- RSS worker config is currently hardcoded in [workers-rust/worker-rss/src/config.rs](/home/dorn/Projects/Manifeed/workers-rust/worker-rss/src/config.rs)
- embedding worker config is hardcoded in [workers-rust/worker-source-embedding/src/config.rs](/home/dorn/Projects/Manifeed/workers-rust/worker-source-embedding/src/config.rs)
- embedding worker is run natively outside Compose as well

The RSS worker keeps the simple `claim -> process -> complete -> claim` loop and now exposes its current task state through the backend.
The embedding worker no longer downloads Hugging Face weights at runtime. It requires pre-exported ONNX artifacts referenced by [workers-rust/worker-source-embedding/src/config.rs](/home/dorn/Projects/Manifeed/workers-rust/worker-source-embedding/src/config.rs).

Frontend admin:
- `NEXT_PUBLIC_API_URL`

## Documentation

- `doc/backend/backend.md`
- `doc/backend/worker_rss_scrapper_v2_rust.md`
- `doc/backend/worker_source_embedding_v2_rust_onnx.md`
- `doc/frontend_admin/frontend_admin.md`
- `doc/postgres/postgres.md`
- `doc/postgres/schema.md`
- `doc/postgres/relations.md`
- `doc/postgres/review_db_manifeed_simplification_2026-03-10.md`
