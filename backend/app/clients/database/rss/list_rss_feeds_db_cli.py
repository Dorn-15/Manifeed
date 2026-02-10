from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.rss import RssFeed


def list_rss_feeds(db: Session) -> list[RssFeed]:
    query = (
        select(RssFeed)
        .options(selectinload(RssFeed.company))
        .order_by(RssFeed.id.asc())
    )
    return list(db.execute(query).scalars().all())
