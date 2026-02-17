import importlib
from pathlib import Path
from types import SimpleNamespace

import app.services.rss.rss_feed_service as rss_feed_service_module
import app.services.rss.rss_icon_service as rss_icon_service_module
import app.services.rss.rss_sync_service as rss_sync_service_module
import app.services.rss.rss_toggle_service as rss_toggle_service_module
rss_router_module = importlib.import_module("app.routers.rss_router")
sources_router_module = importlib.import_module("app.routers.sources_router")
from app.errors.rss import RssIconNotFoundError
from app.utils.git_repository_utils import GitRepositorySyncError
from app.schemas.rss import (
    RssCompanyRead,
    RssFeedCheckRead,
    RssFeedCheckResultRead,
    RssFeedRead,
    RssSourceFeedSchema,
    RssRepositorySyncRead,
)
from app.schemas.sources import RssSourceIngestRead, RssSourcePageRead, RssSourceRead


def test_rss_sync_endpoint_happy_path(
    client,
    mock_db_session,
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        lambda _: [
            RssSourceFeedSchema(
                url="https://example.com/rss/main",
                title="Main",
                tags=["tech"],
                trust_score=0.9,
                language="fr",
                enabled=True,
                img="icons/main.svg",
                parsing_config={},
            )
        ],
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_company",
        lambda db, company_name: (SimpleNamespace(id=1), True),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "list_rss_feeds_by_urls",
        lambda db, urls: {},
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "get_or_create_tags",
        lambda db, tag_names: ([object()], 1),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "upsert_feed",
        lambda db, company, payload, tags, existing_feed=None: (object(), True),
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "delete_company_feeds_not_in_urls",
        lambda db, company_id, expected_urls: 0,
    )

    response = client.post("/rss/sync")

    assert response.status_code == 200
    assert response.json()["repository_action"] == "update"
    assert response.json()["processed_files"] == 1
    assert response.json()["processed_feeds"] == 1
    assert response.json()["created_feeds"] == 1
    mock_db_session.commit.assert_called_once()


