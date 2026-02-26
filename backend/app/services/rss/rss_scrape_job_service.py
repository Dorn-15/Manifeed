from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterator
from datetime import datetime, timezone
import os
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.clients.database.rss import (
    create_rss_scrape_job,
    get_rss_scrape_job_status_read,
    list_rss_feed_scrape_payloads,
    list_rss_scrape_job_feed_reads,
    set_rss_scrape_job_status,
)
from app.clients.queue import publish_rss_scrape_job
from app.errors.rss import RssJobQueuePublishError
from app.schemas.rss import (
    RssScrapeFeedPayloadSchema,
    RssScrapeJobFeedRead,
    RssScrapeJobQueuedRead,
    RssScrapeJobRequestSchema,
    RssScrapeJobStatusRead,
)

DEFAULT_QUEUE_BATCH_SIZE = 50


async def enqueue_rss_feed_check_job(
    db: Session,
    *,
    feed_ids: list[int] | None = None,
) -> RssScrapeJobQueuedRead:
    return await _enqueue_rss_scrape_job(
        db=db,
        ingest=False,
        requested_by="rss_feeds_check_endpoint",
        feed_ids=feed_ids,
        enabled_only=False,
    )


async def enqueue_rss_sources_ingest_job(
    db: Session,
    *,
    feed_ids: list[int] | None = None,
) -> RssScrapeJobQueuedRead:
    return await _enqueue_rss_scrape_job(
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
    status_payload = get_rss_scrape_job_status_read(db, job_id=job_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail=f"RSS scrape job {job_id} not found")
    return status_payload


def list_rss_scrape_job_feeds(
    db: Session,
    *,
    job_id: str,
) -> list[RssScrapeJobFeedRead]:
    status_payload = get_rss_scrape_job_status_read(db, job_id=job_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail=f"RSS scrape job {job_id} not found")
    return list_rss_scrape_job_feed_reads(db, job_id=job_id)


async def _enqueue_rss_scrape_job(
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
    initial_status = "queued" if feeds else "completed"

    create_rss_scrape_job(
        db,
        job_id=job_id,
        ingest=ingest,
        requested_by=requested_by,
        requested_at=requested_at,
        status=initial_status,
        feeds=feeds,
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    if feeds:
        mixed_feeds = _mix_feeds_by_company(feeds)
        queue_batch_size = _resolve_queue_batch_size()
        try:
            for feed_batch in _iter_feed_batches(mixed_feeds, batch_size=queue_batch_size):
                payload = RssScrapeJobRequestSchema(
                    job_id=job_id,
                    requested_at=requested_at,
                    ingest=ingest,
                    requested_by=requested_by,
                    feeds=feed_batch,
                ).model_dump(mode="json")
                await publish_rss_scrape_job(payload)
        except Exception as exception:
            _mark_job_as_failed_after_publish_error(db, job_id=job_id)
            raise RssJobQueuePublishError("Unable to publish RSS scrape job") from exception

    return RssScrapeJobQueuedRead(job_id=job_id, status=initial_status)


def _mark_job_as_failed_after_publish_error(db: Session, *, job_id: str) -> None:
    try:
        if set_rss_scrape_job_status(db, job_id=job_id, status="failed"):
            db.commit()
    except Exception:
        db.rollback()


def _iter_feed_batches(
    feeds: list[RssScrapeFeedPayloadSchema],
    *,
    batch_size: int,
) -> Iterator[list[RssScrapeFeedPayloadSchema]]:
    batch: list[RssScrapeFeedPayloadSchema] = []
    for feed in feeds:
        batch.append(feed)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _mix_feeds_by_company(
    feeds: list[RssScrapeFeedPayloadSchema],
) -> list[RssScrapeFeedPayloadSchema]:
    if len(feeds) <= 1:
        return feeds

    feeds_by_company: dict[str, deque[RssScrapeFeedPayloadSchema]] = defaultdict(deque)
    company_order: list[str] = []
    for feed in feeds:
        company_key = _resolve_company_key(feed)
        if company_key not in feeds_by_company:
            company_order.append(company_key)
        feeds_by_company[company_key].append(feed)

    mixed_feeds: list[RssScrapeFeedPayloadSchema] = []
    has_pending = True
    while has_pending:
        has_pending = False
        for company_key in company_order:
            company_feeds = feeds_by_company[company_key]
            if not company_feeds:
                continue
            mixed_feeds.append(company_feeds.popleft())
            has_pending = True
    return mixed_feeds


def _resolve_company_key(feed: RssScrapeFeedPayloadSchema) -> str:
    if isinstance(feed.company_id, int) and feed.company_id > 0:
        return f"company:{feed.company_id}"
    return f"feed:{feed.feed_id}"


def _resolve_queue_batch_size() -> int:
    raw_value = os.getenv("RSS_SCRAPE_QUEUE_BATCH_SIZE", str(DEFAULT_QUEUE_BATCH_SIZE))
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_QUEUE_BATCH_SIZE
    if parsed <= 0:
        return DEFAULT_QUEUE_BATCH_SIZE
    return parsed
