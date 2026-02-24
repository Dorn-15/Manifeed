import importlib

from app.errors.rss import RssIconNotFoundError
from app.services.health import health_service

rss_router_module = importlib.import_module("app.routers.rss_router")


def test_health_endpoint_happy_path(client, monkeypatch) -> None:
    monkeypatch.setattr(health_service, "check_db_connection", lambda _db: True)

    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_rss_icon_not_found_is_mapped_by_exception_handler(client, monkeypatch) -> None:
    monkeypatch.setattr(
        rss_router_module,
        "get_rss_icon_file_path",
        lambda icon_url: (_ for _ in ()).throw(RssIconNotFoundError("missing icon")),
    )

    response = client.get("/rss/img/missing/icon.svg")

    assert response.status_code == 404
    assert response.json() == {"message": "missing icon"}
