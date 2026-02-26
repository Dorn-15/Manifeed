from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import (
    RssFeed,
    RssScrapeJob,
    RssScrapeJobFeed,
    RssScrapeJobResult,
)
from app.models.sources import RssSourceFeed
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
    latest_source_subquery = (
        select(
            RssSourceFeed.feed_id.label("feed_id"),
            func.max(RssSourceFeed.published_at).label("last_db_article_published_at"),
        )
        .group_by(RssSourceFeed.feed_id)
        .subquery()
    )

    query = (
        select(
            RssFeed,
            latest_source_subquery.c.last_db_article_published_at,
        )
        .options(
            selectinload(RssFeed.company),
            selectinload(RssFeed.scraping),
        )
        .outerjoin(
            latest_source_subquery,
            latest_source_subquery.c.feed_id == RssFeed.id,
        )
        .order_by(RssFeed.id.asc())
    )

    if enabled_only:
        query = query.where(RssFeed.enabled.is_(True))

    if feed_ids:
        unique_feed_ids = sorted({feed_id for feed_id in feed_ids if isinstance(feed_id, int) and feed_id > 0})
        if not unique_feed_ids:
            return []
        query = query.where(RssFeed.id.in_(unique_feed_ids))

    payloads: list[RssScrapeFeedPayloadSchema] = []
    for feed, last_db_article_published_at in db.execute(query).all():
        scraping = getattr(feed, "scraping", None)
        company = getattr(feed, "company", None)
        payloads.append(
            RssScrapeFeedPayloadSchema(
                feed_id=feed.id,
                feed_url=feed.url,
                company_id=getattr(feed, "company_id", None),
                host_header=normalize_host(getattr(company, "host", None)),
                fetchprotection=_resolve_feed_fetchprotection(feed),
                etag=getattr(scraping, "etag", None),
                last_update=getattr(scraping, "last_update", None),
                last_db_article_published_at=_normalize_datetime(last_db_article_published_at),
            )
        )
    return payloads


def create_rss_scrape_job(
    db: Session,
    *,
    job_id: str,
    ingest: bool,
    requested_by: str,
    requested_at: datetime,
    status: str,
    feeds: list[RssScrapeFeedPayloadSchema],
) -> RssScrapeJob:
    job = RssScrapeJob(
        job_id=job_id,
        ingest=ingest,
        requested_by=requested_by,
        requested_at=_normalize_datetime(requested_at) or datetime.now(timezone.utc),
        feed_count=len(feeds),
        status=status,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)

    for feed in feeds:
        db.add(
            RssScrapeJobFeed(
                job_id=job_id,
                feed_id=feed.feed_id,
                feed_url=feed.feed_url,
                last_db_article_published_at=feed.last_db_article_published_at,
            )
        )

    return job


def set_rss_scrape_job_status(
    db: Session,
    *,
    job_id: str,
    status: str,
) -> bool:
    job = db.get(RssScrapeJob, job_id)
    if job is None:
        return False

    job.status = status
    job.updated_at = datetime.now(timezone.utc)
    return True


def get_rss_scrape_job_status_read(
    db: Session,
    *,
    job_id: str,
) -> RssScrapeJobStatusRead | None:
    job = db.get(RssScrapeJob, job_id)
    if job is None:
        return None

    result_counts = db.execute(
        select(
            func.count(RssScrapeJobResult.feed_id),
            func.count().filter(RssScrapeJobResult.status == "success"),
            func.count().filter(RssScrapeJobResult.status == "not_modified"),
            func.count().filter(RssScrapeJobResult.status == "error"),
        )
        .where(RssScrapeJobResult.job_id == job_id)
    ).one()

    feeds_processed = int(result_counts[0] or 0)
    feeds_success = int(result_counts[1] or 0)
    feeds_not_modified = int(result_counts[2] or 0)
    feeds_error = int(result_counts[3] or 0)

    return RssScrapeJobStatusRead(
        job_id=job.job_id,
        ingest=job.ingest,
        requested_by=job.requested_by,
        requested_at=job.requested_at,
        status=job.status,  # type: ignore[arg-type]
        feeds_total=job.feed_count,
        feeds_processed=feeds_processed,
        feeds_success=feeds_success,
        feeds_not_modified=feeds_not_modified,
        feeds_error=feeds_error,
    )


def list_rss_scrape_job_feed_reads(
    db: Session,
    *,
    job_id: str,
) -> list[RssScrapeJobFeedRead]:
    rows = db.execute(
        select(
            RssScrapeJobFeed.feed_id,
            RssScrapeJobFeed.feed_url,
            RssScrapeJobResult.status,
            RssScrapeJobResult.error_message,
            RssScrapeJobResult.fetchprotection,
            RssScrapeJobResult.new_etag,
            RssScrapeJobResult.new_last_update,
        )
        .outerjoin(
            RssScrapeJobResult,
            (RssScrapeJobResult.job_id == RssScrapeJobFeed.job_id)
            & (RssScrapeJobResult.feed_id == RssScrapeJobFeed.feed_id),
        )
        .where(RssScrapeJobFeed.job_id == job_id)
        .order_by(RssScrapeJobFeed.feed_id.asc())
    ).all()

    return [
        RssScrapeJobFeedRead(
            feed_id=row.feed_id,
            feed_url=row.feed_url,
            status=row.status or "pending",
            error_message=row.error_message,
            fetchprotection=row.fetchprotection,
            new_etag=row.new_etag,
            new_last_update=row.new_last_update,
        )
        for row in rows
    ]


def _resolve_feed_fetchprotection(feed: RssFeed) -> int:
    scraping = getattr(feed, "scraping", None)
    scraping_fetchprotection = getattr(scraping, "fetchprotection", None)
    if isinstance(scraping_fetchprotection, int) and 0 <= scraping_fetchprotection <= 2:
        return scraping_fetchprotection

    company = getattr(feed, "company", None)
    company_fetchprotection = getattr(company, "fetchprotection", None)
    if isinstance(company_fetchprotection, int) and 0 <= company_fetchprotection <= 2:
        return company_fetchprotection

    return 1


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
