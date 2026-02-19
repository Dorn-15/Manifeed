# Database Schema

Source of truth: `backend/alembic/versions/0001_initial_schema.py`.

## Enum Types

### `rss_feed_status`
Allowed values:
- `valid`
- `invalid`
- `unchecked`

## Tables

### `rss_company`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `name` | `VARCHAR(50)` | No | - | Unique (`uq_rss_company_name`) |

Indexes:
- `idx_rss_company_name` on `name`

### `rss_tags`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `name` | `VARCHAR(50)` | No | - | Unique (`uq_rss_tags_name`) |

Indexes:
- `idx_rss_tags_name` on `name`

### `rss_feeds`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `INTEGER` | No | - | Primary key |
| `url` | `VARCHAR(500)` | No | - | Unique (`uq_rss_feeds_url`) |
| `company_id` | `INTEGER` | Yes | - | FK -> `rss_company.id` (`ON DELETE SET NULL`) |
| `section` | `VARCHAR(50)` | Yes | - | - |
| `enabled` | `BOOLEAN` | No | `true` | - |
| `status` | `rss_feed_status` | No | `unchecked` | Enum constrained |
| `trust_score` | `FLOAT` | No | `0.5` | Check (`ck_rss_feeds_trust_score`: `0.0 <= trust_score <= 1.0`) |
| `country` | `CHAR(2)` | Yes | - | - |
| `icon_url` | `VARCHAR(500)` | Yes | - | - |
| `parsing_config` | `JSONB` | No | `'{}'::jsonb` | - |
| `last_update` | `TIMESTAMPTZ` | Yes | - | - |
| `created_at` | `TIMESTAMPTZ` | No | `now()` | - |
| `updated_at` | `TIMESTAMPTZ` | No | `now()` | Auto-updated by trigger |

Indexes:
- `idx_rss_feeds_enabled` on `enabled` with predicate `enabled = true`
- `idx_rss_feeds_status` on `status` with predicate `status = 'valid'`
- `idx_rss_feeds_company_id` on `company_id`
- `idx_rss_feeds_company_id_section` on (`company_id`, `section`)

Triggers/functions:
- Function: `set_rss_feeds_updated_at()`
- Trigger: `trg_rss_feeds_updated_at` (`BEFORE UPDATE` on `rss_feeds`) sets `NEW.updated_at = now()`

### `rss_feed_tags`
| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `feed_id` | `INTEGER` | No | - | FK -> `rss_feeds.id` (`ON DELETE CASCADE`) |
| `tag_id` | `INTEGER` | No | - | FK -> `rss_tags.id` (`ON DELETE CASCADE`) |

Primary key:
- Composite PK (`feed_id`, `tag_id`)

Indexes:
- `idx_rss_feed_tags_feed_id` on `feed_id`
- `idx_rss_feed_tags_tag_id` on `tag_id`
