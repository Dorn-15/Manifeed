from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.rss import (
    RssScrapeFeedPayloadSchema,
    RssScrapeJobFeedRead,
    RssScrapeJobStatusRead,
)
from app.utils import normalize_host


def list_rss_feed_scrape_payloads(
    db: Session,
    *,
    feed_ids: Sequence[int] | None = None,
    enabled_only: bool = False,
) -> list[RssScrapeFeedPayloadSchema]:
    filters: list[str] = []
    params: dict[str, object] = {}
    if enabled_only:
        filters.append("feed.enabled = TRUE")
    if feed_ids:
        normalized_ids = sorted({feed_id for feed_id in feed_ids if isinstance(feed_id, int) and feed_id > 0})
        if not normalized_ids:
            return []
        filters.append("feed.id = ANY(:feed_ids)")
        params["feed_ids"] = normalized_ids

    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)

    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    feed.id AS feed_id,
                    feed.url AS feed_url,
                    feed.company_id,
                    company.host AS company_host,
                    COALESCE(feed.fetchprotection_override, company.fetchprotection, 1) AS fetchprotection,
                    runtime.etag,
                    runtime.last_feed_updated_at,
                    runtime.last_db_article_published_at
                FROM rss_feeds AS feed
                LEFT JOIN rss_company AS company
                    ON company.id = feed.company_id
                LEFT JOIN rss_feed_runtime AS runtime
                    ON runtime.feed_id = feed.id
                {where_sql}
                ORDER BY feed.id ASC
                """
            ),
            params,
        )
        .mappings()
        .all()
    )

    return [
        RssScrapeFeedPayloadSchema(
            feed_id=int(row["feed_id"]),
            feed_url=str(row["feed_url"]),
            company_id=(int(row["company_id"]) if row["company_id"] is not None else None),
            host_header=normalize_host(row["company_host"]),
            fetchprotection=int(row["fetchprotection"] or 1),
            etag=(str(row["etag"]) if row["etag"] is not None else None),
            last_update=_normalize_datetime(row["last_feed_updated_at"]),
            last_db_article_published_at=_normalize_datetime(row["last_db_article_published_at"]),
        )
        for row in rows
    ]


def create_rss_scrape_job(
    db: Session,
    *,
    job_id: str,
    ingest: bool,
    requested_by: str,
    requested_at: datetime,
    status: str,
    tasks_total: int,
    items_total: int,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO worker_jobs (
                id,
                job_kind,
                requested_by,
                status,
                requested_at,
                tasks_total,
                tasks_processed,
                items_total,
                items_processed,
                items_success,
                items_error,
                created_at,
                updated_at
            ) VALUES (
                :job_id,
                :job_kind,
                :requested_by,
                :status,
                :requested_at,
                :tasks_total,
                0,
                :items_total,
                0,
                0,
                0,
                :requested_at,
                :requested_at
            )
            """
        ),
        {
            "job_id": job_id,
            "job_kind": ("rss_scrape_ingest" if ingest else "rss_scrape_check"),
            "requested_by": requested_by,
            "status": status,
            "requested_at": _normalize_datetime(requested_at) or datetime.now(timezone.utc),
            "tasks_total": max(0, int(tasks_total)),
            "items_total": max(0, int(items_total)),
        },
    )

def get_rss_scrape_job_status_read(
    db: Session,
    *,
    job_id: str,
) -> RssScrapeJobStatusRead | None:
    row = (
        db.execute(
            text(
                """
                SELECT
                    job.id AS job_id,
                    job.job_kind,
                    job.requested_by,
                    job.requested_at,
                    job.status,
                    job.tasks_total,
                    job.tasks_processed,
                    job.items_total AS feeds_total,
                    job.items_processed AS feeds_processed,
                    COUNT(item.feed_id) FILTER (WHERE item.status = 'success') AS feeds_success,
                    COUNT(item.feed_id) FILTER (WHERE item.status = 'not_modified') AS feeds_not_modified,
                    COUNT(item.feed_id) FILTER (WHERE item.status = 'error') AS feeds_error
                FROM worker_jobs AS job
                LEFT JOIN rss_scrape_tasks AS task
                    ON task.job_id = job.id
                LEFT JOIN rss_scrape_task_items AS item
                    ON item.task_id = task.id
                WHERE job.id = :job_id
                    AND job.job_kind IN ('rss_scrape_check', 'rss_scrape_ingest')
                GROUP BY
                    job.id,
                    job.job_kind,
                    job.requested_by,
                    job.requested_at,
                    job.status,
                    job.tasks_total,
                    job.tasks_processed,
                    job.items_total,
                    job.items_processed
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    return RssScrapeJobStatusRead(
        job_id=str(row["job_id"]),
        ingest=(row["job_kind"] == "rss_scrape_ingest"),
        requested_by=str(row["requested_by"]),
        requested_at=_normalize_datetime(row["requested_at"]) or datetime.now(timezone.utc),
        status=str(row["status"]),  # type: ignore[arg-type]
        tasks_total=int(row["tasks_total"] or 0),
        tasks_processed=int(row["tasks_processed"] or 0),
        feeds_total=int(row["feeds_total"] or 0),
        feeds_processed=int(row["feeds_processed"] or 0),
        feeds_success=int(row["feeds_success"] or 0),
        feeds_not_modified=int(row["feeds_not_modified"] or 0),
        feeds_error=int(row["feeds_error"] or 0),
    )


def list_rss_scrape_job_feed_reads(
    db: Session,
    *,
    job_id: str,
) -> list[RssScrapeJobFeedRead]:
    rows = (
        db.execute(
            text(
                """
                SELECT
                    item.feed_id,
                    feed.url AS feed_url,
                    item.status,
                    item.error_message,
                    item.fetchprotection_used,
                    item.new_etag,
                    item.new_last_update
                FROM rss_scrape_task_items AS item
                JOIN rss_scrape_tasks AS task
                    ON task.id = item.task_id
                JOIN rss_feeds AS feed
                    ON feed.id = item.feed_id
                WHERE task.job_id = :job_id
                ORDER BY item.feed_id ASC
                """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .all()
    )

    return [
        RssScrapeJobFeedRead(
            feed_id=int(row["feed_id"]),
            feed_url=str(row["feed_url"]),
            status=str(row["status"]),  # type: ignore[arg-type]
            error_message=(str(row["error_message"]) if row["error_message"] is not None else None),
            fetchprotection=(
                int(row["fetchprotection_used"])
                if row["fetchprotection_used"] is not None
                else None
            ),
            new_etag=(str(row["new_etag"]) if row["new_etag"] is not None else None),
            new_last_update=_normalize_datetime(row["new_last_update"]),
        )
        for row in rows
    ]


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
