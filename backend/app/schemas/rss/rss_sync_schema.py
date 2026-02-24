from typing import Literal

from pydantic import BaseModel, Field

RepositoryAction = Literal["cloned", "update", "up_to_date"]


class RssRepositorySyncRead(BaseModel):
    action: RepositoryAction
    repository_path: str
    changed_files: list[str] = Field(default_factory=list)


class RssSyncRead(BaseModel):
    repository_action: RepositoryAction
