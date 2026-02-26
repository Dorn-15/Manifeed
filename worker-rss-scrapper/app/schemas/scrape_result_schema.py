from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.feed_source_schema import FeedSourceSchema

ScrapeResultStatus = Literal["success", "not_modified", "error"]


class ScrapeResultSchema(BaseModel):
    job_id: str
    ingest: bool
    feed_id: int
    feed_url: str
    status: ScrapeResultStatus
    error_message: str | None = None
    new_etag: str | None = None
    new_last_update: datetime | None = None
    fetchprotection: int = Field(ge=0, le=2)
    sources: list[FeedSourceSchema] = Field(default_factory=list)
