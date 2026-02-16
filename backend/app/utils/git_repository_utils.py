from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Literal

from app.errors.rss import RssRepositorySyncError
from app.utils import (
    normalize_file_extension,
    is_empty_directory,
)

RepositoryGitAction = Literal["cloned", "up_to_date", "update"]


@dataclass(frozen=True)
class PullOrCloneResult:
    action: RepositoryGitAction
    previous_revision: str | None = None
    current_revision: str | None = None


def pull_or_clone(
    repository_url: str,
    repository_path: Path,
    branch: str,
) -> PullOrCloneResult:
    if not repository_path.exists() or is_empty_directory(repository_path):
        repository_path.parent.mkdir(parents=True, exist_ok=True)
        run_git_command(
            [
                "clone",
                "--branch",
                branch,
                repository_url,
                str(repository_path),
            ],
            cwd=None,
        )
        current_revision = run_git_command(["rev-parse", "HEAD"], cwd=repository_path)
        return PullOrCloneResult(action="cloned", current_revision=current_revision)

    if not (repository_path / ".git").exists():
        raise RssRepositorySyncError(
            f"Path exists but is not a git repository: {repository_path}"
        )

    _validate_repository_remote(repository_path, repository_url)
    run_git_command(["fetch", "origin", branch], cwd=repository_path)

    previous_revision = run_git_command(["rev-parse", "HEAD"], cwd=repository_path)
    remote_revision = run_git_command(["rev-parse", f"origin/{branch}"], cwd=repository_path)
    if previous_revision == remote_revision:
        return PullOrCloneResult(
            action="up_to_date",
            previous_revision=previous_revision,
            current_revision=remote_revision,
        )

    run_git_command(["checkout", branch], cwd=repository_path)
    run_git_command(["pull", "--ff-only", "origin", branch], cwd=repository_path)
    current_revision = run_git_command(["rev-parse", "HEAD"], cwd=repository_path)
    return PullOrCloneResult(
        action="update",
        previous_revision=previous_revision,
        current_revision=current_revision,
    )


def list_changed_files(
    repository_path: Path,
    old_revision: str,
    new_revision: str,
    file_extension: str = "*",
) -> list[str]:
    normalized_extension = normalize_file_extension(file_extension)
    changed_files_output = run_git_command(
        ["diff", "--name-only", old_revision, new_revision],
        cwd=repository_path,
    )
    changed_files = {
        changed_file.strip()
        for changed_file in changed_files_output.splitlines()
        if changed_file.strip().endswith(normalized_extension)
    }
    return sorted(changed_files)


def _validate_repository_remote(repository_path: Path, expected_repository_url: str) -> None:
    current_remote_url = run_git_command(
        ["config", "--get", "remote.origin.url"],
        cwd=repository_path,
    )
    if current_remote_url != expected_repository_url:
        raise RssRepositorySyncError(
            "Repository remote mismatch for "
            f"{repository_path}. Expected {expected_repository_url}, got {current_remote_url}."
        )


def run_git_command(command: list[str], cwd: Path | None) -> str:
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
