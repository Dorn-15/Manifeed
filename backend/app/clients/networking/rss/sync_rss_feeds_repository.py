import json
from pathlib import Path

from pydantic import ValidationError

from app.utils import (
    list_changed_files,
    list_files_with_extension,
    pull_or_clone,
)
from app.errors.rss import (
    RssCatalogParseError,
    RssRepositorySyncError,
)
from app.schemas.rss import (
    RssSourceFeedSchema,
    RssRepositorySyncRead,
)


def sync_rss_feeds_repository(
    repository_url: str,
    repository_path: Path,
    branch: str,
    file_extension: str = ".json",
) -> RssRepositorySyncRead:
    repository_sync = pull_or_clone(
        repository_url=repository_url,
        repository_path=repository_path,
        branch=branch,
    )

    if repository_sync.action == "cloned":
        changed_files = list_files_with_extension(
            repository_path=repository_path,
            file_extension=file_extension,
        )
    elif repository_sync.action == "update":
        if repository_sync.previous_revision is None or repository_sync.current_revision is None:
            raise RssRepositorySyncError(
                "Git update result is missing revision range for changed files lookup."
            )
        changed_files = list_changed_files(
            repository_path=repository_path,
            old_revision=repository_sync.previous_revision,
            new_revision=repository_sync.current_revision,
            file_extension=file_extension,
        )
    else:
        changed_files = []

    return RssRepositorySyncRead(
        action=repository_sync.action,
        repository_path=str(repository_path),
        changed_files=changed_files,
    )


def load_source_feeds_from_json(json_file_path: Path) -> list[RssSourceFeedSchema]:
    if not json_file_path.exists():
        raise RssCatalogParseError(f"JSON file not found: {json_file_path}")

    try:
        payload = json.loads(json_file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exception:
        raise RssCatalogParseError(
            f"Invalid JSON format in file {json_file_path}: {exception}"
        ) from exception

    if not isinstance(payload, list):
        raise RssCatalogParseError(
            f"Expected a list of feeds in file {json_file_path}, got {type(payload).__name__}"
        )

    feeds: list[RssSourceFeedSchema] = []
    for index, feed_payload in enumerate(payload):
        try:
            feeds.append(RssSourceFeedSchema.model_validate(feed_payload))
        except ValidationError as exception:
            raise RssCatalogParseError(
                f"Invalid feed at index {index} in file {json_file_path}: {exception}"
            ) from exception
    return feeds
