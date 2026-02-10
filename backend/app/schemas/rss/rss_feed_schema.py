from pydantic import BaseModel


class RssFeedRead(BaseModel):
    id: int
    url: str
    company_name: str | None = None
    section: str | None = None
    enabled: bool
    status: str
    trust_score: float
    language: str | None = None
    icon_url: str | None = None
