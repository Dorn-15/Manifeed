from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas.rss import (
    RssCompanyRead,
    RssEnabledTogglePayload,
    RssFeedRead,
    RssSyncRead,
)
from app.services.rss import (
    get_rss_feeds,
    get_rss_icon_file_path,
    sync_rss_catalog,
    toggle_rss_company_enabled,
    toggle_rss_feed_enabled,
)
from database import get_db_session

rss_router = APIRouter(prefix="/rss", tags=["rss"])


@rss_router.get("/", response_model=list[RssFeedRead])
def read_rss_feeds(db: Session = Depends(get_db_session)) -> list[RssFeedRead]:
    return get_rss_feeds(db)


@rss_router.patch("/feeds/{feed_id}/enabled", response_model=RssFeedRead)
def update_rss_feed_enabled(
    feed_id: int,
    payload: RssEnabledTogglePayload,
    db: Session = Depends(get_db_session),
) -> RssFeedRead:
    return toggle_rss_feed_enabled(
        db,
        feed_id=feed_id,
        enabled=payload.enabled,
    )


@rss_router.patch("/companies/{company_id}/enabled", response_model=RssCompanyRead)
def update_rss_company_enabled(
    company_id: int,
    payload: RssEnabledTogglePayload,
    db: Session = Depends(get_db_session),
) -> RssCompanyRead:
    return toggle_rss_company_enabled(
        db,
        company_id=company_id,
        enabled=payload.enabled,
    )


@rss_router.post("/sync", response_model=RssSyncRead)
def sync_rss_feeds(db: Session = Depends(get_db_session)) -> RssSyncRead:
    return sync_rss_catalog(db)


@rss_router.get("/img/{icon_url:path}")
def read_rss_icon(icon_url: str) -> FileResponse:
    icon_file_path = get_rss_icon_file_path(icon_url)
    return FileResponse(
        path=icon_file_path,
        media_type="image/svg+xml",
        filename=icon_file_path.name,
    )
