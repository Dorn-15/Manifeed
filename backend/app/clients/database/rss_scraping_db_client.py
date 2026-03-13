from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import WorkerResultSchema


def upsert_feed_scraping_state(
    db: Session,
    *,
    payload: WorkerResultSchema,
    apply_resolved_fetchprotection: bool,
) -> None:
    is_error = payload.status == "error"
    is_success = payload.status in {"success", "not_modified"}
    latest_source_published_at = _resolve_latest_source_published_at(payload)
    db.execute(
        text(
            """
            INSERT INTO rss_feed_runtime (
                feed_id,
                last_scraped_at,
                last_success_at,
                last_status,
                etag,
                last_feed_updated_at,
                last_db_article_published_at,
                consecutive_error_count,
                last_error_at,
                last_error_message,
                updated_at
            ) VALUES (
                :feed_id,
                now(),
                CASE WHEN :is_success THEN now() ELSE NULL END,
                :status,
                :etag,
                :last_feed_updated_at,
                :last_db_article_published_at,
                CASE WHEN :is_error THEN 1 ELSE 0 END,
                CASE WHEN :is_error THEN now() ELSE NULL END,
                CASE WHEN :is_error THEN :error_message ELSE NULL END,
                now()
            )
            ON CONFLICT (feed_id) DO UPDATE SET
                last_scraped_at = now(),
                last_success_at = CASE
                    WHEN :is_success THEN now()
                    ELSE rss_feed_runtime.last_success_at
                END,
                last_status = CAST(:status AS rss_feed_runtime_status_enum),
                etag = COALESCE(:etag, rss_feed_runtime.etag),
                last_feed_updated_at = COALESCE(:last_feed_updated_at, rss_feed_runtime.last_feed_updated_at),
                last_db_article_published_at = COALESCE(
                    :last_db_article_published_at,
                    rss_feed_runtime.last_db_article_published_at
                ),
                consecutive_error_count = CASE
                    WHEN :is_error THEN rss_feed_runtime.consecutive_error_count + 1
                    ELSE 0
                END,
                last_error_at = CASE
                    WHEN :is_error THEN now()
                    ELSE NULL
                END,
                last_error_message = CASE
                    WHEN :is_error THEN :error_message
                    ELSE NULL
                END,
                updated_at = now()
            """
        ),
        {
            "feed_id": payload.feed_id,
            "status": payload.status,
            "etag": payload.new_etag,
            "last_feed_updated_at": payload.new_last_update,
            "last_db_article_published_at": latest_source_published_at,
            "is_error": is_error,
            "is_success": is_success,
            "error_message": payload.error_message,
        },
    )
    if not apply_resolved_fetchprotection or payload.resolved_fetchprotection is None:
        return

    db.execute(
        text(
            """
            UPDATE rss_feeds AS feed
            SET fetchprotection_override = CASE
                WHEN company.fetchprotection IS NOT NULL
                    AND company.fetchprotection = :fetchprotection
                    THEN NULL
                ELSE :fetchprotection
            END
            FROM rss_company AS company
            WHERE company.id = feed.company_id
                AND feed.id = :feed_id
            """
        ),
        {
            "feed_id": payload.feed_id,
            "fetchprotection": payload.resolved_fetchprotection,
        },
    )
    db.execute(
        text(
            """
            UPDATE rss_feeds
            SET fetchprotection_override = :fetchprotection
            WHERE id = :feed_id
                AND company_id IS NULL
            """
        ),
        {
            "feed_id": payload.feed_id,
            "fetchprotection": payload.resolved_fetchprotection,
        },
    )


def complete_rss_scrape_task_summary(
    db: Session,
    *,
    task_id: int,
    feeds_processed: int,
    feeds_success: int,
    feeds_error: int,
) -> dict[str, int]:
    db.execute(
        text(
            """
            UPDATE rss_scrape_tasks
            SET
                status = 'completed',
                claim_expires_at = NULL,
                completed_at = now(),
                feeds_processed = :feeds_processed,
                feeds_success = :feeds_success,
                feeds_error = :feeds_error,
                updated_at = now()
            WHERE id = :task_id
            """
        ),
        {
            "task_id": task_id,
            "feeds_processed": feeds_processed,
            "feeds_success": feeds_success,
            "feeds_error": feeds_error,
        },
    )
    return {
        "feeds_processed": feeds_processed,
        "feeds_success": feeds_success,
        "feeds_error": feeds_error,
    }


