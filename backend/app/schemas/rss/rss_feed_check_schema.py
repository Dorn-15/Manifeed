from typing import Literal

from pydantic import BaseModel, Field

RssFeedCheckStatus = Literal["valid", "invalid"]


class RssFeedCheckResultRead(BaseModel):
    feed_id: int
    url: str
    status: RssFeedCheckStatus
    error: str


class RssFeedCheckRead(BaseModel):
    results: list[RssFeedCheckResultRead] = Field(default_factory=list)
    valid_count: int = 0
    invalid_count: int = 0
