from pathlib import Path

import pytest

import app.clients.networking.rss.git_repository_utils as git_repository_utils_module
from app.errors.rss import RssRepositorySyncError


def test_pull_or_clone_returns_cloned_when_repository_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    executed_commands: list[tuple[list[str], Path | None]] = []

    def fake_run_git_command(command: list[str], cwd: Path | None) -> str:
        executed_commands.append((command, cwd))
        if command == ["rev-parse", "HEAD"]:
            return "abc123"
        return ""

    monkeypatch.setattr(git_repository_utils_module, "run_git_command", fake_run_git_command)

    result = git_repository_utils_module.pull_or_clone(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert result.action == "cloned"
    assert result.current_revision == "abc123"
    assert executed_commands[0][0][0] == "clone"


def test_pull_or_clone_returns_up_to_date_when_revision_matches_remote(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / ".git").mkdir()
    executed_commands: list[tuple[list[str], Path | None]] = []

    def fake_run_git_command(command: list[str], cwd: Path | None) -> str:
        executed_commands.append((command, cwd))
        responses = {
            ("config", "--get", "remote.origin.url"): "https://github.com/Dorn-15/rss_feeds",
            ("fetch", "origin", "main"): "",
            ("rev-parse", "HEAD"): "abc123",
            ("rev-parse", "origin/main"): "abc123",
        }
        return responses.get(tuple(command), "")

    monkeypatch.setattr(git_repository_utils_module, "run_git_command", fake_run_git_command)

    result = git_repository_utils_module.pull_or_clone(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert result.action == "up_to_date"
    assert result.previous_revision == "abc123"
    assert result.current_revision == "abc123"
    assert not any(command[0] == "pull" for command, _ in executed_commands)


def test_pull_or_clone_returns_update_when_remote_revision_differs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / ".git").mkdir()
    executed_commands: list[tuple[list[str], Path | None]] = []
    head_responses = iter(["abc123", "def456"])

    def fake_run_git_command(command: list[str], cwd: Path | None) -> str:
        executed_commands.append((command, cwd))
        if command == ["config", "--get", "remote.origin.url"]:
            return "https://github.com/Dorn-15/rss_feeds"
        if command == ["fetch", "origin", "main"]:
            return ""
        if command == ["rev-parse", "HEAD"]:
            return next(head_responses)
        if command == ["rev-parse", "origin/main"]:
            return "def456"
        if command == ["checkout", "main"]:
            return ""
        if command == ["pull", "--ff-only", "origin", "main"]:
            return ""
        return ""

    monkeypatch.setattr(git_repository_utils_module, "run_git_command", fake_run_git_command)

    result = git_repository_utils_module.pull_or_clone(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert result.action == "update"
    assert result.previous_revision == "abc123"
    assert result.current_revision == "def456"
    assert any(command[0] == "pull" for command, _ in executed_commands)


def test_pull_or_clone_raises_for_non_git_directory(tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "README.md").write_text("not a git repo", encoding="utf-8")

    with pytest.raises(RssRepositorySyncError):
        git_repository_utils_module.pull_or_clone(
            repository_url="https://github.com/Dorn-15/rss_feeds",
            repository_path=repository_path,
            branch="main",
        )


def test_list_changed_files_filters_with_custom_extension(monkeypatch, tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"

    monkeypatch.setattr(
        git_repository_utils_module,
        "run_git_command",
        lambda command, cwd: "Le_Monde.json\nsources.yaml\nThe_Verge.json\n",
    )

    changed_files = git_repository_utils_module.list_changed_files(
        repository_path=repository_path,
        old_revision="abc123",
        new_revision="def456",
        file_extension="json",
    )

    assert changed_files == ["Le_Monde.json", "The_Verge.json"]


def test_normalize_file_extension_supports_wildcard_format() -> None:
    normalized_extension = git_repository_utils_module.normalize_file_extension("*.yaml")

    assert normalized_extension == ".yaml"


def test_normalize_file_extension_rejects_empty_value() -> None:
    with pytest.raises(RssRepositorySyncError):
        git_repository_utils_module.normalize_file_extension("   ")
