from pydantic import BaseModel


class RssCompanyRead(BaseModel):
    id: int
    name: str
    host: str | None = None
    icon_url: str | None = None
    country: str | None = None
    language: str | None = None
    fetchprotection: int
    enabled: bool
