from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TaskLeaseRead(BaseModel):
    task_id: str = Field(min_length=1)
    worker_name: str | None = None
    idle_ms: int = Field(ge=0)
    attempts: int = Field(ge=0)


class QueueWorkerRead(BaseModel):
    name: str = Field(min_length=1)
    processing_tasks: int = Field(ge=0)
    idle_ms: int = Field(ge=0)
    connected: bool
    active: bool


class TaskQueueOverviewRead(BaseModel):
    queue_name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    worker_type: str = Field(min_length=1)
    queue_exists: bool
    queue_length: int = Field(ge=0)
    queued_tasks: int = Field(ge=0)
    processing_tasks: int = Field(ge=0)
    last_task_id: str | None = None
    connected_workers: int = Field(ge=0)
    active_workers: int = Field(ge=0)
    blocked: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    error: str | None = None
    workers: list[QueueWorkerRead] = Field(default_factory=list)
    leased_tasks: list[TaskLeaseRead] = Field(default_factory=list)


class QueueOverviewRead(BaseModel):
    generated_at: datetime
    connected_idle_threshold_ms: int = Field(ge=1)
    active_idle_threshold_ms: int = Field(ge=1)
    stuck_pending_threshold_ms: int = Field(ge=1)
    queue_backend_available: bool
    queue_backend_error: str | None = None
    blocked_queues: int = Field(ge=0)
    items: list[TaskQueueOverviewRead] = Field(default_factory=list)


class QueuePurgeRead(BaseModel):
    queue_name: str = Field(min_length=1)
    deleted: bool
    purged_at: datetime
