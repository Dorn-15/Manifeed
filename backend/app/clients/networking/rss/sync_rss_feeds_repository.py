import json
from pathlib import Path

from pydantic import ValidationError

from app.utils import pull_or_clone
from app.errors.rss import RssCatalogParseError
from app.schemas.rss import (
    RssSourceCatalogSchema,
    RssRepositorySyncRead,
)


def sync_rss_feeds_repository(
    repository_url: str,
    repository_path: Path | str,
    branch: str,
) -> RssRepositorySyncRead:
    repository_path = Path(repository_path).expanduser()

    repository_sync = pull_or_clone(
        repository_url=repository_url,
        repository_path=repository_path,
        branch=branch,
    )

    return RssRepositorySyncRead(
        action=repository_sync.action,
        repository_path=str(repository_path),
        previous_revision=repository_sync.previous_revision,
        current_revision=repository_sync.current_revision,
    )


def load_source_feeds_from_json(json_file_path: Path) -> RssSourceCatalogSchema:
    if not json_file_path.is_file():
        raise RssCatalogParseError(f"JSON file not found: {json_file_path}")

    try:
        with json_file_path.open(encoding="utf-8") as json_file:
            payload = json.load(json_file)
    except json.JSONDecodeError as exception:
        raise RssCatalogParseError(
            f"Invalid JSON format in file {json_file_path}: {exception}"
        ) from exception

    if not isinstance(payload, dict):
        raise RssCatalogParseError(
            f"Expected an object payload in file {json_file_path}, got {type(payload).__name__}"
        )

    try:
        return RssSourceCatalogSchema.model_validate(payload)
    except ValidationError as exception:
        raise RssCatalogParseError(
            f"Invalid catalog payload in file {json_file_path}: {exception}"
        ) from exception
