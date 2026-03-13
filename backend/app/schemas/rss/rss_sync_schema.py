from typing import Literal

from pydantic import BaseModel, Field

CatalogSyncMode = Literal["noop", "full_reconcile"]
RepositoryAction = Literal["cloned", "update", "up_to_date"]


class RssRepositorySyncRead(BaseModel):
    action: RepositoryAction
    repository_path: str
    previous_revision: str | None = None
    current_revision: str | None = None
    changed_files: list[str] = Field(default_factory=list)


class RssSyncRead(BaseModel):
    repository_action: RepositoryAction
    mode: CatalogSyncMode = "noop"
    current_revision: str | None = None
    applied_from_revision: str | None = None
    files_processed: int = 0
    companies_removed: int = 0
    feeds_removed: int = 0
