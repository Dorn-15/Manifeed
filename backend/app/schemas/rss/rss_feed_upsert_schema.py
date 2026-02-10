from typing import Any

from pydantic import BaseModel, Field


class RssFeedUpsertSchema(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    section: str | None = Field(default=None, max_length=50)
    enabled: bool
    trust_score: float = Field(ge=0.0, le=1.0)
    language: str | None = Field(default=None, min_length=2, max_length=2)
    icon_url: str | None = Field(default=None, max_length=500)
    parsing_config: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
