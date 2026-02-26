# Database Schema

Source of truth:
- Alembic migrations in `db-manager/alembic/versions/`
- Latest revision: `0006_scrape_jobs_v2`

## Overview

Main table groups:
- RSS catalog: `rss_company`, `rss_feeds`, `rss_tags`, `rss_feed_tags`
- Scraping state: `feeds_scraping`
- Sources: `rss_sources`, `rss_source_feeds` (+ default partitions)
- Async jobs: `rss_scrape_jobs`, `rss_scrape_job_feeds`, `rss_scrape_job_results`

## Tables

### `rss_company`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `name` | `VARCHAR(50)` | No | - | Unique (`uq_rss_company_name`) |
| `host` | `VARCHAR(255)` | Yes | - | Optional host hint for worker headers |
| `icon_url` | `VARCHAR(500)` | Yes | - | Company icon path |
| `country` | `CHAR(2)` | Yes | - | ISO-like country code |
| `language` | `CHAR(2)` | Yes | - | ISO-like language code |
| `fetchprotection` | `SMALLINT` | No | `1` | Check `0 <= fetchprotection <= 2` |
| `enabled` | `BOOLEAN` | No | `true` | Company toggle |

Indexes:
- `idx_rss_company_country` on `country`
- `idx_rss_company_language` on `language`

### `rss_feeds`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `url` | `VARCHAR(500)` | No | - | Unique (`uq_rss_feeds_url`) |
| `section` | `VARCHAR(50)` | Yes | - | Optional feed section |
| `enabled` | `BOOLEAN` | No | `true` | Feed toggle |
| `trust_score` | `FLOAT` | No | `0.5` | Check `0.0 <= trust_score <= 1.0` |
| `company_id` | `INTEGER` | Yes | - | FK -> `rss_company.id` (`ON DELETE SET NULL`) |

Indexes:
- `idx_rss_feeds_enabled` on `enabled` with predicate `enabled = true`
- `idx_rss_feeds_company_id` on `company_id`

### `rss_tags`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `name` | `VARCHAR(50)` | No | - | Unique (`uq_rss_tags_name`) |

### `rss_feed_tags`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `feed_id` | `INTEGER` | No | - | FK -> `rss_feeds.id` (`ON DELETE CASCADE`) |
| `tag_id` | `INTEGER` | No | - | FK -> `rss_tags.id` (`ON DELETE CASCADE`) |

Primary key:
- (`feed_id`, `tag_id`)

Indexes:
- `idx_rss_feed_tags_tag_id` on `tag_id`

### `feeds_scraping`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `feed_id` | `INTEGER` | No | - | PK + FK -> `rss_feeds.id` (`ON DELETE CASCADE`) |
| `fetchprotection` | `SMALLINT` | No | `1` | Check `0 <= fetchprotection <= 2` |
| `last_update` | `TIMESTAMPTZ` | Yes | - | Last known feed update time |
| `etag` | `VARCHAR(255)` | Yes | - | Last known ETag |
| `error_nbr` | `INTEGER` | No | `0` | Check `error_nbr >= 0` |
| `error_msg` | `TEXT` | Yes | - | Last scrape error |

Indexes:
- `idx_feeds_scraping_fetchprotection` on `fetchprotection`

### `rss_sources` (partitioned)

Partition key:
- `RANGE (published_at)`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `INTEGER` | No | `nextval('rss_sources_id_seq')` | Part of composite PK |
| `title` | `VARCHAR(500)` | No | - | Source title |
| `summary` | `TEXT` | Yes | - | Optional summary |
| `author` | `VARCHAR(255)` | Yes | - | Optional author |
| `url` | `VARCHAR(1000)` | No | - | Source URL |
| `published_at` | `TIMESTAMPTZ` | No | `1970-01-01T00:00:00+00:00` | Part of composite PK |
| `image_url` | `VARCHAR(1000)` | Yes | - | Optional image |

