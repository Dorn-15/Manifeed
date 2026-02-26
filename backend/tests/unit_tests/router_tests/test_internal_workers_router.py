import importlib

from app.schemas.internal import WorkerTokenRead

internal_workers_router_module = importlib.import_module("app.routers.internal_workers_router")


def test_issue_worker_token_route_delegates_to_service(client, monkeypatch) -> None:
    expected = WorkerTokenRead(
        access_token="token-value",
        expires_at="2026-02-26T13:00:00Z",
    )

    def fake_issue_worker_access_token(payload):
        assert payload.worker_id == "worker_rss_scrapper"
        assert payload.worker_secret == "secret"
        return expected

    monkeypatch.setattr(
        internal_workers_router_module,
        "issue_worker_access_token",
        fake_issue_worker_access_token,
    )

    response = client.post(
        "/internal/workers/token",
        json={"worker_id": "worker_rss_scrapper", "worker_secret": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
