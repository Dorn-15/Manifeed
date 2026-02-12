from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssFeed, RssCompany
from app.schemas.rss import RssFeedRead


def list_rss_feeds(db: Session) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .options(selectinload(RssFeed.company))
        .order_by(RssFeed.id.asc())
    )
    return list(db.execute(query).scalars().all())


def list_rss_feeds_read(db: Session) -> list[RssFeedRead]:
    query = (
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
        .order_by(RssFeed.id.asc())
    )
    rows = db.execute(query).mappings().all()
    return [RssFeedRead(**row) for row in rows]


def get_rss_feed_by_id(db: Session, feed_id: int) -> RssFeed | None:
    query = (
        select(RssFeed)
        .options(selectinload(RssFeed.company))
        .where(RssFeed.id == feed_id)
    )
    return db.execute(query).scalar_one_or_none()


def get_rss_feed_read_by_id(db: Session, feed_id: int) -> RssFeedRead | None:
    query = (
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
        .where(RssFeed.id == feed_id)
    )
    row = db.execute(query).mappings().one_or_none()
    return RssFeedRead(**row) if row else None


def set_rss_feed_enabled(db: Session, feed_id: int, enabled: bool) -> bool:
    result = db.execute(
        update(RssFeed).where(RssFeed.id == feed_id).values(enabled=enabled)
    )
    return result.rowcount > 0


def get_rss_company_by_id(db: Session, company_id: int) -> RssCompany | None:
    return db.execute(
        select(RssCompany).where(RssCompany.id == company_id)
    ).scalar_one_or_none()
