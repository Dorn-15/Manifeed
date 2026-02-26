from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class WorkerTokenRequestSchema(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)
    worker_secret: str = Field(min_length=1, max_length=500)


class WorkerTokenRead(BaseModel):
    access_token: str
    expires_at: datetime
