from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssFeed, RssCompany
from app.schemas.rss import RssFeedRead


def list_rss_feeds(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .options(selectinload(RssFeed.company))
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
    query = _rss_feed_read_select().order_by(RssFeed.id.asc())
    if feed_ids:
        unique_feed_ids = sorted(set(feed_ids))
        query = query.where(RssFeed.id.in_(unique_feed_ids))
    rows = db.execute(query).mappings().all()
    return [RssFeedRead(**row) for row in rows]


def list_rss_feeds_by_urls(
    db: Session,
    urls: Sequence[str],
) -> dict[str, RssFeed]:
    unique_urls = sorted(set(urls))
    if not unique_urls:
        return {}

    feeds = db.execute(
        select(RssFeed).where(RssFeed.url.in_(unique_urls))
    ).scalars().all()
    return {feed.url: feed for feed in feeds}


def list_enabled_rss_feeds(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .where(RssFeed.enabled.is_(True))
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
        .options(selectinload(RssFeed.company))
        .where(RssFeed.id == feed_id)
    )
    return db.execute(query).scalar_one_or_none()


def get_rss_feed_read_by_id(db: Session, feed_id: int) -> RssFeedRead | None:
    query = _rss_feed_read_select().where(RssFeed.id == feed_id)
    row = db.execute(query).mappings().one_or_none()
    return RssFeedRead(**row) if row else None


def _rss_feed_read_select():
    return (
        select(
            RssFeed.id.label("id"),
            RssFeed.url.label("url"),
            RssCompany.id.label("company_id"),
            RssCompany.name.label("company_name"),
            RssCompany.enabled.label("company_enabled"),
            RssFeed.section.label("section"),
            RssFeed.enabled.label("enabled"),
            RssFeed.status.label("status"),
            RssFeed.trust_score.label("trust_score"),
            RssFeed.language.label("language"),
            RssFeed.icon_url.label("icon_url"),
        )
        .select_from(RssFeed)
        .outerjoin(RssCompany, RssFeed.company_id == RssCompany.id)
    )