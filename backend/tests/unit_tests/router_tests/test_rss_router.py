import importlib
from contextlib import contextmanager
from fastapi.responses import FileResponse

from app.schemas.rss import (
    RssCompanyEnabledToggleRead,
    RssFeedCheckResultRead,
    RssFeedEnabledToggleRead,
    RssFeedRead,
    RssSyncRead,
)
from app.utils import JobAlreadyRunning

rss_router_module = importlib.import_module("app.routers.rss_router")


@contextmanager
def _no_op_job_lock(_db, _name):
    yield


def test_read_rss_feeds_returns_service_payload(client, mock_db_session, monkeypatch) -> None:
    expected = [
        RssFeedRead(
            id=1,
            url="https://example.com/rss",
            section="Main",
            enabled=True,
            trust_score=0.9,
            fetchprotection=1,
            company=None,
        )
    ]

    monkeypatch.setattr(rss_router_module, "get_rss_feeds_read", lambda db: expected)

    response = client.get("/rss/")

    assert response.status_code == 200
    assert response.json() == [item.model_dump() for item in expected]


def test_sync_rss_route_passes_force_parameter(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(rss_router_module, "job_lock", _no_op_job_lock)

    def fake_sync_rss_catalog(db, force=False):
        assert db is mock_db_session
        assert force is True
        return RssSyncRead(repository_action="up_to_date")

    monkeypatch.setattr(rss_router_module, "sync_rss_catalog", fake_sync_rss_catalog)

    response = client.post("/rss/sync?force=true")

    assert response.status_code == 200
    assert response.json() == {"repository_action": "up_to_date"}


def test_patch_feed_enabled_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(rss_router_module, "job_lock", _no_op_job_lock)

    def fake_toggle_rss_feed_enabled(db, feed_id, enabled):
        assert db is mock_db_session
        assert feed_id == 5
        assert enabled is False
        return RssFeedEnabledToggleRead(feed_id=5, enabled=False)

    monkeypatch.setattr(rss_router_module, "toggle_rss_feed_enabled", fake_toggle_rss_feed_enabled)

    response = client.patch("/rss/feeds/5/enabled", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == {"feed_id": 5, "enabled": False}


def test_patch_company_enabled_route_delegates_to_service(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(rss_router_module, "job_lock", _no_op_job_lock)

    def fake_toggle_rss_company_enabled(db, company_id, enabled):
        assert db is mock_db_session
        assert company_id == 2
        assert enabled is True
        return RssCompanyEnabledToggleRead(company_id=2, enabled=True)

    monkeypatch.setattr(rss_router_module, "toggle_rss_company_enabled", fake_toggle_rss_company_enabled)

    response = client.patch("/rss/companies/2/enabled", json={"enabled": True})

    assert response.status_code == 200
    assert response.json() == {"company_id": 2, "enabled": True}


def test_check_rss_feeds_route_passes_feed_ids(client, mock_db_session, monkeypatch) -> None:
    monkeypatch.setattr(rss_router_module, "job_lock", _no_op_job_lock)

    async def fake_check_rss_feeds(db, feed_ids):
        assert db is mock_db_session
        assert feed_ids == [7, 8]
        return [
            RssFeedCheckResultRead(
                feed_id=8,
                url="https://example.com/rss/8",
                status="invalid",
                error="timeout",
                fetchprotection=0,
            )
        ]

    monkeypatch.setattr(rss_router_module, "check_rss_feeds", fake_check_rss_feeds)

    response = client.post("/rss/feeds/check?feed_ids=7&feed_ids=8")

    assert response.status_code == 200
    assert response.json() == [
        {
            "feed_id": 8,
            "url": "https://example.com/rss/8",
            "status": "invalid",
            "error": "timeout",
            "fetchprotection": 0,
        }
    ]


def test_sync_rss_route_returns_409_when_job_is_running(client, monkeypatch) -> None:
    @contextmanager
    def busy_job_lock(_db, _name):
        raise JobAlreadyRunning("rss_sync")
        yield

    monkeypatch.setattr(rss_router_module, "job_lock", busy_job_lock)

    response = client.post("/rss/sync")

    assert response.status_code == 409
    assert response.json() == {"message": "RSS sync already running"}


def test_patch_feed_enabled_returns_422_for_invalid_payload(client) -> None:
    response = client.patch("/rss/feeds/5/enabled", json={})

    assert response.status_code == 422


def test_read_rss_icon_returns_svg_file(client, monkeypatch, tmp_path) -> None:
    icon_file = tmp_path / "icon.svg"
    icon_file.write_text("<svg></svg>", encoding="utf-8")

    monkeypatch.setattr(
        rss_router_module,
        "get_rss_icon_file_path",
        lambda icon_url: FileResponse(
            path=icon_file,
            media_type="image/svg+xml",
            filename=icon_file.name,
        ),
    )

    response = client.get("/rss/img/example/icon.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text == "<svg></svg>"
