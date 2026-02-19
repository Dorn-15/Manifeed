import importlib
import json
from pathlib import Path

import pytest

repository_client_module = importlib.import_module(
    "app.clients.networking.rss.sync_rss_feeds_repository"
)
from app.utils.git_repository_utils import PullOrCloneResult
from app.errors.rss import RssCatalogParseError
from app.utils import (
    list_files_with_extension,
)


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
                    "country": "en",
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


def test_sync_rss_feeds_repository_returns_cloned_with_catalog_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"

    monkeypatch.setattr(
        repository_client_module,
        "pull_or_clone",
        lambda repository_url, repository_path, branch: PullOrCloneResult(action="cloned"),
    )
    monkeypatch.setattr(
        repository_client_module,
        "list_files_with_extension",
        lambda repository_path, file_extension: ["Le_Monde.json", "The_Verge.json"],
    )

    response = repository_client_module.sync_rss_feeds_repository(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
    )

    assert response.action == "cloned"
    assert response.changed_files == ["Le_Monde.json", "The_Verge.json"]


def test_sync_rss_feeds_repository_returns_update_with_extension_filter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"

    monkeypatch.setattr(
        repository_client_module,
        "pull_or_clone",
        lambda repository_url, repository_path, branch: PullOrCloneResult(
            action="update",
            previous_revision="abc123",
            current_revision="def456",
        ),
    )

    def fake_list_changed_files(
        repository_path: Path,
        old_revision: str,
        new_revision: str,
        file_extension: str,
    ) -> list[str]:
        assert old_revision == "abc123"
        assert new_revision == "def456"
        assert file_extension == ".yaml"
        return ["rss_sources.yaml"]

    monkeypatch.setattr(repository_client_module, "list_changed_files", fake_list_changed_files)

    response = repository_client_module.sync_rss_feeds_repository(
        repository_url="https://github.com/Dorn-15/rss_feeds",
        repository_path=repository_path,
        branch="main",
        file_extension=".yaml",
    )

    assert response.action == "update"
    assert response.changed_files == ["rss_sources.yaml"]


def test_list_files_with_extension_supports_custom_file_extension(tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")
    (repository_path / "sources.yaml").write_text("[]", encoding="utf-8")
    (repository_path / ".git").mkdir()
    (repository_path / ".git" / "ignored.yaml").write_text("[]", encoding="utf-8")

    catalog_files = list_files_with_extension(
        repository_path=repository_path,
        file_extension="yaml",
    )

    assert catalog_files == ["sources.yaml"]
