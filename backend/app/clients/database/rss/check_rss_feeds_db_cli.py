from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rss import RssFeed


def list_rss_feeds_for_check(
    db: Session,
    feed_ids: Sequence[int] | None = None,
) -> list[RssFeed]:
    query = select(RssFeed).order_by(RssFeed.id.asc())
    if feed_ids:
        unique_feed_ids = sorted(set(feed_ids))
        query = query.where(RssFeed.id.in_(unique_feed_ids))
    return list(db.execute(query).scalars().all())
