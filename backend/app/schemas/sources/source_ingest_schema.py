from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RssSourceIngestStatus = Literal["completed"]
RssFeedFetchStatus = Literal["success", "not_modified", "error"]


@dataclass(slots=True)
class RssSourceCandidateSchema:
    title: str
    url: str
    summary: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    image_url: str | None = None


@dataclass(slots=True)
class RssFeedFetchPayloadSchema:
    status: RssFeedFetchStatus
    entries: list[dict[str, Any]] = field(default_factory=list)
    last_modified: datetime | None = None
    error: str | None = None


class RssSourceIngestPayload(BaseModel):
    feed_ids: list[int] | None = Field(default=None, min_length=1)


class RssSourceIngestErrorRead(BaseModel):
    feed_id: int
    feed_url: str
    error: str


class RssSourceIngestRead(BaseModel):
    status: RssSourceIngestStatus = "completed"
    feeds_processed: int = Field(ge=0, default=0)
    feeds_skipped: int = Field(ge=0, default=0)
    sources_created: int = Field(ge=0, default=0)
    sources_updated: int = Field(ge=0, default=0)
    errors: list[RssSourceIngestErrorRead] = Field(default_factory=list)
    duration_ms: int = Field(ge=0, default=0)
