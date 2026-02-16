from typing import Literal

from pydantic import BaseModel, Field

RepositoryAction = Literal["cloned", "update", "up_to_date"]


class RssRepositorySyncRead(BaseModel):
    action: RepositoryAction
    repository_path: str
    changed_files: list[str] = Field(default_factory=list)


class RssSyncRead(BaseModel):
    repository_action: RepositoryAction
    processed_files: int = 0
    processed_feeds: int = 0
    created_companies: int = 0
    created_tags: int = 0
    created_feeds: int = 0
    updated_feeds: int = 0
    deleted_feeds: int = 0
