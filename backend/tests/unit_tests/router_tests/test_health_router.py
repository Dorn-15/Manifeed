import importlib

from app.schemas.health import HealthRead

health_router_module = importlib.import_module("app.routers.health_router")


def test_health_route_returns_service_payload(client, mock_db_session, monkeypatch) -> None:
    expected = HealthRead(status="ok", database="ok")

    def fake_get_health_status(db):
        assert db is mock_db_session
        return expected

    monkeypatch.setattr(health_router_module, "get_health_status", fake_get_health_status)

    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == expected.model_dump()
