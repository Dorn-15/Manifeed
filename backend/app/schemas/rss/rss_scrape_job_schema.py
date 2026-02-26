from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RssScrapeJobStatus = Literal[
    "queued",
    "processing",
    "completed",
    "completed_with_errors",
    "failed",
]
RssScrapeResultStatus = Literal["success", "not_modified", "error", "pending"]


class RssScrapeFeedPayloadSchema(BaseModel):
    feed_id: int = Field(ge=1)
    feed_url: str = Field(min_length=1, max_length=500)
    company_id: int | None = Field(default=None, ge=1)
    host_header: str | None = Field(default=None, min_length=1, max_length=255)
    fetchprotection: int = Field(default=1, ge=0, le=2)
    etag: str | None = Field(default=None, max_length=255)
    last_update: datetime | None = None
    last_db_article_published_at: datetime | None = None


class RssScrapeJobRequestSchema(BaseModel):
    job_id: str = Field(min_length=1, max_length=36)
    requested_at: datetime
    ingest: bool
    requested_by: str = Field(min_length=1, max_length=100)
    feeds: list[RssScrapeFeedPayloadSchema] = Field(default_factory=list)


class RssScrapeJobQueuedRead(BaseModel):
    job_id: str
    status: RssScrapeJobStatus


class RssScrapeJobStatusRead(BaseModel):
    job_id: str
    ingest: bool
    requested_by: str
    requested_at: datetime
    status: RssScrapeJobStatus
    feeds_total: int = Field(ge=0)
    feeds_processed: int = Field(ge=0)
    feeds_success: int = Field(ge=0)
    feeds_not_modified: int = Field(ge=0)
    feeds_error: int = Field(ge=0)


class RssScrapeJobFeedRead(BaseModel):
    feed_id: int
    feed_url: str
    status: RssScrapeResultStatus = "pending"
    error_message: str | None = None
    fetchprotection: int | None = Field(default=None, ge=0, le=2)
    new_etag: str | None = None
    new_last_update: datetime | None = None