Constraints:
- Primary key: (`id`, `published_at`)
- Unique: (`url`, `published_at`) as `uq_rss_sources_url_published_at`

Indexes:
- `idx_rss_sources_published_at` on `published_at`

### `rss_source_feeds` (partitioned)

Partition key:
- `RANGE (published_at)`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `source_id` | `INTEGER` | No | - | Part of composite PK |
| `feed_id` | `INTEGER` | No | - | Part of composite PK, FK -> `rss_feeds.id` |
| `published_at` | `TIMESTAMPTZ` | No | `1970-01-01T00:00:00+00:00` | Part of composite PK |

Constraints:
- Primary key: (`source_id`, `feed_id`, `published_at`)
- FK (`source_id`, `published_at`) -> `rss_sources(id, published_at)` (`ON DELETE CASCADE`, `ON UPDATE CASCADE`)
- FK (`feed_id`) -> `rss_feeds(id)` (`ON DELETE CASCADE`)

Indexes:
- `idx_rss_source_feeds_source_id_published_at` on (`source_id`, `published_at`)
- `idx_rss_source_feeds_feed_id` on `feed_id`
- `idx_rss_source_feeds_published_at` on `published_at`

### `rss_scrape_jobs`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `job_id` | `VARCHAR(36)` | No | - | Primary key (UUID string) |
| `ingest` | `BOOLEAN` | No | - | `true` for sources ingest jobs |
| `requested_by` | `VARCHAR(100)` | No | - | Origin endpoint marker |
| `requested_at` | `TIMESTAMPTZ` | No | - | Job creation timestamp |
| `feed_count` | `INTEGER` | No | - | Check `feed_count >= 0` |
| `status` | `VARCHAR(40)` | No | `'queued'` | Check enum-like constraint |
| `updated_at` | `TIMESTAMPTZ` | No | `now()` | Last status update |

Allowed `status` values:
- `queued`
- `processing`
- `completed`
- `completed_with_errors`
- `failed`

Indexes:
- `idx_rss_scrape_jobs_requested_at` on `requested_at`

### `rss_scrape_job_feeds`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `job_id` | `VARCHAR(36)` | No | - | FK -> `rss_scrape_jobs.job_id` |
| `feed_id` | `INTEGER` | No | - | FK -> `rss_feeds.id` |
| `feed_url` | `VARCHAR(500)` | No | - | Snapshot of feed URL at enqueue time |
| `last_db_article_published_at` | `TIMESTAMPTZ` | Yes | - | Last known source timestamp in DB |

Primary key:
- (`job_id`, `feed_id`)

Indexes:
- `idx_rss_scrape_job_feeds_feed_id` on `feed_id`

### `rss_scrape_job_results`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `job_id` | `VARCHAR(36)` | No | - | FK -> `rss_scrape_jobs.job_id` |
| `feed_id` | `INTEGER` | No | - | FK -> `rss_feeds.id` |
| `status` | `VARCHAR(32)` | No | - | `success|not_modified|error` |
| `queue_kind` | `VARCHAR(32)` | No | - | `check|ingest|error` |
| `error_message` | `TEXT` | Yes | - | Failure reason |
| `fetchprotection` | `SMALLINT` | Yes | - | Runtime fetch mode used |
| `new_etag` | `VARCHAR(255)` | Yes | - | Latest etag from worker |
| `new_last_update` | `TIMESTAMPTZ` | Yes | - | Latest update timestamp from worker |
| `processed_at` | `TIMESTAMPTZ` | No | `now()` | Persistence timestamp |

Primary key:
- (`job_id`, `feed_id`)

Constraints:
- `status IN ('success', 'not_modified', 'error')`
- `queue_kind IN ('check', 'ingest', 'error')`

## Sequences and Partitions

- Sequence: `rss_sources_id_seq` (owned by `rss_sources.id`)
- Default partitions:
  - `rss_sources_default`
  - `rss_source_feeds_default`

Weekly partitions are created by backend maintenance endpoint:
- `POST /sources/partitions/repartition-default`
