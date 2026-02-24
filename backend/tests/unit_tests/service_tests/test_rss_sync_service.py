from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_sync_service as rss_sync_service_module
from app.errors.rss import RssCatalogParseError
from app.schemas.rss import RssRepositorySyncRead, RssSourceCatalogSchema, RssSourceFeedSchema


def _catalog(company: str = "Le Monde") -> RssSourceCatalogSchema:
    return RssSourceCatalogSchema(
        company=company,
        host="www.lemonde.fr",
        img="icons/lemonde.svg",
        country="fr",
        language="fr",
        fetchprotection=2,
        feeds=[
            RssSourceFeedSchema(
                url="https://example.com/rss/main",
                title="Main",
                tags=["tech"],
                enabled=True,
                trust_score=0.9,
                fetchprotection=1,
            ),
            RssSourceFeedSchema(
                url="https://example.com/rss/ai",
                title="AI",
                tags=["ai"],
                enabled=True,
                trust_score=0.8,
                fetchprotection=2,
            ),
        ],
    )


def test_sync_rss_catalog_returns_up_to_date_without_commit(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch, force=False: RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            changed_files=[],
        ),
    )

    result = rss_sync_service_module.sync_rss_catalog(db)

    assert result.repository_action == "up_to_date"
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_sync_rss_catalog_syncs_all_changed_files_and_commits(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch, force=False: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            changed_files=["a.json", "b.json"],
        ),
    )

    synced_files: list[str] = []

    def fake_sync_catalog_file(db, repository_path, relative_json_file_path):
        synced_files.append(relative_json_file_path)

    monkeypatch.setattr(rss_sync_service_module, "_sync_catalog_file", fake_sync_catalog_file)

    result = rss_sync_service_module.sync_rss_catalog(db)

    assert result.repository_action == "update"
    assert synced_files == ["a.json", "b.json"]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_rss_catalog_rolls_back_when_file_sync_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch, force=False: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            changed_files=["broken.json"],
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "_sync_catalog_file",
        lambda db, repository_path, relative_json_file_path: (_ for _ in ()).throw(ValueError("boom")),
    )

    with pytest.raises(ValueError, match="boom"):
        rss_sync_service_module.sync_rss_catalog(db)

    db.rollback.assert_called_once()


def test_sync_catalog_file_removes_company_feeds_when_file_disappears(monkeypatch, tmp_path: Path) -> None:
    db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()

    monkeypatch.setattr(rss_sync_service_module, "_extract_company_name", lambda _p: "Le Monde")
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_company_by_name",
        lambda _db, _name: SimpleNamespace(id=7),
    )

    calls: list[tuple[int, set[str]]] = []

    def fake_delete_company_feeds_not_in_urls(db, company_id, expected_urls):
        calls.append((company_id, expected_urls))

    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        fake_delete_company_feeds_not_in_urls,
    )

    rss_sync_service_module._sync_catalog_file(
        db=db,
        repository_path=repository_path,
        relative_json_file_path="Le_Monde.json",
    )

    assert calls == [(7, set())]


def test_sync_catalog_file_upserts_feeds_and_links_company(monkeypatch, tmp_path: Path) -> None:
    db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(rss_sync_service_module, "load_source_feeds_from_json", lambda _p: _catalog())
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_company",
        lambda db, company_name, host, icon_url, country, language, fetchprotection: (
            SimpleNamespace(id=5, fetchprotection=fetchprotection),
            True,
        ),
    )

    payloads = [
        SimpleNamespace(url="https://example.com/rss/main", tags=["tech"]),
        SimpleNamespace(url="https://example.com/rss/ai", tags=["ai"]),
    ]
    normalize_calls: list[str] = []

    def fake_normalize(source_feed, default_fetchprotection):
        normalize_calls.append(source_feed.url)
        return payloads[len(normalize_calls) - 1]

    monkeypatch.setattr(rss_sync_service_module, "normalize_source_feed_entry", fake_normalize)
    monkeypatch.setattr(
        rss_sync_service_module,
        "list_rss_feeds_by_urls",
        lambda db, urls: {"https://example.com/rss/main": SimpleNamespace(id=11)},
    )
    monkeypatch.setattr(rss_sync_service_module, "get_or_create_tags", lambda db, tags: ([object()], False))

    upserted_urls: list[str] = []

    def fake_upsert_feed(db, payload, tags, existing_feed=None):
        upserted_urls.append(payload.url)
        if payload.url.endswith("main"):
            return SimpleNamespace(id=11), False
        return SimpleNamespace(id=12), True

    monkeypatch.setattr(rss_sync_service_module, "upsert_feed", fake_upsert_feed)

    link_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "link_company_to_feed",
        lambda db, company_id, feed_id: link_calls.append((company_id, feed_id)),
    )

    delete_calls: list[set[str]] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        lambda db, company_id, expected_urls: delete_calls.append(expected_urls),
    )

    rss_sync_service_module._sync_catalog_file(
        db=db,
        repository_path=repository_path,
        relative_json_file_path="Le_Monde.json",
    )

    assert normalize_calls == [
        "https://example.com/rss/main",
        "https://example.com/rss/ai",
    ]
    assert upserted_urls == [
        "https://example.com/rss/main",
        "https://example.com/rss/ai",
    ]
    assert link_calls == [(5, 11), (5, 12)]
    assert delete_calls == [{"https://example.com/rss/main", "https://example.com/rss/ai"}]


def test_extract_company_name_wraps_value_error_as_catalog_parse_error(monkeypatch) -> None:
    monkeypatch.setattr(
        rss_sync_service_module,
        "normalize_name_from_filename",
        lambda _path: (_ for _ in ()).throw(ValueError("invalid filename")),
    )

    with pytest.raises(RssCatalogParseError, match="invalid filename"):
        rss_sync_service_module._extract_company_name(".json")
