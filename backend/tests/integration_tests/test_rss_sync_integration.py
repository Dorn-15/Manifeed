from pathlib import Path
from types import SimpleNamespace

import app.services.rss.rss_sync_service as rss_sync_service_module
from app.utils.git_repository_utils import GitRepositorySyncError
from app.schemas.rss import RssRepositorySyncRead, RssSourceCatalogSchema, RssSourceFeedSchema


def test_rss_sync_endpoint_happy_path(client, mock_db_session, monkeypatch, tmp_path: Path) -> None:
    repository_path = tmp_path / "rss_feeds"
    repository_path.mkdir()
    (repository_path / "Le_Monde.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(rss_sync_service_module, "get_rss_feeds_repository_path", lambda: repository_path)
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch, force=False: RssRepositorySyncRead(
            action="update",
            repository_path=str(repository_path),
            changed_files=["Le_Monde.json"],
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "load_source_feeds_from_json",
        lambda path: RssSourceCatalogSchema(
            company="Le Monde",
            host="www.lemonde.fr",
            img="icons/lemonde.svg",
            country="fr",
            language="fr",
            fetchprotection=1,
            feeds=[
                RssSourceFeedSchema(
                    url="https://example.com/rss/main",
                    title="Main",
                    tags=["tech"],
                    enabled=True,
                    trust_score=0.9,
                    fetchprotection=1,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_company",
        lambda db, company_name, **kwargs: (
            SimpleNamespace(id=1, fetchprotection=kwargs.get("fetchprotection", 1)),
            True,
        ),
    )
    monkeypatch.setattr(rss_sync_service_module, "list_rss_feeds_by_urls", lambda db, urls: {})
    monkeypatch.setattr(rss_sync_service_module, "get_or_create_tags", lambda db, tags: ([object()], True))
    monkeypatch.setattr(
        rss_sync_service_module,
        "upsert_feed",
        lambda db, payload, tags, existing_feed=None: (SimpleNamespace(id=5, url=payload.url), True),
    )
    monkeypatch.setattr(rss_sync_service_module, "link_company_to_feed", lambda db, company_id, feed_id: True)
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        lambda db, company_id, expected_urls: 0,
    )

    response = client.post("/rss/sync")

    assert response.status_code == 200
    assert response.json() == {"repository_action": "update"}
    mock_db_session.commit.assert_called_once()


def test_rss_sync_endpoint_maps_git_error_to_502(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch, force=False: (_ for _ in ()).throw(
            GitRepositorySyncError("fetch failed")
        ),
    )

    response = client.post("/rss/sync")

    assert response.status_code == 502
    assert response.json() == {"message": "RSS repository sync failed"}
