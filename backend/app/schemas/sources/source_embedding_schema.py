from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.enums import WorkerJobKind, WorkerJobStatus


class RssSourceEmbeddingPayloadSchema(BaseModel):
    id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    url: str = Field(min_length=1, max_length=1000)


class RssSourceEmbeddingRequestSchema(BaseModel):
    sources: list[RssSourceEmbeddingPayloadSchema] = Field(default_factory=list, min_length=1)


class RssSourceEmbeddingEnqueueRead(BaseModel):
    job_id: str | None = None
    job_kind: WorkerJobKind = WorkerJobKind.SOURCE_EMBEDDING
    status: WorkerJobStatus = WorkerJobStatus.QUEUED
    tasks_total: int = Field(ge=0, default=0)
    items_total: int = Field(ge=0, default=0)
    queued_sources: int = Field(ge=0)


class RssSourceEmbeddingMapPointRead(BaseModel):
    source_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    url: str = Field(min_length=1, max_length=1000)
    published_at: datetime | None = None
    image_url: str | None = None
    company_names: list[str] = Field(default_factory=list)
    x: float
    y: float


class RssSourceEmbeddingMapRead(BaseModel):
    items: list[RssSourceEmbeddingMapPointRead] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)
    date_from: date | None = None
    date_to: date | None = None
    embedding_model_name: str = Field(min_length=1, max_length=120)
    projection_version: str = Field(min_length=1, max_length=80)


class RssSourceEmbeddingNeighborRead(RssSourceEmbeddingMapPointRead):
    similarity: float = Field(ge=-1, le=1)


class RssSourceEmbeddingNeighborhoodRead(BaseModel):
    source: RssSourceEmbeddingMapPointRead
    neighbors: list[RssSourceEmbeddingNeighborRead] = Field(default_factory=list)
    neighbor_limit: int = Field(ge=1)
    date_from: date | None = None
    date_to: date | None = None
    embedding_model_name: str = Field(min_length=1, max_length=120)
    projection_version: str = Field(min_length=1, max_length=80)


class RssSourceEmbeddingSimilarityCandidateSchema(BaseModel):
    source_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    url: str = Field(min_length=1, max_length=1000)
    published_at: datetime | None = None
    image_url: str | None = None
    company_names: list[str] = Field(default_factory=list)
    x: float
    y: float
    embedding: list[float] = Field(default_factory=list, min_length=1)
    embedding_model_name: str = Field(min_length=1, max_length=120)
    projection_version: str = Field(min_length=1, max_length=80)
    similarity: float | None = None
