from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.rss import RssScrapeJobQueuedRead
from app.services.rss.rss_scrape_job_service import enqueue_rss_sources_ingest_job


async def enqueue_sources_ingest_job(
    db: Session,
    *,
    feed_ids: list[int] | None = None,
) -> RssScrapeJobQueuedRead:
    return await enqueue_rss_sources_ingest_job(
        db,
        feed_ids=feed_ids,
    )
