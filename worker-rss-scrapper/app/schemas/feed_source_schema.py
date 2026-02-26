from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class FeedSourceSchema(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1, max_length=1000)
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    image_url: str | None = None
