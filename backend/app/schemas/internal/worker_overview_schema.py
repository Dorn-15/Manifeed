from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkerType = Literal["rss_scrapper", "source_embedding"]


class WorkerInstanceRead(BaseModel):
    name: str = Field(min_length=1)
    processing_tasks: int = Field(ge=0)
    idle_ms: int = Field(ge=0)
    connected: bool
    active: bool
    connection_state: str | None = Field(default=None, max_length=32)
    desired_state: str | None = Field(default=None, max_length=32)
    current_task_id: int | None = Field(default=None, ge=1)
    current_execution_id: int | None = Field(default=None, ge=1)
    current_task_label: str | None = Field(default=None, max_length=255)
    current_feed_id: int | None = Field(default=None, ge=1)
    current_feed_url: str | None = Field(default=None, max_length=1000)
    last_error: str | None = None


class WorkerTypeOverviewRead(BaseModel):
    worker_type: WorkerType
    queue_name: str = Field(min_length=1)
    queue_length: int = Field(ge=0)
    queued_tasks: int = Field(ge=0)
    processing_tasks: int = Field(ge=0)
    worker_count: int = Field(ge=0)
    connected: bool
    active: bool
    workers: list[WorkerInstanceRead] = Field(default_factory=list)


class WorkerOverviewRead(BaseModel):
    generated_at: datetime
    connected_idle_threshold_ms: int = Field(ge=1)
    active_idle_threshold_ms: int = Field(ge=1)
    items: list[WorkerTypeOverviewRead] = Field(default_factory=list)
