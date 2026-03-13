from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.clients.database import (
    create_rss_scrape_job,
    enqueue_rss_scrape_tasks,
    get_rss_scrape_job_status_read,
    list_rss_feed_scrape_payloads,
    list_rss_scrape_job_feed_reads,
    resolve_rss_scrape_task_batch_size,
)
from app.domain.rss import build_rss_scrape_batches
from app.errors.rss import RssJobEnqueueError
from app.schemas.rss import RssScrapeJobFeedRead, RssScrapeJobQueuedRead, RssScrapeJobStatusRead


def enqueue_rss_feed_check_job(
    db: Session,
    *,
    feed_ids: list[int] | None = None,
) -> RssScrapeJobQueuedRead:
    return _enqueue_rss_scrape_job(
        db=db,
        ingest=False,
        requested_by="rss_feeds_check_endpoint",
        feed_ids=feed_ids,
        enabled_only=True,
    )


def enqueue_rss_sources_ingest_job(
    db: Session,
    *,
    feed_ids: list[int] | None = None,
) -> RssScrapeJobQueuedRead:
    return _enqueue_rss_scrape_job(
        db=db,
        ingest=True,
        requested_by="sources_ingest_endpoint",
        feed_ids=feed_ids,
        enabled_only=True,
    )


def get_rss_scrape_job_status(
    db: Session,
    *,
    job_id: str,
) -> RssScrapeJobStatusRead:
    payload = get_rss_scrape_job_status_read(db, job_id=job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"RSS scrape job {job_id} not found")
    return payload


def list_rss_scrape_job_feeds(
    db: Session,
    *,
    job_id: str,
) -> list[RssScrapeJobFeedRead]:
    status_payload = get_rss_scrape_job_status_read(db, job_id=job_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail=f"RSS scrape job {job_id} not found")
    return list_rss_scrape_job_feed_reads(db, job_id=job_id)


def _enqueue_rss_scrape_job(
    *,
    db: Session,
    ingest: bool,
    requested_by: str,
    feed_ids: list[int] | None,
    enabled_only: bool,
) -> RssScrapeJobQueuedRead:
    feeds = list_rss_feed_scrape_payloads(
        db,
        feed_ids=feed_ids,
        enabled_only=enabled_only,
    )
    requested_at = datetime.now(timezone.utc)
    job_id = str(uuid4())
    status = "completed" if not feeds else "queued"
    feed_batches = build_rss_scrape_batches(
        feeds,
        batch_size=resolve_rss_scrape_task_batch_size(),
        random_seed=job_id,
    )
    tasks_total = len(feed_batches)

    try:
        create_rss_scrape_job(
            db,
            job_id=job_id,
            ingest=ingest,
            requested_by=requested_by,
            requested_at=requested_at,
            status=status,
            tasks_total=tasks_total,
            items_total=len(feeds),
        )
        if feeds:
            enqueue_rss_scrape_tasks(
                db,
                job_id=job_id,
                requested_at=requested_at,
                feed_batches=feed_batches,
            )
        db.commit()
    except Exception as exception:
        db.rollback()
        raise RssJobEnqueueError(f"Unable to enqueue RSS scrape job: {exception}") from exception

    return RssScrapeJobQueuedRead(
        job_id=job_id,
        job_kind=("rss_scrape_ingest" if ingest else "rss_scrape_check"),
        status=status,
        tasks_total=tasks_total,
        feeds_total=len(feeds),
    )
