from pydantic import BaseModel


class RssEnabledTogglePayload(BaseModel):
    enabled: bool


class RssFeedEnabledToggleRead(BaseModel):
    feed_id: int
    enabled: bool


class RssCompanyEnabledToggleRead(BaseModel):
    company_id: int
    enabled: bool