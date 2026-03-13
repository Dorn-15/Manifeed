from sqlalchemy.orm import Session

from app.clients.database import list_rss_feeds_read
from app.schemas.rss import RssFeedRead


def get_rss_feeds_read(db: Session) -> list[RssFeedRead]:
    return list_rss_feeds_read(db)
