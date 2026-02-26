# worker_rss_scrapper

## Purpose

`worker_rss_scrapper` is the RSS processing microservice.

It:
- consumes scrape jobs from Redis stream `rss_scrape_requests`
- fetches and parses RSS/Atom feeds
- normalizes sources
- publishes per-feed results to result streams consumed by `db_manager`

It does not write to PostgreSQL directly.

## Image and Container

- Image: built from `worker-rss-scrapper/Dockerfile`
- Container: `manifeed_worker_rss_scrapper`

## Dependencies

- `backend` (worker token endpoint)
- `redis` (streams)

## Startup and Main Loop

At startup, the worker:
1. creates Redis consumer group `worker_rss_scrapper_group` on stream `rss_scrape_requests`
2. starts an async loop
3. refreshes/validates worker token via backend
4. reads jobs with `XREADGROUP`
5. processes feeds concurrently (grouped by company for per-company rate limiting)
6. publishes result messages
7. ACKs the request message only after processing/publishing

If a queue/auth/network failure happens, it retries in loop with short delay.

## Redis Streams and Consumer Group

Input:
- Stream: `rss_scrape_requests`
- Group: `worker_rss_scrapper_group`
- Consumer: `worker_rss_scrapper_1`

Outputs:
- `rss_check_results` for check jobs
- `rss_ingest_results` for ingest jobs
- `error_feeds_parsing` for feed errors

Queue operations use reconnect-once behavior for Redis connection errors/timeouts.

## Message Contracts

### Input payload (`rss_scrape_requests`)

```json
{
  "job_id": "uuid",
  "requested_at": "2026-02-26T12:00:00Z",
  "ingest": true,
  "requested_by": "sources_ingest_endpoint",
  "feeds": [
    {
      "feed_id": 42,
      "feed_url": "https://example.com/rss.xml",
      "company_id": 5,
      "host_header": "example.com",
      "fetchprotection": 2,
      "etag": "\"abc123\"",
      "last_update": "2026-02-25T19:02:10Z",
      "last_db_article_published_at": "2026-02-24T08:00:00Z"
    }
  ]
}
```

### Output payload (`rss_check_results` / `rss_ingest_results` / `error_feeds_parsing`)

```json
{
  "job_id": "uuid",
  "ingest": true,
  "feed_id": 42,
  "feed_url": "https://example.com/rss.xml",
  "status": "success|not_modified|error",
  "error_message": null,
  "new_etag": "\"def456\"",
  "new_last_update": "2026-02-26T11:58:00Z",
  "fetchprotection": 2,
  "sources": [
    {
      "title": "Article A",
      "url": "https://example.com/article-a",
      "summary": "Summary",
      "author": "Editorial",
      "published_at": "2026-02-26T11:50:00Z",
      "image_url": "https://example.com/image-a.jpg"
    }
  ]
}
```

## Fetch and Parse Behavior

Per feed:

1. Build request headers from feed settings.
2. Fetch with retry (`max_attempts=3`, linear backoff).
3. Detect `not_modified` via:
   - HTTP `304`, or
   - same `etag` / `last-modified` as DB state.
4. Parse RSS/Atom XML entries.
5. Normalize and deduplicate source items.
6. Publish result message.

Status mapping:
- `success`: feed parsed and normalized
- `not_modified`: no content change
- `error`: fetch/parse failure

## fetchprotection Strategy (`0..2`)

- `0`: blocked, no outbound request, immediate `error`
- `1`: request without default RSS headers
- `2`: request with default RSS headers (+ optional host/origin/referer based on `host_header`)

Conditional headers:
- `If-None-Match` from input `etag`
- `If-Modified-Since` from input `last_update`

## Normalization Rules

- Require `title` and `url`
- Drop duplicate URLs in one feed run
- Keep only entries with `published_at >= 2026-01-01T00:00:00Z`
- Normalize fields: `title`, `url`, `summary`, `author`, `published_at`, `image_url`

## Worker Authentication

The worker authenticates against backend endpoint:
- `POST /internal/workers/token`

Token handling:
- uses `WORKER_ID` + `WORKER_SECRET`
- caches token and refreshes when close to expiry (`60s` buffer)

## Environment Variables

- `MANIFEED_API_URL` (default `http://backend:8000`)
- `WORKER_ID` (default `worker_rss_scrapper`)
- `WORKER_SECRET` (default `change-me` in code)
- `REDIS_URL` (default `redis://redis:6379/0`)
- `WORKER_QUEUE_READ_COUNT` (default `20`)
- `WORKER_COMPANY_MAX_REQUESTS_PER_SECOND` (default `4`)

Note: stream names and consumer group names are currently hardcoded in code.

## Tests

- `make test-worker`
- Unit tests under `worker-rss-scrapper/tests/unit_tests/` cover queue, auth, parsing, normalization and worker service behavior.
