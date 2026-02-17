from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.sources import RssSource, RssSourceFeed
from app.schemas.sources import RssSourceCandidateSchema


def create_rss_source(
    db: Session,
    payload: RssSourceCandidateSchema,
) -> RssSource:
    source = RssSource(
        title=payload.title,
        summary=payload.summary,
        url=payload.url,
        published_at=payload.published_at,
        language=payload.language,
        image_url=payload.image_url,
    )
    db.add(source)
    return source


def update_rss_source(
    source: RssSource,
    payload: RssSourceCandidateSchema,
) -> bool:
    has_changes = False

    if source.title != payload.title:
        source.title = payload.title
        has_changes = True

    if payload.summary is not None and source.summary != payload.summary:
        source.summary = payload.summary
        has_changes = True

    if payload.published_at is not None and source.published_at != payload.published_at:
        source.published_at = payload.published_at
        has_changes = True

    if payload.language is not None and source.language != payload.language:
        source.language = payload.language
        has_changes = True

    if payload.image_url is not None and source.image_url != payload.image_url:
        source.image_url = payload.image_url
        has_changes = True

    return has_changes


def link_source_to_feed(
    source: RssSource,
    feed_id: int,
) -> bool:
    if feed_id <= 0:
        return False

    for feed_link in source.feed_links:
        if feed_link.feed_id == feed_id:
            return False

    source.feed_links.append(RssSourceFeed(feed_id=feed_id))
    return True
