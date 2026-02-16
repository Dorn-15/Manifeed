from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.rss import RssFeed

def set_rss_feed_enabled(db: Session, feed_id: int, enabled: bool) -> bool:
    result = db.execute(
        update(RssFeed).where(RssFeed.id == feed_id).values(enabled=enabled)
    )
    return result.rowcount > 0
