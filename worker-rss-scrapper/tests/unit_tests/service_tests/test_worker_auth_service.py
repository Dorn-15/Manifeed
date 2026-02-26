import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.errors.worker_exceptions import WorkerAuthenticationError
import app.services.worker_auth_service as worker_auth_service_module


def test_ensure_worker_authenticated_uses_cached_token(monkeypatch) -> None:
    worker_auth_service_module._cached_token = "cached-token"
    worker_auth_service_module._cached_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    async def fake_request_worker_token(*, worker_id, worker_secret):
        raise AssertionError("request_worker_token must not be called when cache is valid")

    monkeypatch.setattr(worker_auth_service_module, "request_worker_token", fake_request_worker_token)

    token = asyncio.run(worker_auth_service_module.ensure_worker_authenticated())

    assert token == "cached-token"


def test_ensure_worker_authenticated_requests_new_token(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_ID", "worker_rss_scrapper")
    monkeypatch.setenv("WORKER_SECRET", "secret")

    async def fake_request_worker_token(*, worker_id, worker_secret):
        assert worker_id == "worker_rss_scrapper"
        assert worker_secret == "secret"
        return "new-token", datetime.now(timezone.utc) + timedelta(hours=1)

    monkeypatch.setattr(worker_auth_service_module, "request_worker_token", fake_request_worker_token)

    token = asyncio.run(worker_auth_service_module.ensure_worker_authenticated())

    assert token == "new-token"
    assert worker_auth_service_module._cached_token == "new-token"
    assert worker_auth_service_module._cached_expires_at is not None


def test_ensure_worker_authenticated_raises_on_blank_credentials(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_ID", " ")
    monkeypatch.setenv("WORKER_SECRET", " ")

    with pytest.raises(WorkerAuthenticationError, match="Worker credentials are not configured"):
        asyncio.run(worker_auth_service_module.ensure_worker_authenticated())
