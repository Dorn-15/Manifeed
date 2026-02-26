from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas import WorkerResultSchema


def insert_job_result_if_new(
    db: Session,
    *,
    payload: WorkerResultSchema,
    queue_kind: str,
) -> bool:
    inserted = db.execute(
        text(
            """
            INSERT INTO rss_scrape_job_results (
                job_id,
                feed_id,
                status,
                queue_kind,
                error_message,
                fetchprotection,
                new_etag,
                new_last_update
            )
            SELECT
                :job_id,
                :feed_id,
                :status,
                :queue_kind,
                :error_message,
                :fetchprotection,
                :new_etag,
                :new_last_update
            WHERE EXISTS (
                SELECT 1
                FROM rss_scrape_jobs
                WHERE job_id = :job_id
            )
            ON CONFLICT (job_id, feed_id) DO NOTHING
            RETURNING job_id
            """
        ),
        {
            "job_id": payload.job_id,
            "feed_id": payload.feed_id,
            "status": payload.status,
            "queue_kind": queue_kind,
            "error_message": payload.error_message,
            "fetchprotection": payload.fetchprotection,
            "new_etag": payload.new_etag,
            "new_last_update": payload.new_last_update,
        },
    ).scalar_one_or_none()
    return inserted is not None


def upsert_feed_scraping_state(
    db: Session,
    *,
    payload: WorkerResultSchema,
) -> None:
    is_error = payload.status == "error"
    db.execute(
        text(
            """
            INSERT INTO feeds_scraping (
                feed_id,
                fetchprotection,
                last_update,
                etag,
                error_nbr,
                error_msg
            ) VALUES (
                :feed_id,
                :fetchprotection,
                :last_update,
                :etag,
                :error_nbr,
                :error_msg
            )
            ON CONFLICT (feed_id) DO UPDATE SET
                fetchprotection = EXCLUDED.fetchprotection,
                last_update = COALESCE(EXCLUDED.last_update, feeds_scraping.last_update),
                etag = COALESCE(EXCLUDED.etag, feeds_scraping.etag),
                error_nbr = CASE
                    WHEN :is_error THEN feeds_scraping.error_nbr + 1
                    ELSE feeds_scraping.error_nbr
                END,
                error_msg = CASE
                    WHEN :is_error THEN :error_msg
                    ELSE NULL
                END
            """
        ),
        {
            "feed_id": payload.feed_id,
            "fetchprotection": payload.fetchprotection,
            "last_update": payload.new_last_update,
            "etag": payload.new_etag,
            "error_nbr": 1 if is_error else 0,
            "error_msg": payload.error_message if is_error else None,
            "is_error": is_error,
        },
    )


def refresh_rss_scrape_job_status(
    db: Session,
    *,
    job_id: str,
) -> None:
    job_row = db.execute(
        text(
            """
            SELECT feed_count
            FROM rss_scrape_jobs
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().first()
    if job_row is None:
        return

    feed_count = int(job_row["feed_count"] or 0)
    result_counts = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS processed_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count
            FROM rss_scrape_job_results
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().first()
    processed_count = int((result_counts or {}).get("processed_count") or 0)
    error_count = int((result_counts or {}).get("error_count") or 0)

    if feed_count == 0:
        status = "completed"
    elif processed_count == 0:
        status = "queued"
    elif processed_count < feed_count:
        status = "processing"
    elif error_count > 0:
        status = "completed_with_errors"
    else:
        status = "completed"

    db.execute(
        text(
            """
            UPDATE rss_scrape_jobs
            SET status = :status, updated_at = now()
            WHERE job_id = :job_id
            """
        ),
        {
            "job_id": job_id,
            "status": status,
        },
    )
