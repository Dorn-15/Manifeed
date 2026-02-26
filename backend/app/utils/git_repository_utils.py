from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Literal
from urllib.parse import urlparse

from .directory_utils import is_empty_directory
from .normalize_utils import normalize_file_extension

RepositoryGitAction = Literal["cloned", "up_to_date", "update"]

class GitRepositorySyncError(Exception):
    """Raised when a git repository sync operation fails."""

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
        raise GitRepositorySyncError(
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
    normalized_current_remote_url = _normalize_repository_url(current_remote_url)
    normalized_expected_remote_url = _normalize_repository_url(expected_repository_url)
    if normalized_current_remote_url != normalized_expected_remote_url:
        raise GitRepositorySyncError(
            "Repository remote mismatch for "
            f"{repository_path}. Expected {expected_repository_url}, got {current_remote_url}."
        )
    if current_remote_url != expected_repository_url:
        run_git_command(
            ["remote", "set-url", "origin", expected_repository_url],
            cwd=repository_path,
        )


def run_git_command(command: list[str], cwd: Path | None) -> str:
    full_command = _build_git_command(command=command, cwd=cwd)
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
        raise GitRepositorySyncError(
            f"Git command failed ({' '.join(full_command)}): {stderr}"
        ) from exception
    return process.stdout.strip()


def _build_git_command(command: list[str], cwd: Path | None) -> list[str]:
    if cwd is None:
        return ["git", *command]

    safe_directory = _resolve_git_safe_directory(cwd)
    return ["git", "-c", f"safe.directory={safe_directory}", *command]


def _resolve_git_safe_directory(cwd: Path) -> str:
    normalized_cwd = cwd.expanduser()
    for candidate in (normalized_cwd, *normalized_cwd.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(normalized_cwd)


def _normalize_repository_url(repository_url: str) -> str:
    normalized_url = repository_url.strip()
    if normalized_url.startswith("git@"):
        host_and_path = normalized_url[4:]
        if ":" in host_and_path:
            host, path = host_and_path.split(":", 1)
            return f"{host.lower()}/{_normalize_repository_path(path)}"
        return _normalize_repository_path(host_and_path)

    parsed_url = urlparse(normalized_url)
    if parsed_url.scheme and parsed_url.netloc:
        return f"{parsed_url.netloc.lower()}/{_normalize_repository_path(parsed_url.path)}"

    return _normalize_repository_path(normalized_url)


def _normalize_repository_path(repository_path: str) -> str:
    normalized_path = repository_path.strip().lstrip("/").rstrip("/")
    if normalized_path.endswith(".git"):
        return normalized_path[:-4]
    return normalized_path
