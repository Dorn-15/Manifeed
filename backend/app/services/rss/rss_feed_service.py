from sqlalchemy.orm import Session

from app.clients.database.rss import list_rss_feeds_read
from app.schemas.rss import RssFeedRead


def get_rss_feeds(db: Session) -> list[RssFeedRead]:
    return list_rss_feeds_read(db)
