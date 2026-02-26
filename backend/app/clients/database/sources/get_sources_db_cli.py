from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssFeed
from app.models.sources import RssSource, RssSourceFeed
from app.schemas.sources import RssSourceDetailRead, RssSourceRead

SOURCE_PUBLISHED_AT_FALLBACK = datetime(1970, 1, 1, tzinfo=timezone.utc)


def list_rss_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
) -> tuple[list[RssSourceRead], int]:
    source_ids_query = _build_source_ids_query(feed_id=feed_id, company_id=company_id)
    source_ids_subquery = source_ids_query.subquery()

    total = int(
        db.execute(
            select(func.count()).select_from(source_ids_subquery)
        ).scalar_one()
        or 0
    )
    if total == 0:
        return [], 0

    paged_source_ids = list(
        db.execute(
            select(source_ids_subquery.c.source_id)
            .order_by(
                source_ids_subquery.c.sort_published_at.desc().nullslast(),
                source_ids_subquery.c.source_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars().all()
    )
    if not paged_source_ids:
        return [], total

    sources_by_id = _load_sources_by_ids(db=db, source_ids=paged_source_ids)
    source_reads: list[RssSourceRead] = []
    for source_id in paged_source_ids:
        source = sources_by_id.get(source_id)
        if source is None:
            continue

        source_reads.append(
            RssSourceRead(
                id=source.id,
                title=source.title,
                summary=source.summary,
                author=source.author,
                url=source.url,
                published_at=_to_public_published_at(source.published_at),
                image_url=source.image_url,
                company_names=_collect_company_names(source),
            )
        )

    return source_reads, total


def list_rss_sources_by_urls(
    db: Session,
    urls: Sequence[str],
) -> dict[str, RssSource]:
    unique_urls = sorted(set(urls))
    if not unique_urls:
        return {}

    query = (
        select(RssSource)
        .options(selectinload(RssSource.feed_links))
        .where(RssSource.url.in_(unique_urls))
        .order_by(
            RssSource.url.asc(),
            RssSource.published_at.desc().nullslast(),
            RssSource.id.desc(),
        )
    )
    sources = db.execute(query).scalars().all()
    sources_by_url: dict[str, RssSource] = {}
    for source in sources:
        if source.url not in sources_by_url:
            sources_by_url[source.url] = source
    return sources_by_url


def get_rss_source_detail_read_by_id(
    db: Session,
    source_id: int,
) -> RssSourceDetailRead | None:
    query = (
        select(RssSource)
        .options(
            selectinload(RssSource.feed_links)
            .selectinload(RssSourceFeed.feed)
            .selectinload(RssFeed.company),
        )
        .where(RssSource.id == source_id)
    )
    source = db.execute(query).scalars().first()
    if source is None:
        return None

    feed_sections: set[str] = set()
    for feed_link in source.feed_links:
        feed = feed_link.feed
        if feed is None or not feed.section:
            continue
        feed_sections.add(feed.section)

    return RssSourceDetailRead(
        id=source.id,
        title=source.title,
        summary=source.summary,
        author=source.author,
        url=source.url,
        published_at=_to_public_published_at(source.published_at),
        image_url=source.image_url,
        company_names=_collect_company_names(source),
        feed_sections=sorted(feed_sections),
    )


def _build_source_ids_query(*, feed_id: int | None, company_id: int | None):
    source_id_column = RssSource.id.label("source_id")
    sort_published_at_column = func.max(RssSource.published_at).label("sort_published_at")
    query = (
        select(
            source_id_column,
            sort_published_at_column,
        )
        .select_from(RssSource)
        .join(
            RssSourceFeed,
            and_(
                RssSourceFeed.source_id == RssSource.id,
                RssSourceFeed.published_at == RssSource.published_at,
            ),
        )
        .join(RssFeed, RssFeed.id == RssSourceFeed.feed_id)
    )
    if company_id is not None:
        query = query.where(RssFeed.company_id == company_id)

    if feed_id is not None:
        query = query.where(RssSourceFeed.feed_id == feed_id)

    return query.group_by(source_id_column)


def _load_sources_by_ids(db: Session, source_ids: list[int]) -> dict[int, RssSource]:
    query = (
        select(RssSource)
        .options(
            selectinload(RssSource.feed_links)
            .selectinload(RssSourceFeed.feed)
            .selectinload(RssFeed.company),
        )
        .where(RssSource.id.in_(source_ids))
    )
    sources = db.execute(query).scalars().all()
    return {source.id: source for source in sources}


def _collect_company_names(source: RssSource) -> list[str]:
    company_names: set[str] = set()
    for feed_link in source.feed_links:
        feed = feed_link.feed
        if feed is None or feed.company is None:
            continue
        if feed.company.name:
            company_names.add(feed.company.name)
    return sorted(company_names)


def _to_public_published_at(published_at: datetime | None) -> datetime | None:
    if published_at is None:
        return None

    normalized_published_at = (
        published_at.replace(tzinfo=timezone.utc)
        if published_at.tzinfo is None
        else published_at.astimezone(timezone.utc)
    )
    if normalized_published_at == SOURCE_PUBLISHED_AT_FALLBACK:
        return None
    return normalized_published_at
