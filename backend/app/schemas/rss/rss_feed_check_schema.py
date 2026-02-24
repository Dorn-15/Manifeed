from typing import Literal

from pydantic import BaseModel

RssFeedCheckStatus = Literal["valid", "invalid"]


class RssFeedCheckResultRead(BaseModel):
    feed_id: int
    url: str
    status: RssFeedCheckStatus
    error: str
    fetchprotection: int | None = None
