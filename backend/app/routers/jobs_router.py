from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.schemas.rss import (
    RssScrapeJobFeedRead,
    RssScrapeJobStatusRead,
)
from app.services.rss import (
    get_rss_scrape_job_status,
    list_rss_scrape_job_feeds,
)
from database import get_db_session

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}", response_model=RssScrapeJobStatusRead)
def read_job_status(
    job_id: str = Path(min_length=1),
    db: Session = Depends(get_db_session),
) -> RssScrapeJobStatusRead:
    return get_rss_scrape_job_status(db, job_id=job_id)


@jobs_router.get("/{job_id}/feeds", response_model=list[RssScrapeJobFeedRead])
def read_job_feeds(
    job_id: str = Path(min_length=1),
    db: Session = Depends(get_db_session),
) -> list[RssScrapeJobFeedRead]:
    return list_rss_scrape_job_feeds(db, job_id=job_id)
