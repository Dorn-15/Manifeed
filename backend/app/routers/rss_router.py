from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.schemas.rss import (
    RssFeedRead,
    RssSyncRead,
)
from app.services.rss import (
    get_rss_feeds,
    get_rss_icon_file_path,
    sync_rss_catalog,
)
from database import get_db_session

rss_router = APIRouter(prefix="/rss", tags=["rss"])


@rss_router.get("/", response_model=list[RssFeedRead])
def read_rss_feeds(db: Session = Depends(get_db_session)) -> list[RssFeedRead]:
    return get_rss_feeds(db)


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
