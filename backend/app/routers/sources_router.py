from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.errors.rss import RssJobAlreadyRunningError
from app.schemas.sources import (
    RssSourceDetailRead,
    RssSourceIngestPayload,
    RssSourceIngestRead,
    RssSourcePageRead,
)
from app.services.sources import (
    get_rss_source_by_id,
    get_rss_sources,
    ingest_rss_sources,
)
from app.utils import JobAlreadyRunning, job_lock
from database import get_db_session

sources_router = APIRouter(prefix="/sources", tags=["sources"])


@sources_router.get("/", response_model=RssSourcePageRead)
def read_sources(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(
        db,
        limit=limit,
        offset=offset,
    )


@sources_router.get("/feeds/{feed_id}", response_model=RssSourcePageRead)
def read_sources_by_feed(
    feed_id: int = Path(ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(
        db,
        limit=limit,
        offset=offset,
        feed_id=feed_id,
    )


@sources_router.get("/companies/{company_id}", response_model=RssSourcePageRead)
def read_sources_by_company(
    company_id: int = Path(ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db_session),
) -> RssSourcePageRead:
    return get_rss_sources(
        db,
        limit=limit,
        offset=offset,
        company_id=company_id,
    )


@sources_router.post("/ingest", response_model=RssSourceIngestRead)
async def ingest_sources(
    payload: RssSourceIngestPayload | None = None,
    db: Session = Depends(get_db_session),
) -> RssSourceIngestRead:
    feed_ids = payload.feed_ids if payload else None
    try:
        with job_lock(db, "sources_ingest"):
            return await ingest_rss_sources(db, feed_ids=feed_ids)
    except JobAlreadyRunning as exception:
        raise RssJobAlreadyRunningError("Sources ingest already running") from exception


@sources_router.get("/{source_id}", response_model=RssSourceDetailRead)
def read_source_by_id(
    source_id: int = Path(ge=1),
    db: Session = Depends(get_db_session),
) -> RssSourceDetailRead:
    source = get_rss_source_by_id(db, source_id=source_id)
    if source is None:
        raise HTTPException(
            status_code=404,
            detail=f"RSS source {source_id} not found",
        )
    return source
