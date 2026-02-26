from pathlib import Path
import subprocess

import pytest

import app.utils.git_repository_utils as git_utils_module


def test_run_git_command_adds_safe_directory_for_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / ".git").mkdir()

    captured: dict[str, object] = {}

    def fake_run(full_command, cwd, check, capture_output, text):
        captured["full_command"] = full_command
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(
            args=full_command,
            returncode=0,
            stdout="main\n",
            stderr="",
        )

    monkeypatch.setattr(git_utils_module.subprocess, "run", fake_run)

    result = git_utils_module.run_git_command(
        command=["branch", "--show-current"],
        cwd=repository_path,
    )

    assert result == "main"
    assert captured["cwd"] == repository_path
    assert captured["full_command"] == [
        "git",
        "-c",
        f"safe.directory={repository_path}",
        "branch",
        "--show-current",
    ]


def test_run_git_command_adds_repo_root_when_called_from_subdirectory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / ".git").mkdir()
    catalog_path = repository_path / "json"
    catalog_path.mkdir()

    captured: dict[str, object] = {}

    def fake_run(full_command, cwd, check, capture_output, text):
        captured["full_command"] = full_command
        return subprocess.CompletedProcess(
            args=full_command,
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    monkeypatch.setattr(git_utils_module.subprocess, "run", fake_run)

    git_utils_module.run_git_command(
        command=["diff", "--name-only", "old", "new"],
        cwd=catalog_path,
    )

    assert captured["full_command"] == [
        "git",
        "-c",
        f"safe.directory={repository_path}",
        "diff",
        "--name-only",
        "old",
        "new",
    ]


def test_run_git_command_keeps_clone_without_safe_directory(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(full_command, cwd, check, capture_output, text):
        captured["full_command"] = full_command
        return subprocess.CompletedProcess(
            args=full_command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(git_utils_module.subprocess, "run", fake_run)

    git_utils_module.run_git_command(
        command=["clone", "https://example.com/repo.git", "/tmp/repo"],
        cwd=None,
    )

    assert captured["full_command"] == [
        "git",
        "clone",
        "https://example.com/repo.git",
        "/tmp/repo",
    ]


def test_validate_repository_remote_accepts_equivalent_ssh_and_https(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_git_command(command: list[str], cwd: Path) -> str:
        if command == ["config", "--get", "remote.origin.url"]:
            return "git@github.com:Dorn-15/rss_feeds.git"
        calls.append(command)
        return ""

    monkeypatch.setattr(
        git_utils_module,
        "run_git_command",
        fake_run_git_command,
    )

    git_utils_module._validate_repository_remote(
        repository_path=Path("/rss_feeds"),
        expected_repository_url="https://github.com/Dorn-15/rss_feeds",
    )
    assert calls == [
        [
            "remote",
            "set-url",
            "origin",
            "https://github.com/Dorn-15/rss_feeds",
        ]
    ]


def test_validate_repository_remote_raises_when_remote_is_different(monkeypatch) -> None:
    monkeypatch.setattr(
        git_utils_module,
        "run_git_command",
        lambda command, cwd: "git@github.com:other/rss_feeds.git",
    )

    with pytest.raises(git_utils_module.GitRepositorySyncError, match="Repository remote mismatch"):
        git_utils_module._validate_repository_remote(
            repository_path=Path("/rss_feeds"),
            expected_repository_url="https://github.com/Dorn-15/rss_feeds",
        )


def test_validate_repository_remote_keeps_identical_remote_without_update(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_git_command(command: list[str], cwd: Path) -> str:
        calls.append(command)
        return "https://github.com/Dorn-15/rss_feeds"

    monkeypatch.setattr(
        git_utils_module,
        "run_git_command",
        fake_run_git_command,
    )

    git_utils_module._validate_repository_remote(
        repository_path=Path("/rss_feeds"),
        expected_repository_url="https://github.com/Dorn-15/rss_feeds",
    )

    assert calls == [["config", "--get", "remote.origin.url"]]
