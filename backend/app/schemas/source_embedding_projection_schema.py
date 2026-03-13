from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceEmbeddingProjectionInputSchema(BaseModel):
    source_id: int = Field(ge=1)
    embedding: list[float] = Field(default_factory=list, min_length=1)
    embedding_updated_at: datetime


class SourceEmbeddingProjectionPointSchema(BaseModel):
    source_id: int = Field(ge=1)
    embedding_model_name: str = Field(min_length=1, max_length=120)
    projection_version: str = Field(min_length=1, max_length=80)
    x: float
    y: float
    embedding_updated_at: datetime


class SourceEmbeddingProjectionStateSchema(BaseModel):
    embedding_model_name: str = Field(min_length=1, max_length=120)
    projection_version: str = Field(min_length=1, max_length=80)
    projector_kind: str = Field(min_length=1, max_length=40)
    projector_state: bytes = Field(min_length=1)
    fitted_sources_count: int = Field(ge=1)
    last_embedding_updated_at: datetime | None = None
    updated_at: datetime | None = None
