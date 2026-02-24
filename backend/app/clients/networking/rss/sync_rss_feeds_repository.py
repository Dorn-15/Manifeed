import json
from pathlib import Path
from pathlib import PurePosixPath
from pydantic import ValidationError

from app.utils import (
    list_changed_files,
    list_files_on_dir_with_ext,
    pull_or_clone,
)
from app.errors.rss import (
    RssCatalogParseError,
    RssRepositorySyncError,
)
from app.schemas.rss import (
    RssSourceCatalogSchema,
    RssRepositorySyncRead,
)

_CATALOG_DIR = "json"


def sync_rss_feeds_repository(
    repository_url: str,
    repository_path: Path | str,
    branch: str,
    file_extension: str = ".json",
    force: bool = False,
) -> RssRepositorySyncRead:
    repository_path = Path(repository_path).expanduser()

    repository_sync = pull_or_clone(
        repository_url=repository_url,
        repository_path=repository_path,
        branch=branch,
    )

    changed_files: list[str] = []
    catalog_repository_path = repository_path / _CATALOG_DIR
    if force or repository_sync.action == "cloned":
        changed_files = list_files_on_dir_with_ext(
            repository_path=catalog_repository_path,
            file_extension=file_extension,
        )
    elif repository_sync.action == "update":
        if repository_sync.previous_revision is None or repository_sync.current_revision is None:
            raise RssRepositorySyncError(
                "Git update result is missing revision range for changed files lookup."
            )
        changed_files = list_changed_files(
            repository_path=catalog_repository_path,
            old_revision=repository_sync.previous_revision,
            new_revision=repository_sync.current_revision,
            file_extension=file_extension,
        )

    changed_files = [_to_repository_relative_catalog_path(path) for path in changed_files]

    return RssRepositorySyncRead(
        action=repository_sync.action,
        repository_path=str(repository_path),
        changed_files=changed_files,
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


def _to_repository_relative_catalog_path(path: str) -> str:
    normalized_path = PurePosixPath(path).as_posix()

    if normalized_path in ("", ".", _CATALOG_DIR):
        return _CATALOG_DIR

    while normalized_path.startswith("./"):
        normalized_path = normalized_path[2:]

    if normalized_path.startswith(f"{_CATALOG_DIR}/"):
        return normalized_path
    return f"{_CATALOG_DIR}/{normalized_path}"
