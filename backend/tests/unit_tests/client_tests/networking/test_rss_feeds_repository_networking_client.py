import json
from pathlib import Path

import pytest

import app.clients.networking.rss_feeds_repository_networking_client as repository_client_module
from app.errors.rss import RssCatalogParseError


def test_load_source_feeds_from_json_parses_valid_payload(tmp_path: Path) -> None:
    json_file_path = tmp_path / "The_Verge.json"
    json_file_path.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.com/rss",
                    "title": "Tech",
                    "tags": ["tech", "digital"],
                    "trust_score": 0.9,
                    "language": "en",
                    "enabled": True,
                    "img": "theVerge/theVerge.svg",
                }
            ]
        ),
        encoding="utf-8",
    )

    feeds = repository_client_module.load_source_feeds_from_json(json_file_path)

    assert len(feeds) == 1
    assert feeds[0].url == "https://example.com/rss"
    assert feeds[0].tags == ["tech", "digital"]


def test_load_source_feeds_from_json_rejects_non_list_payload(tmp_path: Path) -> None:
    json_file_path = tmp_path / "invalid.json"
    json_file_path.write_text(json.dumps({"url": "https://example.com/rss"}), encoding="utf-8")

    with pytest.raises(RssCatalogParseError):
        repository_client_module.load_source_feeds_from_json(json_file_path)


def test_sync_rss_feeds_repository_clones_when_path_is_missing(
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

    monkeypatch.setattr(
        repository_client_module,
        "_run_git_command",
        fake_run_git_command,
    )
    monkeypatch.setattr(
        repository_client_module,
        "list_json_catalog_files",
        lambda _: ["Le_Monde.json", "The_Verge.json"],
    )

    response = repository_client_module.sync_rss_feeds_repository(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert response.action == "cloned"
    assert response.commit_after == "abc123"
    assert response.changed_json_files == ["Le_Monde.json", "The_Verge.json"]
    assert executed_commands[0][0][0] == "clone"


def test_sync_rss_feeds_repository_clones_when_directory_exists_but_is_empty(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    executed_commands: list[tuple[list[str], Path | None]] = []

    def fake_run_git_command(command: list[str], cwd: Path | None) -> str:
        executed_commands.append((command, cwd))
        if command == ["rev-parse", "HEAD"]:
            return "abc123"
        return ""

    monkeypatch.setattr(
        repository_client_module,
        "_run_git_command",
        fake_run_git_command,
    )
    monkeypatch.setattr(
        repository_client_module,
        "list_json_catalog_files",
        lambda _: ["Le_Monde.json"],
    )

    response = repository_client_module.sync_rss_feeds_repository(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert response.action == "cloned"
    assert response.changed_json_files == ["Le_Monde.json"]
    assert executed_commands[0][0][0] == "clone"
