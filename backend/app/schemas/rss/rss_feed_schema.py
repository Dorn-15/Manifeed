from pydantic import BaseModel

from .rss_company_schema import RssCompanyRead


class RssFeedRead(BaseModel):
    id: int
    url: str
    section: str | None = None
    enabled: bool
    trust_score: float
    fetchprotection: int
    company: RssCompanyRead | None = None
