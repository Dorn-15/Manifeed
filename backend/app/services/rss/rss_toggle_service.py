from sqlalchemy.orm import Session

from app.clients.database.rss import (
    get_company_by_id,
    get_rss_feed_by_id,
    set_rss_feed_enabled,
    set_rss_company_enabled,
)
from app.errors.rss import (
    RssCompanyNotFoundError,
    RssFeedNotFoundError,
    RssFeedToggleForbiddenError,
)
from app.schemas.rss import (
    RssCompanyEnabledToggleRead,
    RssFeedEnabledToggleRead,
)


def toggle_rss_feed_enabled(
    db: Session,
    feed_id: int,
    enabled: bool,
) -> RssFeedEnabledToggleRead:
    feed = get_rss_feed_by_id(db, feed_id)
    if feed is None:
        raise RssFeedNotFoundError(f"RSS feed {feed_id} not found")
    if feed.enabled == enabled:
        return RssFeedEnabledToggleRead(feed_id=feed.id, enabled=feed.enabled)
    if feed.company is not None and feed.company.enabled is False:
        raise RssFeedToggleForbiddenError(
            f"Cannot toggle feed {feed_id}: company '{feed.company.name}' is disabled"
        )

    try:
        updated = set_rss_feed_enabled(db, feed_id=feed_id, enabled=enabled)
        if not updated:
            raise RssFeedNotFoundError(f"RSS feed {feed_id} not found")
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RssFeedEnabledToggleRead(feed_id=feed.id, enabled=enabled)


def toggle_rss_company_enabled(
    db: Session,
    company_id: int,
    enabled: bool,
) -> RssCompanyEnabledToggleRead:
    company = get_company_by_id(db, company_id)
    if company is None:
        raise RssCompanyNotFoundError(f"RSS company {company_id} not found")
    if company.enabled == enabled:
        return RssCompanyEnabledToggleRead(company_id=company.id, enabled=company.enabled)

    try:
        updated = set_rss_company_enabled(db, company_id=company_id, enabled=enabled)
        if not updated:
            raise RssCompanyNotFoundError(f"RSS company {company_id} not found")
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RssCompanyEnabledToggleRead(company_id=company.id, enabled=enabled)
