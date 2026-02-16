from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.errors.rss import RssJobAlreadyRunningError, RssRepositorySyncError
from app.schemas.rss import (
    RssCompanyRead,
    RssEnabledTogglePayload,
    RssFeedCheckRead,
    RssFeedRead,
    RssSyncRead,
)
from app.services.rss import (
    check_rss_feeds,
    get_rss_feeds,
    get_rss_icon_file_path,
    sync_rss_catalog,
    toggle_rss_company_enabled,
    toggle_rss_feed_enabled,
)
from app.utils import JobAlreadyRunning, job_lock, GitRepositorySyncError
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
    try:
        with job_lock(db, "rss_patch_feed_enabled"):
            return toggle_rss_feed_enabled(
                db,
                feed_id=feed_id,
                enabled=payload.enabled,
            )
    except JobAlreadyRunning as exception:
        raise RssJobAlreadyRunningError("RSS feed toggle already running") from exception


@rss_router.patch("/companies/{company_id}/enabled", response_model=RssCompanyRead)
def update_rss_company_enabled(
    company_id: int,
    payload: RssEnabledTogglePayload,
    db: Session = Depends(get_db_session),
) -> RssCompanyRead:
    try:
        with job_lock(db, "rss_patch_company_enabled"):
            return toggle_rss_company_enabled(
                db,
                company_id=company_id,
                enabled=payload.enabled,
            )
    except JobAlreadyRunning as exception:
        raise RssJobAlreadyRunningError("RSS company toggle already running") from exception


@rss_router.post("/sync", response_model=RssSyncRead)
def sync_rss_feeds(db: Session = Depends(get_db_session)) -> RssSyncRead:
    try:
        with job_lock(db, "rss_sync"):
            return sync_rss_catalog(db)
    except GitRepositorySyncError as exception:
        raise RssRepositorySyncError("RSS repository sync failed") from exception
    except JobAlreadyRunning as exception:
        raise RssJobAlreadyRunningError("RSS sync already running") from exception


@rss_router.post("/feeds/check", response_model=RssFeedCheckRead)
async def check_rss_feed_urls(
    feed_ids: list[int] | None = Query(default=None),
    db: Session = Depends(get_db_session),
) -> RssFeedCheckRead:
    try:
        with job_lock(db, "rss_feed_check"):
            return await check_rss_feeds(db, feed_ids=feed_ids)
    except JobAlreadyRunning as exception:
        raise RssJobAlreadyRunningError("RSS feed check already running") from exception


@rss_router.get("/img/{icon_url:path}")
def read_rss_icon(icon_url: str) -> FileResponse:
    icon_file_path = get_rss_icon_file_path(icon_url)
    return FileResponse(
        path=icon_file_path,
        media_type="image/svg+xml",
        filename=icon_file_path.name,
    )