def increment_rss_scrape_job_status(
    db: Session,
    *,
    job_id: str,
    tasks_processed_delta: int,
    items_processed_delta: int,
    items_success_delta: int,
    items_error_delta: int,
) -> None:
    db.execute(
        text(
            """
            UPDATE worker_jobs
            SET
                status = CAST(
                    CASE
                        WHEN tasks_processed + :tasks_processed_delta >= tasks_total THEN
                            CASE
                                WHEN items_error + :items_error_delta > 0 THEN 'completed_with_errors'
                                ELSE 'completed'
                            END
                        ELSE 'processing'
                    END
                    AS worker_job_status_enum
                ),
                tasks_processed = tasks_processed + :tasks_processed_delta,
                items_processed = items_processed + :items_processed_delta,
                items_success = items_success + :items_success_delta,
                items_error = items_error + :items_error_delta,
                started_at = COALESCE(started_at, now()),
                finished_at = CASE
                    WHEN tasks_processed + :tasks_processed_delta >= tasks_total THEN now()
                    ELSE NULL
                END,
                updated_at = now()
            WHERE id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "tasks_processed_delta": max(0, tasks_processed_delta),
            "items_processed_delta": max(0, items_processed_delta),
            "items_success_delta": max(0, items_success_delta),
            "items_error_delta": max(0, items_error_delta),
        },
    )


def refresh_rss_scrape_job_status(
    db: Session,
    *,
    job_id: str,
) -> None:
    row = db.execute(
        text(
            """
            SELECT
                COUNT(task.id) AS tasks_total,
                COUNT(task.id) FILTER (WHERE task.status IN ('completed', 'failed')) AS tasks_processed,
                COUNT(item.feed_id) AS items_total,
                COUNT(item.feed_id) FILTER (WHERE item.status <> 'pending') AS items_processed,
                COUNT(item.feed_id) FILTER (WHERE item.status IN ('success', 'not_modified')) AS items_success,
                COUNT(item.feed_id) FILTER (WHERE item.status = 'error') AS items_error,
                COUNT(task.id) FILTER (WHERE task.status = 'processing') AS processing_count,
                COUNT(task.id) FILTER (WHERE task.status = 'pending') AS pending_count,
                COUNT(task.id) FILTER (WHERE task.status = 'failed') AS failed_task_count
            FROM rss_scrape_tasks AS task
            LEFT JOIN rss_scrape_task_items AS item
                ON item.task_id = task.id
            WHERE task.job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().one_or_none()
    if row is None:
        return

    tasks_total = int(row["tasks_total"] or 0)
    tasks_processed = int(row["tasks_processed"] or 0)
    items_total = int(row["items_total"] or 0)
    items_processed = int(row["items_processed"] or 0)
    items_success = int(row["items_success"] or 0)
    items_error = int(row["items_error"] or 0)
    processing_count = int(row["processing_count"] or 0)
    pending_count = int(row["pending_count"] or 0)
    failed_task_count = int(row["failed_task_count"] or 0)

    if tasks_total == 0:
        status = "completed"
    elif processing_count > 0 or (tasks_processed > 0 and pending_count > 0):
        status = "processing"
    elif pending_count == tasks_total:
        status = "queued"
    elif items_error > 0 or failed_task_count > 0:
        status = "completed_with_errors"
    else:
        status = "completed"

    db.execute(
        text(
            """
            UPDATE worker_jobs
            SET
                status = CAST(:status AS worker_job_status_enum),
                tasks_total = :tasks_total,
                tasks_processed = :tasks_processed,
                items_total = :items_total,
                items_processed = :items_processed,
                items_success = :items_success,
                items_error = :items_error,
                started_at = CASE
                    WHEN :status <> 'queued' THEN COALESCE(started_at, now())
                    ELSE started_at
                END,
                finished_at = CASE
                    WHEN :status IN ('completed', 'completed_with_errors', 'failed') THEN now()
                    ELSE NULL
                END,
                updated_at = now()
            WHERE id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "status": status,
            "tasks_total": tasks_total,
            "tasks_processed": tasks_processed,
            "items_total": items_total,
            "items_processed": items_processed,
            "items_success": items_success,
            "items_error": items_error,
        },
    )


def _resolve_latest_source_published_at(payload: WorkerResultSchema) -> datetime | None:
    published_values = [
        source.published_at
        for source in payload.sources
        if source.published_at is not None
    ]
    if not published_values:
        return None
    return max(published_values)
