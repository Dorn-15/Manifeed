from __future__ import annotations

from sqlalchemy.orm import Session

from app.clients.database import (
    insert_job_result_if_new,
    refresh_rss_scrape_job_status,
    upsert_feed_scraping_state,
    upsert_sources_for_feed,
)
from app.schemas import WorkerResultSchema


def persist_worker_result(
    db: Session,
    *,
    payload: WorkerResultSchema,
    queue_kind: str,
) -> bool:
    is_new = insert_job_result_if_new(
        db,
        payload=payload,
        queue_kind=queue_kind,
    )
    if not is_new:
        return False

    upsert_feed_scraping_state(db, payload=payload)

    if queue_kind == "ingest":
        upsert_sources_for_feed(db, payload=payload)

    refresh_rss_scrape_job_status(db, job_id=payload.job_id)
    return True
