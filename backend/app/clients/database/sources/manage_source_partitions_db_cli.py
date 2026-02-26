from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)
_SOURCES_DEFAULT_BUFFER_TABLE = "tmp_rss_sources_default_buffer"
_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE = "tmp_rss_source_feeds_default_buffer"


@dataclass(slots=True)
class SourcePartitionMaintenanceResult:
    source_default_rows_repartitioned: int
    source_feed_default_rows_repartitioned: int
    source_weekly_partitions_created: int
    source_feed_weekly_partitions_created: int
    weeks_covered: int


def repartition_default_sources_by_published_at(
    db: Session,
) -> SourcePartitionMaintenanceResult:
    _prepare_default_partition_buffers(db)

    source_default_rows = _count_table_rows(db, _SOURCES_DEFAULT_BUFFER_TABLE)
    source_feed_default_rows = _count_table_rows(db, _SOURCE_FEEDS_DEFAULT_BUFFER_TABLE)

    _clear_default_partitions(db)
    week_starts = _list_week_starts_for_all_sources(db)

    source_partitions_created = 0
    source_feed_partitions_created = 0
    for week_start in week_starts:
        source_created, source_feed_created = _create_weekly_partition_pair(db, week_start)
        source_partitions_created += int(source_created)
        source_feed_partitions_created += int(source_feed_created)

    _restore_sources_from_buffer(db)
    _restore_source_feeds_from_buffer(db)
    _sync_sources_sequence(db)

    return SourcePartitionMaintenanceResult(
        source_default_rows_repartitioned=source_default_rows,
        source_feed_default_rows_repartitioned=source_feed_default_rows,
        source_weekly_partitions_created=source_partitions_created,
        source_feed_weekly_partitions_created=source_feed_partitions_created,
        weeks_covered=len(week_starts),
    )


def _prepare_default_partition_buffers(db: Session) -> None:
    db.execute(text(f"DROP TABLE IF EXISTS pg_temp.{_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}"))
    db.execute(text(f"DROP TABLE IF EXISTS pg_temp.{_SOURCES_DEFAULT_BUFFER_TABLE}"))

    db.execute(
        text(
            f"""
            CREATE TEMP TABLE {_SOURCES_DEFAULT_BUFFER_TABLE}
            ON COMMIT DROP AS
            SELECT
                id,
                title,
                summary,
                author,
                url,
                COALESCE(published_at, :fallback_published_at) AS published_at,
                image_url
            FROM rss_sources_default
            """
        ),
        {"fallback_published_at": SOURCE_PUBLISHED_AT_FALLBACK},
    )
    db.execute(
        text(
            f"""
            CREATE TEMP TABLE {_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}
            ON COMMIT DROP AS
            SELECT
                source_id,
                feed_id,
                COALESCE(published_at, :fallback_published_at) AS published_at
            FROM rss_source_feeds_default
            """
        ),
        {"fallback_published_at": SOURCE_PUBLISHED_AT_FALLBACK},
    )


def _clear_default_partitions(db: Session) -> None:
    db.execute(text("DELETE FROM rss_source_feeds_default"))
    db.execute(text("DELETE FROM rss_sources_default"))


def _list_week_starts_for_all_sources(db: Session) -> list[datetime]:
    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT date_trunc('week', published_at) AS week_start
            FROM (
                SELECT published_at
                FROM rss_sources
                WHERE published_at > :fallback_published_at
                UNION ALL
                SELECT published_at
                FROM {_SOURCES_DEFAULT_BUFFER_TABLE}
                WHERE published_at > :fallback_published_at
            ) AS all_sources
            ORDER BY week_start ASC
            """
        ),
        {"fallback_published_at": SOURCE_PUBLISHED_AT_FALLBACK},
    ).scalars()

    week_starts: list[datetime] = []
    for week_start in rows:
        if not isinstance(week_start, datetime):
            continue
        week_starts.append(_normalize_to_utc(week_start))
    return week_starts


def _create_weekly_partition_pair(
    db: Session,
    week_start: datetime,
) -> tuple[bool, bool]:
    normalized_week_start = _normalize_to_utc(week_start)
    week_end = normalized_week_start + timedelta(days=7)
    partition_suffix = normalized_week_start.strftime("%Y%m%d")

    source_partition_name = f"rss_sources_w_{partition_suffix}"
    source_feed_partition_name = f"rss_source_feeds_w_{partition_suffix}"

    source_partition_created = _create_partition_if_missing(
        db=db,
        table_name=source_partition_name,
        parent_table_name="rss_sources",
        week_start=normalized_week_start,
        week_end=week_end,
    )
    source_feed_partition_created = _create_partition_if_missing(
        db=db,
        table_name=source_feed_partition_name,
        parent_table_name="rss_source_feeds",
        week_start=normalized_week_start,
        week_end=week_end,
    )
    return source_partition_created, source_feed_partition_created


def _create_partition_if_missing(
    db: Session,
    *,
    table_name: str,
    parent_table_name: str,
    week_start: datetime,
    week_end: datetime,
) -> bool:
    if _table_exists(db, table_name):
        return False

    db.execute(
        text(
            f"""
            CREATE TABLE {table_name}
            PARTITION OF {parent_table_name}
            FOR VALUES FROM (:week_start) TO (:week_end)
            """
        ),
        {
            "week_start": week_start,
            "week_end": week_end,
        },
    )
    return True


def _table_exists(db: Session, table_name: str) -> bool:
    existing_table_name = db.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": table_name},
    ).scalar_one_or_none()
    return isinstance(existing_table_name, str) and bool(existing_table_name)


def _restore_sources_from_buffer(db: Session) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO rss_sources (id, title, summary, author, url, published_at, image_url)
            SELECT
                id,
                title,
                summary,
                author,
                url,
                published_at,
                image_url
            FROM {_SOURCES_DEFAULT_BUFFER_TABLE}
            ORDER BY id ASC
            ON CONFLICT (id, published_at) DO NOTHING
            """
        )
    )


def _restore_source_feeds_from_buffer(db: Session) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO rss_source_feeds (source_id, feed_id, published_at)
            SELECT
                source_id,
                feed_id,
                published_at
            FROM {_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}
            ORDER BY source_id ASC, feed_id ASC
            ON CONFLICT (source_id, feed_id, published_at) DO NOTHING
            """
        )
    )


def _sync_sources_sequence(db: Session) -> None:
    db.execute(
        text(
            """
            SELECT setval(
                'rss_sources_id_seq',
                COALESCE((SELECT MAX(id) FROM rss_sources), 1),
                (SELECT EXISTS(SELECT 1 FROM rss_sources))
            )
            """
        )
    )


def _count_table_rows(db: Session, table_name: str) -> int:
    return int(
        db.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")
        ).scalar_one()
        or 0
    )


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
