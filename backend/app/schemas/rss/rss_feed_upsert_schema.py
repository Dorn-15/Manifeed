from pydantic import BaseModel, Field


class RssFeedUpsertSchema(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    section: str | None = Field(default=None, max_length=50)
    enabled: bool = True
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    fetchprotection: int | None = Field(default=None, ge=0, le=3)
    tags: list[str] = Field(default_factory=list)
