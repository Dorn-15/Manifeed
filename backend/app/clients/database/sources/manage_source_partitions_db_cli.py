from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

_SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE = "tmp_rss_sources_default_buffer"
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

    content_default_rows = _count_table_rows(db, _SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE)
    source_feed_default_rows = _count_table_rows(db, _SOURCE_FEEDS_DEFAULT_BUFFER_TABLE)

    _clear_default_partitions(db)
    month_starts = _list_week_starts_for_all_sources(db)

    content_partitions_created = 0
    source_feed_partitions_created = 0
    for month_start in month_starts:
        contents_created, source_feed_created = _create_weekly_partition_pair(db, month_start)
        content_partitions_created += int(contents_created)
        source_feed_partitions_created += int(source_feed_created)

    _restore_sources_from_buffer(db)
    _restore_source_feeds_from_buffer(db)
    _sync_sources_sequence(db)

    return SourcePartitionMaintenanceResult(
        source_default_rows_repartitioned=content_default_rows,
        source_feed_default_rows_repartitioned=source_feed_default_rows,
        source_weekly_partitions_created=content_partitions_created,
        source_feed_weekly_partitions_created=source_feed_partitions_created,
        weeks_covered=len(month_starts),
    )


def _prepare_default_partition_buffers(db: Session) -> None:
    db.execute(text(f"DROP TABLE IF EXISTS pg_temp.{_SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE}"))
    db.execute(text(f"DROP TABLE IF EXISTS pg_temp.{_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}"))

    db.execute(
        text(
            f"""
            CREATE TEMP TABLE {_SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE}
            ON COMMIT DROP AS
            SELECT
                source_id,
                ingested_at,
                title,
                summary,
                author,
                image_url
            FROM rss_source_contents_default
            """
        )
    )
    db.execute(
        text(
            f"""
            CREATE TEMP TABLE {_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}
            ON COMMIT DROP AS
            SELECT
                source_id,
                feed_id,
                ingested_at
            FROM rss_source_feeds_default
            """
        )
    )


def _clear_default_partitions(db: Session) -> None:
    db.execute(text("DELETE FROM rss_source_feeds_default"))
    db.execute(text("DELETE FROM rss_source_contents_default"))


def _list_month_starts_for_all_default_rows(db: Session) -> list[datetime]:
    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT date_trunc('month', ingested_at) AS month_start
            FROM (
                SELECT ingested_at FROM {_SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE}
                UNION ALL
                SELECT ingested_at FROM {_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}
            ) AS default_rows
            ORDER BY month_start ASC
            """
        )
    ).scalars()

    month_starts: list[datetime] = []
    for month_start in rows:
        if not isinstance(month_start, datetime):
            continue
        month_starts.append(_normalize_to_utc(month_start))
    return month_starts


def _create_monthly_partition_pair(
    db: Session,
    month_start: datetime,
) -> tuple[bool, bool]:
    normalized_month_start = _normalize_to_utc(month_start)
    month_end = (normalized_month_start + timedelta(days=32)).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    partition_suffix = normalized_month_start.strftime("%Y%m")

    content_partition_name = f"rss_source_contents_m_{partition_suffix}"
    source_feed_partition_name = f"rss_source_feeds_m_{partition_suffix}"

    content_partition_created = _create_partition_if_missing(
        db=db,
        table_name=content_partition_name,
        parent_table_name="rss_source_contents",
        month_start=normalized_month_start,
        month_end=month_end,
    )
    source_feed_partition_created = _create_partition_if_missing(
        db=db,
        table_name=source_feed_partition_name,
        parent_table_name="rss_source_feeds",
        month_start=normalized_month_start,
        month_end=month_end,
    )
    return content_partition_created, source_feed_partition_created


def _list_week_starts_for_all_sources(db: Session) -> list[datetime]:
    return _list_month_starts_for_all_default_rows(db)


def _create_weekly_partition_pair(
    db: Session,
    week_start: datetime,
) -> tuple[bool, bool]:
    return _create_monthly_partition_pair(db, week_start)


def _create_partition_if_missing(
    db: Session,
    *,
    table_name: str,
    parent_table_name: str,
    month_start: datetime,
    month_end: datetime,
) -> bool:
    if _table_exists(db, table_name):
        return False

    db.execute(
        text(
            f"""
            CREATE TABLE {table_name}
            PARTITION OF {parent_table_name}
            FOR VALUES FROM (:month_start) TO (:month_end)
            """
        ),
        {
            "month_start": month_start,
            "month_end": month_end,
        },
    )
    return True


def _table_exists(db: Session, table_name: str) -> bool:
    existing_table_name = db.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": table_name},
    ).scalar_one_or_none()
    return isinstance(existing_table_name, str) and bool(existing_table_name)


def _restore_source_contents_from_buffer(db: Session) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO rss_source_contents (
                source_id,
                ingested_at,
                title,
                summary,
                author,
                image_url
            )
            SELECT
                source_id,
                ingested_at,
                title,
                summary,
                author,
                image_url
            FROM {_SOURCE_CONTENTS_DEFAULT_BUFFER_TABLE}
            ORDER BY source_id ASC
            ON CONFLICT (source_id, ingested_at) DO NOTHING
            """
        )
    )


def _restore_source_feeds_from_buffer(db: Session) -> None:
    db.execute(
        text(
            f"""
            INSERT INTO rss_source_feeds (
                source_id,
                feed_id,
                ingested_at
            )
            SELECT
                source_id,
                feed_id,
                ingested_at
            FROM {_SOURCE_FEEDS_DEFAULT_BUFFER_TABLE}
            ORDER BY source_id ASC, feed_id ASC
            ON CONFLICT (source_id, feed_id, ingested_at) DO NOTHING
            """
        )
    )


def _count_table_rows(db: Session, table_name: str) -> int:
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one() or 0)


def _restore_sources_from_buffer(db: Session) -> None:
    _restore_source_contents_from_buffer(db)


def _sync_sources_sequence(db: Session) -> None:
    return None


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
