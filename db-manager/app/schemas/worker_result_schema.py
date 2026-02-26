from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class WorkerSourceSchema(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1, max_length=1000)
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    image_url: str | None = None


WorkerResultStatus = Literal["success", "not_modified", "error"]


class WorkerResultSchema(BaseModel):
    job_id: str
    ingest: bool
    feed_id: int = Field(ge=1)
    feed_url: str = Field(min_length=1, max_length=500)
    status: WorkerResultStatus
    error_message: str | None = None
    new_etag: str | None = None
    new_last_update: datetime | None = None
    fetchprotection: int = Field(ge=0, le=2)
    sources: list[WorkerSourceSchema] = Field(default_factory=list)
