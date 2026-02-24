from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.sources import RssSource, RssSourceFeed
from app.schemas.sources import RssSourceCandidateSchema


def create_rss_source(
    db: Session,
    payload: RssSourceCandidateSchema,
) -> RssSource:
    normalized_published_at = payload.published_at or datetime.now(timezone.utc)
    source = RssSource(
        title=payload.title,
        summary=payload.summary,
        author=payload.author,
        url=payload.url,
        published_at=normalized_published_at,
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

    if payload.author is not None and source.author != payload.author:
        source.author = payload.author
        has_changes = True

    if payload.published_at is not None and source.published_at != payload.published_at:
        source.published_at = payload.published_at
        for feed_link in source.feed_links:
            feed_link.published_at = payload.published_at
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
    if source.id is None:
        return False

    for feed_link in source.feed_links:
        if feed_link.feed_id == feed_id:
            return False

    source.feed_links.append(
        RssSourceFeed(
            source_id=source.id,
            feed_id=feed_id,
            published_at=source.published_at,
        )
    )
    return True