def test_rss_sync_endpoint_repository_error_is_mapped_to_502(
    client,
    monkeypatch,
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "rss_feeds"
    monkeypatch.setattr(
        rss_sync_service_module,
        "resolve_rss_feeds_repository_path",
        lambda: repository_path,
    )
    monkeypatch.setattr(
        rss_sync_service_module,
        "sync_rss_feeds_repository",
        lambda repository_url, repository_path, branch: (_ for _ in ()).throw(
            GitRepositorySyncError("fetch failed")
        ),
    )

    response = client.post("/rss/sync")

    assert response.status_code == 502
    assert response.json() == {"message": "RSS repository sync failed"}


def test_rss_list_endpoint_happy_path(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_feed_service_module,
        "list_rss_feeds_read",
        lambda _db: [
            RssFeedRead(
                id=1,
                url="https://example.com/rss",
                company_id=10,
                company_name="The Verge",
                company_enabled=True,
                section="Main",
                enabled=True,
                status="unchecked",
                trust_score=0.95,
                language="en",
                icon_url="theVerge/theVerge.svg",
            )
        ],
    )

    response = client.get("/rss/")

    assert response.status_code == 200
    assert response.json() == [
        RssFeedRead(
            id=1,
            url="https://example.com/rss",
            company_id=10,
            company_name="The Verge",
            company_enabled=True,
            section="Main",
            enabled=True,
            status="unchecked",
            trust_score=0.95,
            language="en",
            icon_url="theVerge/theVerge.svg",
        ).model_dump()
    ]


def test_rss_icon_endpoint_not_found_is_mapped_to_404(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_icon_service_module,
        "resolve_rss_icon_file_path",
        lambda repository_path, icon_url: (_ for _ in ()).throw(
            RssIconNotFoundError("Icon not found")
        ),
    )

    response = client.get("/rss/img/theVerge/theVerge.svg")

    assert response.status_code == 404
    assert response.json() == {"message": "Icon not found"}


def test_rss_toggle_feed_endpoint_happy_path(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_toggle_service_module,
        "set_rss_feed_enabled",
        lambda _db, feed_id, enabled: True,
    )
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, feed_id: RssFeedRead(
            id=feed_id,
            url="https://example.com/rss",
            company_id=10,
            company_name="The Verge",
            company_enabled=True,
            section="Main",
            enabled=True,
            status="valid",
            trust_score=0.95,
            language="en",
            icon_url="theVerge/theVerge.svg",
        ),
    )

    response = client.patch("/rss/feeds/1/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert response.json()["enabled"] is False
    assert response.json()["company_enabled"] is True


def test_rss_toggle_company_endpoint_happy_path(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_company_by_id",
        lambda db, company_id: SimpleNamespace(
            id=company_id,
            name="The Verge",
            enabled=True,
        ),
    )

    response = client.patch("/rss/companies/10/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == RssCompanyRead(id=10, name="The Verge", enabled=False).model_dump()


def test_rss_toggle_feed_endpoint_returns_409_on_business_rule_violation(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, feed_id: RssFeedRead(
            id=feed_id,
            url="https://example.com/rss",
            company_id=10,
            company_name="The Verge",
            company_enabled=False,
            section="Main",
            enabled=True,
            status="valid",
            trust_score=0.95,
            language="en",
            icon_url="theVerge/theVerge.svg",
        ),
    )

    response = client.patch("/rss/feeds/1/enabled", json={"enabled": False})

    assert response.status_code == 409
    assert response.json() == {
        "message": "Cannot toggle feed 1: company 'The Verge' is disabled"
    }


def test_rss_toggle_feed_endpoint_returns_404_when_feed_is_missing(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        rss_toggle_service_module,
        "get_rss_feed_read_by_id",
        lambda _db, _feed_id: None,
    )

    response = client.patch("/rss/feeds/1/enabled", json={"enabled": False})

    assert response.status_code == 404
    assert response.json() == {"message": "RSS feed 1 not found"}


def test_rss_check_endpoint_happy_path(client, mock_db_session, monkeypatch) -> None:
    expected_response = RssFeedCheckRead(
        valid_count=2,
        invalid_count=1,
        results=[
            RssFeedCheckResultRead(
                feed_id=4,
                url="https://example.com/rss/4",
                status="invalid",
                error="Request timeout",
            )
        ],
    )

    async def fake_check_rss_feeds(db, feed_ids=None):
        assert db is mock_db_session
        assert feed_ids is None
        return expected_response

    monkeypatch.setattr(rss_router_module, "check_rss_feeds", fake_check_rss_feeds)

    response = client.post("/rss/feeds/check")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_rss_ingest_sources_endpoint_happy_path(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssSourceIngestRead(
        status="completed",
        feeds_processed=1,
        feeds_skipped=0,
        sources_created=2,
        sources_updated=1,
        duration_ms=50,
    )

    async def fake_ingest_rss_sources(db, feed_ids=None):
        assert db is mock_db_session
        assert feed_ids == [1]
        return expected_response

    monkeypatch.setattr(sources_router_module, "ingest_rss_sources", fake_ingest_rss_sources)

    response = client.post("/sources/ingest", json={"feed_ids": [1]})

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_rss_sources_list_endpoint_happy_path(client, mock_db_session, monkeypatch) -> None:
    expected_payload = RssSourcePageRead(
        items=[
            RssSourceRead(
                id=1,
                title="Source 1",
                summary="Summary 1",
                url="https://example.com/source-1",
                image_url=None,
                company_name="The Verge",
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )

    def fake_get_rss_sources(db, limit, offset):
        assert db is mock_db_session
        assert limit == 50
        assert offset == 0
        return expected_payload

    monkeypatch.setattr(sources_router_module, "get_rss_sources", fake_get_rss_sources)

    response = client.get("/sources/")

    assert response.status_code == 200
    assert response.json() == expected_payload.model_dump(mode="json")
