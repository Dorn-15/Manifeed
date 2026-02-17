from sqlalchemy.orm import Session

from app.clients.database.sources import (
    get_rss_source_detail_read_by_id,
    list_rss_sources_read,
)
from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourcePageRead,
    RssSourceRead,
)


def get_rss_sources(
    db: Session,
    *,
    limit: int,
    offset: int,
    feed_id: int | None = None,
    company_id: int | None = None,
) -> RssSourcePageRead:
    items, total = list_rss_sources_read(
        db,
        limit=limit,
        offset=offset,
        feed_id=feed_id,
        company_id=company_id,
    )
    return _build_page_read(items=items, total=total, limit=limit, offset=offset)


def get_rss_source_by_id(
    db: Session,
    *,
    source_id: int,
) -> RssSourceDetailRead | None:
    return get_rss_source_detail_read_by_id(db, source_id=source_id)


def _build_page_read(
    *,
    items: list[RssSourceRead],
    total: int,
    limit: int,
    offset: int,
) -> RssSourcePageRead:
    return RssSourcePageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
