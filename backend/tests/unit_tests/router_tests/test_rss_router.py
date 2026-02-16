import importlib
from contextlib import contextmanager

from app.utils import JobAlreadyRunning
from app.schemas.rss import (
    RssCompanyRead,
    RssFeedCheckRead,
    RssFeedCheckResultRead,
    RssFeedRead,
    RssSyncRead,
)

rss_router_module = importlib.import_module("app.routers.rss_router")


def test_sync_rss_route_returns_service_result(client, mock_db_session, monkeypatch) -> None:
    expected_response = RssSyncRead(
        repository_action="up_to_date",
    )

    def fake_sync_rss_catalog(db):
        assert db is mock_db_session
        return expected_response

    monkeypatch.setattr(rss_router_module, "sync_rss_catalog", fake_sync_rss_catalog)

    response = client.post("/rss/sync")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_get_rss_route_returns_service_result(client, mock_db_session, monkeypatch) -> None:
    expected_response = [
        RssFeedRead(
            id=1,
            url="https://example.com/rss",
            company_name="The Verge",
            section="Main",
            enabled=True,
            status="unchecked",
            trust_score=0.9,
            language="en",
            icon_url="theVerge/theVerge.svg",
        )
    ]

    def fake_get_rss_feeds(db):
        assert db is mock_db_session
        return expected_response

    monkeypatch.setattr(rss_router_module, "get_rss_feeds", fake_get_rss_feeds)

    response = client.get("/rss/")

    assert response.status_code == 200
    assert response.json() == [item.model_dump() for item in expected_response]


def test_get_rss_icon_route_returns_svg_content(client, monkeypatch, tmp_path) -> None:
    icon_path = tmp_path / "icon.svg"
    icon_path.write_text("<svg></svg>", encoding="utf-8")
    monkeypatch.setattr(
        rss_router_module,
        "get_rss_icon_file_path",
        lambda icon_url: icon_path,
    )

    response = client.get("/rss/img/theVerge/theVerge.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg></svg>"


def test_patch_feed_enabled_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssFeedRead(
        id=1,
        url="https://example.com/rss",
        company_id=10,
        company_name="The Verge",
        company_enabled=True,
        section="Main",
        enabled=False,
        status="valid",
        trust_score=0.9,
        language="en",
        icon_url="theVerge/theVerge.svg",
    )

    def fake_toggle_rss_feed_enabled(db, feed_id: int, enabled: bool):
        assert db is mock_db_session
        assert feed_id == 1
        assert enabled is False
        return expected_response

    monkeypatch.setattr(
        rss_router_module,
        "toggle_rss_feed_enabled",
        fake_toggle_rss_feed_enabled,
    )

    response = client.patch("/rss/feeds/1/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_patch_company_enabled_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssCompanyRead(
        id=10,
        name="The Verge",
        enabled=False,
    )

    def fake_toggle_rss_company_enabled(db, company_id: int, enabled: bool):
        assert db is mock_db_session
        assert company_id == 10
        assert enabled is False
        return expected_response

    monkeypatch.setattr(
        rss_router_module,
        "toggle_rss_company_enabled",
        fake_toggle_rss_company_enabled,
    )

    response = client.patch("/rss/companies/10/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_check_rss_feeds_route_returns_service_result(
    client,
    mock_db_session,
    monkeypatch,
) -> None:
    expected_response = RssFeedCheckRead(
        valid_count=3,
        invalid_count=1,
        results=[
            RssFeedCheckResultRead(
                feed_id=7,
                url="https://example.com/rss/7",
                status="invalid",
                error="Request timeout",
            )
        ],
    )

    async def fake_check_rss_feeds(db, feed_ids):
        assert db is mock_db_session
        assert feed_ids == [7, 9]
        return expected_response

    monkeypatch.setattr(
        rss_router_module,
        "check_rss_feeds",
        fake_check_rss_feeds,
    )

    response = client.post("/rss/feeds/check?feed_ids=7&feed_ids=9")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_sync_route_returns_409_when_job_lock_is_busy(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("rss_sync")
        yield

    monkeypatch.setattr(rss_router_module, "job_lock", busy_job_lock)

    response = client.post("/rss/sync")

    assert response.status_code == 409
    assert response.json() == {"message": "RSS sync already running"}


def test_patch_feed_route_returns_409_when_job_lock_is_busy(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("rss_patch_feed_enabled")
        yield

    monkeypatch.setattr(rss_router_module, "job_lock", busy_job_lock)

    response = client.patch("/rss/feeds/1/enabled", json={"enabled": False})

    assert response.status_code == 409
    assert response.json() == {"message": "RSS feed toggle already running"}
