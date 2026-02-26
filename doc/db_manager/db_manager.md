# db_manager Service

## Purpose

`db_manager` is the persistence microservice for worker outputs.

It:
- runs Alembic migrations at startup
- consumes worker result streams from Redis
- upserts scraping state and sources in PostgreSQL
- updates aggregate scrape job status

## Image and Container

- Image: built from `db-manager/Dockerfile`
- Container: `manifeed_db_manager`

## Dependencies

- `postgres`
- `redis`

## Startup Sequence

`main.py` flow:
1. `run_db_migrations()`
2. start async `run_result_consumer()` loop

Migration behavior:
- retries up to 5 attempts by default
- 2 seconds between attempts

## Redis Streams

Consumed streams:
- `rss_check_results`
- `rss_ingest_results`
- `error_feeds_parsing`

Consumer group:
- Group: `db_manager_group`
- Consumer: `db_manager_1`

For each message:
1. parse payload into `WorkerResultSchema`
2. map stream to `queue_kind` (`check|ingest|error`)
3. persist in DB transaction
4. ACK only after successful commit

Invalid payloads are ACKed and logged.

## Persistence Rules

### Idempotency

- Results table primary key is (`job_id`, `feed_id`)
- Existing result for same pair is ignored (`ON CONFLICT DO NOTHING`)

### Always persisted

- Insert into `rss_scrape_job_results` when job exists
- Upsert into `feeds_scraping`:
  - `fetchprotection`
  - `etag`
  - `last_update`
  - error counters/messages

### Ingest-only persistence

When `queue_kind == ingest` and payload status is `success`:
- upsert `rss_sources` (`url`, `published_at` uniqueness)
- upsert relation `rss_source_feeds`

### Job status recomputation

`rss_scrape_jobs.status` is recomputed from results:
- `completed` when `feed_count == 0`
- `queued` when `processed_count == 0`
- `processing` when `processed_count < feed_count`
- `completed_with_errors` when all processed and error count > 0
- `completed` when all processed without errors

## Environment Variables

- `DATABASE_URL` (default `postgresql://manifeed:manifeed@postgres:5432/manifeed`)
- `REDIS_URL` (default `redis://redis:6379/0`)

Note: stream names and group names are currently constants in code.

## Useful Commands

- `make up SERVICE=db_manager`
- `make logs SERVICE=db_manager`
- `make test-db-manager`
- `make db-migrate`
