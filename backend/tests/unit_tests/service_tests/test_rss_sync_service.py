from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_sync_service as rss_sync_service_module
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


def test_sync_rss_catalog_returns_noop_without_commit_when_revision_already_applied(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_rss_catalog_sync_state",
        lambda _db: SimpleNamespace(last_applied_revision="rev-2"),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            previous_revision="rev-2",
            current_revision="rev-2",
        ),
    )

    result = rss_sync_service_module.sync_rss_catalog(db)

    assert result.repository_action == "up_to_date"
    assert result.mode == "noop"
    assert result.current_revision == "rev-2"
    assert result.applied_from_revision == "rev-2"
    assert result.files_processed == 0
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_sync_rss_catalog_reconciles_when_revision_is_not_applied(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_rss_catalog_sync_state",
        lambda _db: SimpleNamespace(last_applied_revision="rev-1"),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            previous_revision="rev-2",
            current_revision="rev-2",
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "_reconcile_rss_catalog",
        lambda db, repository_path: rss_sync_service_module._CatalogReconcileResult(
            files_processed=2,
            companies_removed=1,
            feeds_removed=3,
        ),
    )

    marked_revisions: list[str | None] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "mark_rss_catalog_sync_success",
        lambda db, current_revision: marked_revisions.append(current_revision),
    )

    result = rss_sync_service_module.sync_rss_catalog(db)

    assert result.repository_action == "up_to_date"
    assert result.mode == "full_reconcile"
    assert result.current_revision == "rev-2"
    assert result.applied_from_revision == "rev-1"
    assert result.files_processed == 2
    assert result.companies_removed == 1
    assert result.feeds_removed == 3
    assert marked_revisions == ["rev-2"]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_sync_rss_catalog_force_reconciles_even_when_revision_already_applied(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_rss_catalog_sync_state",
        lambda _db: SimpleNamespace(last_applied_revision="rev-2"),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="up_to_date",
            repository_path=str(repository_path),
            previous_revision="rev-2",
            current_revision="rev-2",
        ),
    )

    reconcile_calls: list[Path] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "_reconcile_rss_catalog",
        lambda db, repository_path: (
            reconcile_calls.append(repository_path)
            or rss_sync_service_module._CatalogReconcileResult(files_processed=1)
        ),
    )
    monkeypatch.setattr(rss_sync_service_module, "mark_rss_catalog_sync_success", lambda db, current_revision: None)

    result = rss_sync_service_module.sync_rss_catalog(db, force=True)

    assert result.mode == "full_reconcile"
    assert result.files_processed == 1
    assert reconcile_calls == [repository_path]


def test_sync_rss_catalog_persists_failure_state_and_raises(monkeypatch) -> None:
    db = Mock(spec=Session)
    repository_path = Path("/tmp/rss_feeds")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_rss_catalog_sync_state",
        lambda _db: SimpleNamespace(last_applied_revision="rev-1"),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            previous_revision="rev-1",
            current_revision="rev-2",
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "_reconcile_rss_catalog",
        lambda db, repository_path: (_ for _ in ()).throw(ValueError("boom")),
    )

    failure_calls: list[tuple[str | None, str]] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "_persist_catalog_sync_failure",
        lambda db, current_revision, error_message: failure_calls.append((current_revision, error_message)),
    )

    with pytest.raises(ValueError, match="boom"):
        rss_sync_service_module.sync_rss_catalog(db)

    assert failure_calls == [("rev-2", "boom")]
    db.rollback.assert_called_once()


def test_reconcile_rss_catalog_prunes_unseen_companies(monkeypatch, tmp_path: Path) -> None:
    db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    (repository_path / "json").mkdir(parents=True)

    monkeypatch.setattr(
        rss_sync_service_module,
        "list_files_on_dir_with_ext",
        lambda repository_path, file_extension: ["Le_Monde.json"],
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "_sync_catalog_file",
        lambda db, catalog_repository_path, relative_json_file_path: (5, 1),
    )
    monkeypatch.setattr(rss_sync_service_module, "list_rss_company_ids_with_feeds", lambda db: [5, 7])

    prune_calls: list[tuple[int, set[str]]] = []
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        lambda db, company_id, expected_urls: prune_calls.append((company_id, expected_urls)) or 4,
    )
    monkeypatch.setattr(rss_sync_service_module, "delete_rss_companies_without_feeds", lambda db: 1)

    result = rss_sync_service_module._reconcile_rss_catalog(
        db,
        repository_path=repository_path,
    )

    assert result.files_processed == 1
    assert result.companies_removed == 1
    assert result.feeds_removed == 5
    assert prune_calls == [(7, set())]


def test_reconcile_rss_catalog_flushes_before_cleanup_queries(monkeypatch, tmp_path: Path) -> None:
    db = Mock(spec=Session)
    repository_path = tmp_path / "rss_feeds"
    (repository_path / "json").mkdir(parents=True)

    monkeypatch.setattr(
        rss_sync_service_module,
        "list_files_on_dir_with_ext",
        lambda repository_path, file_extension: ["Le_Monde.json"],
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "_sync_catalog_file",
        lambda db, catalog_repository_path, relative_json_file_path: (5, 0),
    )

    def fake_list_company_ids(db):
        assert db.flush.call_count == 1
        return [5]

    def fake_delete_companies_without_feeds(db):
        assert db.flush.call_count == 2
        return 0

    monkeypatch.setattr(
        rss_sync_service_module,
        "list_rss_company_ids_with_feeds",
        fake_list_company_ids,
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_rss_companies_without_feeds",
        fake_delete_companies_without_feeds,
    )

    result = rss_sync_service_module._reconcile_rss_catalog(
        db,
        repository_path=repository_path,
    )

    assert result.files_processed == 1
    assert result.companies_removed == 0
    assert result.feeds_removed == 0


def test_sync_catalog_file_upserts_feeds_and_links_company(monkeypatch, tmp_path: Path) -> None:
    db = Mock(spec=Session)
    catalog_repository_path = tmp_path / "rss_feeds" / "json"
    catalog_repository_path.mkdir(parents=True)
    (catalog_repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")

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

    delete_calls: list[tuple[int, set[str]]] = []

    def fake_delete_company_feeds_not_in_urls(db, company_id, expected_urls):
        assert db.flush.call_count == 1
        delete_calls.append((company_id, expected_urls))
        return 2

    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        fake_delete_company_feeds_not_in_urls,
    )

    company_id, feeds_removed = rss_sync_service_module._sync_catalog_file(
        db=db,
        catalog_repository_path=catalog_repository_path,
        relative_json_file_path="Le_Monde.json",
    )

    assert company_id == 5
    assert feeds_removed == 2
    assert normalize_calls == [
        "https://example.com/rss/main",
        "https://example.com/rss/ai",
    ]
    assert upserted_urls == [
        "https://example.com/rss/main",
        "https://example.com/rss/ai",
    ]
    assert link_calls == [(5, 11), (5, 12)]
    assert delete_calls == [(5, {"https://example.com/rss/main", "https://example.com/rss/ai"})]
