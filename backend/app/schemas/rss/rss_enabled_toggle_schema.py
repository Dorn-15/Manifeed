from pydantic import BaseModel


class RssEnabledTogglePayload(BaseModel):
    enabled: bool
