from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.rss import RssCompany, RssFeed, RssFeedRuntime, RssTag
from app.schemas.rss import RssFeedUpsertSchema


def upsert_feed(
    db: Session,
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
            section=payload.section,
            enabled=payload.enabled,
            trust_score=payload.trust_score,
            fetchprotection_override=(
                _normalize_fetchprotection(payload.fetchprotection)
                if payload.fetchprotection is not None
                else None
            ),
            runtime=RssFeedRuntime(),
            tags=list(tags),
        )
        db.add(new_feed)
        db.flush()
        return new_feed, True

    existing_feed.section = payload.section
    existing_feed.enabled = payload.enabled
    existing_feed.trust_score = payload.trust_score
    if payload.fetchprotection is not None:
        existing_feed.fetchprotection_override = _normalize_fetchprotection(payload.fetchprotection)
    _get_or_create_feed_runtime(existing_feed)
    existing_feed.tags = list(tags)
    return existing_feed, False


def link_company_to_feed(
    db: Session,
    *,
    company_id: int,
    feed_id: int,
) -> bool:
    feed = db.execute(
        select(RssFeed).where(RssFeed.id == feed_id)
    ).scalar_one_or_none()
    if feed is None:
        return False

    if feed.company_id == company_id:
        return False

    feed.company_id = company_id
    return True


def set_rss_feed_enabled(db: Session, feed_id: int, enabled: bool) -> bool:
    result = db.execute(
        update(RssFeed).where(RssFeed.id == feed_id).values(enabled=enabled)
    )
    return result.rowcount > 0


def set_rss_company_enabled(db: Session, company_id: int, enabled: bool) -> bool:
    result = db.execute(
        update(RssCompany).where(RssCompany.id == company_id).values(enabled=enabled)
    )
    return result.rowcount > 0


def delete_company_feeds_not_in_urls(
    db: Session,
    company_id: int,
    expected_urls: set[str],
) -> int:
    linked_feed_ids_query = (
        select(RssFeed.id)
        .where(RssFeed.company_id == company_id)
    )
    if expected_urls:
        linked_feed_ids_query = linked_feed_ids_query.where(~RssFeed.url.in_(expected_urls))

    linked_feed_ids = list(db.execute(linked_feed_ids_query).scalars().all())
    if not linked_feed_ids:
        return 0

    db.execute(delete(RssFeed).where(RssFeed.id.in_(linked_feed_ids)))

    return len(linked_feed_ids)


def _normalize_fetchprotection(fetchprotection: int | None) -> int:
    if isinstance(fetchprotection, int) and 0 <= fetchprotection <= 2:
        return fetchprotection
    return 1


def _get_or_create_feed_runtime(feed: RssFeed) -> RssFeedRuntime:
    runtime = feed.runtime
    if runtime is not None:
        return runtime

    runtime = RssFeedRuntime()
    feed.runtime = runtime
    return runtime
