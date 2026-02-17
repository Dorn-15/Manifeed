from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.rss import RssCompany, RssFeed, RssTag
from app.schemas.rss import RssFeedUpsertSchema


def upsert_feed(
    db: Session,
    company: RssCompany,
    payload: RssFeedUpsertSchema,
    tags: Sequence[RssTag],
    existing_feed: RssFeed | None = None,
) -> tuple[RssFeed, bool]:
    if existing_feed is None:
        existing_feed = db.execute(
            select(RssFeed).where(RssFeed.url == payload.url)
        ).scalar_one_or_none()

    if existing_feed is None:
        new_feed = RssFeed(
            url=payload.url,
            company=company,
            section=payload.section,
            enabled=payload.enabled,
            status="unchecked",
            trust_score=payload.trust_score,
            language=payload.language,
            icon_url=payload.icon_url,
            parsing_config=payload.parsing_config,
            tags=list(tags),
        )
        db.add(new_feed)
        db.flush()
        return new_feed, True

    existing_feed.company = company
    existing_feed.section = payload.section
    if existing_feed.status != "invalid":
        existing_feed.enabled = payload.enabled
    existing_feed.trust_score = payload.trust_score
    existing_feed.language = payload.language
    existing_feed.icon_url = payload.icon_url
    existing_feed.parsing_config = payload.parsing_config
    existing_feed.tags = list(tags)
    return existing_feed, False

def set_rss_feed_enabled(db: Session, feed_id: int, enabled: bool) -> bool:
    result = db.execute(
        update(RssFeed).where(RssFeed.id == feed_id).values(enabled=enabled)
    )
    return result.rowcount > 0

def delete_company_feeds_not_in_urls(
    db: Session,
    company_id: int,
    expected_urls: set[str],
) -> int:
    delete_query = (
        delete(RssFeed)
        .where(RssFeed.company_id == company_id)
        .execution_options(synchronize_session=False)
    )
    if expected_urls:
        delete_query = delete_query.where(~RssFeed.url.in_(expected_urls))

    result = db.execute(delete_query)
    rowcount = result.rowcount if result.rowcount is not None else 0
    return max(rowcount, 0)
