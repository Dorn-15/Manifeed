from sqlalchemy.orm import Session

import logging
from app.clients.database.rss import (
    get_company_by_id,
    get_rss_feed_read_by_id,
    set_rss_feed_enabled,
)
from app.errors.rss import (
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
)
from app.schemas.rss import RssCompanyRead, RssFeedRead

logger = logging.getLogger(__name__)

def toggle_rss_feed_enabled(db: Session, feed_id: int, enabled: bool) -> RssFeedRead:
    feed = get_rss_feed_read_by_id(db, feed_id)
    if feed is None:
        raise RssFeedNotFoundError(f"RSS feed {feed_id} not found")
    if feed.enabled == enabled:
        return feed

    company = feed.company_name
    if company is not None and feed.company_enabled is False:
        raise RssFeedToggleForbiddenError(
            f"Cannot toggle feed {feed_id}: company '{company}' is disabled"
        )
    if feed.status == "invalid":
        raise RssFeedToggleForbiddenError(
            f"Cannot toggle feed {feed_id}: status is invalid"
        )

    try:
        updated = set_rss_feed_enabled(db, feed_id=feed_id, enabled=enabled)
        if not updated:
            raise RssFeedNotFoundError(f"RSS feed {feed_id} not found")
        db.commit()
    except Exception:
        db.rollback()
        raise
    feed.enabled = enabled

    return feed


def toggle_rss_company_enabled(db: Session, company_id: int, enabled: bool) -> RssCompanyRead:
    company = get_company_by_id(db, company_id)
    if company is None:
        raise RssCompanyNotFoundError(f"RSS company {company_id} not found")

    if company.enabled != enabled:
        company.enabled = enabled
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(company)

    return RssCompanyRead(id=company.id, name=company.name, enabled=company.enabled)
