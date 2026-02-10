from sqlalchemy.orm import Session

from app.clients.database.rss import list_rss_feeds
from app.schemas.rss import RssFeedRead


def get_rss_feeds(db: Session) -> list[RssFeedRead]:
    feeds = list_rss_feeds(db)
    return [
        RssFeedRead(
            id=feed.id,
            url=feed.url,
            company_name=feed.company.name if feed.company is not None else None,
            section=feed.section,
            enabled=feed.enabled,
            status=feed.status,
            trust_score=feed.trust_score,
            language=feed.language,
            icon_url=feed.icon_url,
        )
        for feed in feeds
    ]
