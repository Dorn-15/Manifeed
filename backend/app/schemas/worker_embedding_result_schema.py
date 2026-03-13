from __future__ import annotations

from pydantic import BaseModel, Field


class WorkerSourceEmbeddingSchema(BaseModel):
    id: int = Field(ge=1)
    embedding: list[float] = Field(default_factory=list, min_length=1)


class WorkerEmbeddingResultPayloadSchema(BaseModel):
    sources: list[WorkerSourceEmbeddingSchema] = Field(default_factory=list, min_length=1)


class WorkerEmbeddingResultSchema(BaseModel):
    model_name: str = Field(min_length=1)
    sources: list[WorkerSourceEmbeddingSchema] = Field(default_factory=list, min_length=1)
