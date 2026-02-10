import json
import subprocess
from pathlib import Path

from pydantic import ValidationError

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
) -> RssRepositorySyncRead:
    if not repository_path.exists() or _is_empty_directory(repository_path):
        repository_path.parent.mkdir(parents=True, exist_ok=True)
        _run_git_command(
            [
                "clone",
                "--branch",
                branch,
                repository_url,
                str(repository_path),
            ],
            cwd=None,
        )
        commit_after = _run_git_command(["rev-parse", "HEAD"], cwd=repository_path)
        return RssRepositorySyncRead(
            action="cloned",
            repository_path=str(repository_path),
            commit_after=commit_after,
            changed_json_files=list_json_catalog_files(repository_path),
        )

    if not (repository_path / ".git").exists():
        raise RssRepositorySyncError(
            f"Path exists but is not a git repository: {repository_path}"
        )

    _validate_repository_remote(repository_path, repository_url)
    _run_git_command(["fetch", "origin", branch], cwd=repository_path)

    commit_before = _run_git_command(["rev-parse", "HEAD"], cwd=repository_path)
    remote_commit = _run_git_command(["rev-parse", f"origin/{branch}"], cwd=repository_path)

    if commit_before == remote_commit:
        return RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            commit_before=commit_before,
            commit_after=remote_commit,
            changed_json_files=[],
        )

    changed_json_files = _list_changed_json_files(
        repository_path=repository_path,
        old_commit=commit_before,
        new_commit=remote_commit,
    )
    _run_git_command(["checkout", branch], cwd=repository_path)
    _run_git_command(["pull", "--ff-only", "origin", branch], cwd=repository_path)
    commit_after = _run_git_command(["rev-parse", "HEAD"], cwd=repository_path)

    return RssRepositorySyncRead(
        action="pulled",
        repository_path=str(repository_path),
        commit_before=commit_before,
        commit_after=commit_after,
        changed_json_files=changed_json_files,
    )


def list_json_catalog_files(repository_path: Path) -> list[str]:
    json_catalog_files = [
        file_path.relative_to(repository_path).as_posix()
        for file_path in repository_path.rglob("*.json")
        if ".git" not in file_path.parts
    ]
    return sorted(json_catalog_files)


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


def _validate_repository_remote(repository_path: Path, expected_repository_url: str) -> None:
    current_remote_url = _run_git_command(
        ["config", "--get", "remote.origin.url"],
        cwd=repository_path,
    )
    if current_remote_url != expected_repository_url:
        raise RssRepositorySyncError(
            "Repository remote mismatch for "
            f"{repository_path}. Expected {expected_repository_url}, got {current_remote_url}."
        )


def _list_changed_json_files(
    repository_path: Path,
    old_commit: str,
    new_commit: str,
) -> list[str]:
    changed_files_output = _run_git_command(
        ["diff", "--name-only", old_commit, new_commit],
        cwd=repository_path,
    )
    changed_json_files = {
        changed_file.strip()
        for changed_file in changed_files_output.splitlines()
        if changed_file.strip().endswith(".json")
    }
    return sorted(changed_json_files)


def _run_git_command(command: list[str], cwd: Path | None) -> str:
    full_command = ["git", *command]
    try:
        process = subprocess.run(
            full_command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exception:
        stderr = exception.stderr.strip() or "no stderr output"
        raise RssRepositorySyncError(
            f"Git command failed ({' '.join(full_command)}): {stderr}"
        ) from exception
    return process.stdout.strip()


def _is_empty_directory(path: Path) -> bool:
    return path.exists() and path.is_dir() and not any(path.iterdir())
