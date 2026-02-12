from pydantic import BaseModel


class RssCompanyRead(BaseModel):
    id: int
    name: str
    enabled: bool
