from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssCompany, RssFeed
from app.models.sources import RssSource, RssSourceFeed
from app.schemas.sources import RssSourceDetailRead, RssSourceRead


def list_rss_sources_read(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
) -> tuple[list[RssSourceRead], int]:
    data_query = _apply_source_filters(
        _source_summary_select(),
        feed_id=feed_id,
        company_id=company_id,
    ).group_by(
        RssSource.id,
        RssSource.title,
        RssSource.summary,
        RssSource.url,
        RssSource.published_at,
        RssSource.image_url,
    )
    data_query = data_query.order_by(
        RssSource.published_at.desc().nullslast(),
        RssSource.id.desc(),
    ).limit(limit).offset(offset)

    rows = db.execute(data_query).mappings().all()
    source_reads = [RssSourceRead(**row) for row in rows]

    total_query = _apply_source_filters(
        select(func.count(func.distinct(RssSource.id))).select_from(RssSource).join(
            RssSourceFeed,
            RssSourceFeed.source_id == RssSource.id,
        ).join(
            RssFeed,
            RssFeed.id == RssSourceFeed.feed_id,
        ).outerjoin(
            RssCompany,
            RssCompany.id == RssFeed.company_id,
        ),
        feed_id=feed_id,
        company_id=company_id,
    )
    total = int(db.execute(total_query).scalar_one() or 0)
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
    )
    sources = db.execute(query).scalars().all()
    return {source.url: source for source in sources}


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
    source = db.execute(query).scalar_one_or_none()
    if source is None:
        return None

    company_names: set[str] = set()
    feed_sections: set[str] = set()
    for feed_link in source.feed_links:
        feed = feed_link.feed
        if feed is None:
            continue
        if feed.company is not None and feed.company.name:
            company_names.add(feed.company.name)
        if feed.section:
            feed_sections.add(feed.section)

    company_name = sorted(company_names)[0] if company_names else None
    return RssSourceDetailRead(
        id=source.id,
        title=source.title,
        summary=source.summary,
        url=source.url,
        published_at=source.published_at,
        image_url=source.image_url,
        company_name=company_name,
        feed_sections=sorted(feed_sections),
    )


def _source_summary_select():
    return (
        select(
            RssSource.id.label("id"),
            RssSource.title.label("title"),
            RssSource.summary.label("summary"),
            RssSource.url.label("url"),
            RssSource.published_at.label("published_at"),
            RssSource.image_url.label("image_url"),
            func.min(RssCompany.name).label("company_name"),
        )
        .select_from(RssSource)
        .join(RssSourceFeed, RssSourceFeed.source_id == RssSource.id)
        .join(RssFeed, RssFeed.id == RssSourceFeed.feed_id)
        .outerjoin(RssCompany, RssCompany.id == RssFeed.company_id)
    )


def _apply_source_filters(
    query,
    *,
    feed_id: int | None,
    company_id: int | None,
):
    if feed_id is not None:
        query = query.where(RssSourceFeed.feed_id == feed_id)

    if company_id is not None:
        query = query.where(RssFeed.company_id == company_id)

    return query
