from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_sync_service as rss_sync_service_module
from app.errors.rss import RssCatalogParseError
from app.schemas.rss import (
    RssSourceFeedSchema,
    RssRepositorySyncRead,
)


def test_sync_rss_catalog_returns_empty_stats_when_repository_is_up_to_date(
    monkeypatch,
) -> None:
    mock_db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(
        rss_sync_service_module,
        "resolve_rss_feeds_repository_path",
        lambda: repository_path,
    )

    def fake_sync_repository(repository_url: str, repository_path: Path, branch: str):
        return RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            changed_files=[],
        )

    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        fake_sync_repository,
    )

    response = rss_sync_service_module.sync_rss_catalog(mock_db)

    assert response.repository_action == "up_to_date"
    assert response.processed_files == 0
    assert response.processed_feeds == 0
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_not_called()


def test_sync_rss_catalog_processes_changed_files_and_commits(monkeypatch, tmp_path) -> None:
    mock_db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        rss_sync_service_module,
        "resolve_rss_feeds_repository_path",
        lambda: repository_path,
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            changed_files=["Le_Monde.json"],
        ),
    )

    source_feeds = [
        RssSourceFeedSchema(
            url="https://example.com/rss/main",
            title="Main",
            tags=["tech"],
            trust_score=0.9,
            language="fr",
            enabled=True,
            img="icons/main.svg",
            parsing_config={},
        ),
        RssSourceFeedSchema(
            url="https://example.com/rss/ai",
            title="AI",
            tags=["ai"],
            trust_score=0.8,
            language="en",
            enabled=True,
            img="icons/ai.svg",
            parsing_config={"item_tag": "item"},
        ),
    ]
    monkeypatch.setattr(
        rss_sync_service_module,
        "load_source_feeds_from_json",
        lambda _: source_feeds,
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_company",
        lambda db, company_name: (SimpleNamespace(id=1), True),
    )
    created_tags_by_call = iter([1, 0])
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_tags",
        lambda db, tag_names: ([object()], next(created_tags_by_call)),
    )
    created_feeds_by_call = iter([True, False])
    monkeypatch.setattr(
        rss_sync_service_module,
        "upsert_feed",
        lambda db, company, payload, tags: (object(), next(created_feeds_by_call)),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        lambda db, company_id, expected_urls: 1,
    )

    response = rss_sync_service_module.sync_rss_catalog(mock_db)

    assert response.repository_action == "update"
    assert response.processed_files == 1
    assert response.processed_feeds == 2
    assert response.created_companies == 1
    assert response.created_tags == 1
    assert response.created_feeds == 1
    assert response.updated_feeds == 1
    assert response.deleted_feeds == 1
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_not_called()


def test_sync_rss_catalog_rolls_back_on_parsing_error(monkeypatch, tmp_path) -> None:
    mock_db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        rss_sync_service_module,
        "resolve_rss_feeds_repository_path",
        lambda: repository_path,
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            changed_files=["Le_Monde.json"],
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "load_source_feeds_from_json",
        lambda _: (_ for _ in ()).throw(RssCatalogParseError("invalid payload")),
    )

    with pytest.raises(RssCatalogParseError):
        rss_sync_service_module.sync_rss_catalog(mock_db)

    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_called_once()
