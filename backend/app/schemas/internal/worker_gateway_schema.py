from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkerTaskClaimRequestSchema(BaseModel):
    count: int = Field(default=1, ge=1, le=100)
    lease_seconds: int = Field(default=300, ge=30, le=86400)


class WorkerTaskClaimRead(BaseModel):
    task_id: int = Field(ge=1)
    execution_id: int = Field(ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkerTaskCommandRead(BaseModel):
    ok: bool = True


class RssTaskCompleteRequestSchema(BaseModel):
    task_id: int = Field(ge=1)
    execution_id: int = Field(ge=1)
    result_events: list[dict[str, Any]] = Field(default_factory=list)


class WorkerTaskFailRequestSchema(BaseModel):
    task_id: int = Field(ge=1)
    execution_id: int = Field(ge=1)
    error_message: str = Field(min_length=1)


class RssWorkerStateRequestSchema(BaseModel):
    active: bool
    connection_state: str = Field(min_length=1, max_length=32)
    pending_tasks: int = Field(default=0, ge=0)
    current_task_id: int | None = Field(default=None, ge=1)
    current_execution_id: int | None = Field(default=None, ge=1)
    current_task_label: str | None = Field(default=None, max_length=255)
    current_feed_id: int | None = Field(default=None, ge=1)
    current_feed_url: str | None = Field(default=None, max_length=1000)
    last_error: str | None = None
    desired_state: str | None = Field(default=None, max_length=32)


class EmbeddingTaskCompleteRequestSchema(BaseModel):
    task_id: int = Field(ge=1)
    execution_id: int = Field(ge=1)
    result_payload: dict[str, Any] = Field(default_factory=dict)


class EmbeddingTaskFailRequestSchema(BaseModel):
    task_id: int = Field(ge=1)
    execution_id: int = Field(ge=1)
    error_message: str = Field(min_length=1)
