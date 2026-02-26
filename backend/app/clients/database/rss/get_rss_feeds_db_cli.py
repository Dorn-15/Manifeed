from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssCompany, RssFeed, RssFeedScraping
from app.schemas.rss import RssCompanyRead, RssFeedRead


def list_rss_feeds(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .options(
            selectinload(RssFeed.company),
            selectinload(RssFeed.scraping),
        )
        .order_by(RssFeed.id.asc())
    )
    if feed_ids:
        unique_feed_ids = sorted(set(feed_ids))
        query = query.where(RssFeed.id.in_(unique_feed_ids))
    return list(db.execute(query).scalars().all())


def list_rss_feeds_read(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeedRead]:
    feeds = list_rss_feeds(db=db, feed_ids=feed_ids)
    return [_to_rss_feed_read(feed) for feed in feeds]


def list_rss_feeds_by_urls(
    db: Session,
    urls: Sequence[str],
) -> dict[str, RssFeed]:
    unique_urls = sorted(set(urls))
    if not unique_urls:
        return {}

    feeds = db.execute(
        select(RssFeed)
        .options(selectinload(RssFeed.scraping))
        .where(RssFeed.url.in_(unique_urls))
    ).scalars().all()
    return {feed.url: feed for feed in feeds}


def list_enabled_rss_feeds(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .options(
            selectinload(RssFeed.company),
            selectinload(RssFeed.scraping),
        )
        .outerjoin(
            RssFeedScraping,
            RssFeedScraping.feed_id == RssFeed.id,
        )
        .where(RssFeed.enabled.is_(True))
        .where(sa.func.coalesce(RssFeedScraping.fetchprotection, 1) != 0)
        .order_by(RssFeed.id.asc())
    )
    if feed_ids:
        unique_feed_ids = sorted(
            {
                feed_id
                for feed_id in feed_ids
                if isinstance(feed_id, int) and feed_id > 0
            }
        )
        if not unique_feed_ids:
            return []
        query = query.where(RssFeed.id.in_(unique_feed_ids))
    return list(db.execute(query).scalars().all())


def get_rss_feed_by_id(db: Session, feed_id: int) -> RssFeed | None:
    query = (
        select(RssFeed)
        .options(
            selectinload(RssFeed.company),
            selectinload(RssFeed.scraping),
        )
        .where(RssFeed.id == feed_id)
    )
    return db.execute(query).scalar_one_or_none()


def _to_rss_feed_read(feed: RssFeed) -> RssFeedRead:
    return RssFeedRead(
        id=feed.id,
        url=feed.url,
        section=feed.section,
        enabled=feed.enabled,
        trust_score=feed.trust_score,
        fetchprotection=_resolve_feed_fetchprotection(feed),
        company=_to_company_read(feed.company) if feed.company is not None else None,
    )


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


def _to_company_read(company: RssCompany) -> RssCompanyRead:
    return RssCompanyRead(
        id=company.id,
        name=company.name,
        host=company.host,
        icon_url=company.icon_url,
        country=company.country,
        language=company.language,
        fetchprotection=company.fetchprotection,
        enabled=company.enabled,
    )
