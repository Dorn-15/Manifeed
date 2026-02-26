# Redis Service

## Purpose

`redis` is the message broker for Manifeed microservices.

It is used with Redis Streams to decouple:
- job enqueueing (`backend`)
- RSS processing (`worker_rss_scrapper`)
- DB persistence (`db_manager`)

## Image and Container

- Image: `redis:7-alpine`
- Container: `manifeed_redis`

## Ports and Networks

- Host mapping: `6379:6379`
- Network: `manifeed_internal`

## Healthcheck

- `redis-cli ping`

## Streams Used

Request stream:
- `rss_scrape_requests`

Result streams:
- `rss_check_results`
- `rss_ingest_results`
- `error_feeds_parsing`

## Producers and Consumers

- `backend`:
  - publishes to `rss_scrape_requests`

- `worker_rss_scrapper`:
  - consumes `rss_scrape_requests` via consumer group `worker_rss_scrapper_group`
  - publishes to result/error streams

- `db_manager`:
  - consumes result/error streams via consumer group `db_manager_group`
  - ACKs after successful DB commit

## Reliability Notes

- Both worker and db_manager retry Redis commands on connection/timeout errors.
- Both services recreate consumer groups on `NOGROUP` errors.
- Stream message payloads are JSON serialized under a single field: `payload`.

## Useful Commands

- `make logs SERVICE=redis`
- `docker compose exec redis redis-cli XINFO STREAM rss_scrape_requests`
- `docker compose exec redis redis-cli XINFO GROUPS rss_scrape_requests`
