from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.clients.database.sources import (
    get_rss_source_detail_read_by_id,
    list_rss_sources_read,
)
from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourcePageRead,
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
    return RssSourcePageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_rss_source_by_id(
    db: Session,
    *,
    source_id: int,
) -> RssSourceDetailRead | None:
    source = get_rss_source_detail_read_by_id(db, source_id=source_id)
    if source is None:
        raise HTTPException(
            status_code=404,
            detail=f"RSS source {source_id} not found",
        )
    return source
