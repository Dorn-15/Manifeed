from datetime import datetime

from pydantic import BaseModel, Field


class RssSourceRead(BaseModel):
    id: int
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    image_url: str | None = None
    company_name: str | None = None


class RssSourcePageRead(BaseModel):
    items: list[RssSourceRead] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class RssSourceDetailRead(BaseModel):
    id: int
    title: str
    summary: str | None = None
    url: str
    published_at: datetime | None = None
    image_url: str | None = None
    company_name: str | None = None
    feed_sections: list[str] = Field(default_factory=list)
