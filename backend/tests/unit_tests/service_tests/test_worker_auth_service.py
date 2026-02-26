from datetime import datetime, timezone

from fastapi import HTTPException
import jwt
import pytest

import app.services.internal.worker_auth_service as worker_auth_service_module
from app.schemas.internal import WorkerTokenRequestSchema


def test_issue_worker_access_token_returns_signed_token(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_credentials",
        lambda: {"worker_rss_scrapper": "secret"},
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_token_secret",
        lambda: "token-secret",
    )
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_token_ttl_seconds",
        lambda: 3600,
    )

    result = worker_auth_service_module.issue_worker_access_token(
        WorkerTokenRequestSchema(
            worker_id="worker_rss_scrapper",
            worker_secret="secret",
        )
    )

    decoded = jwt.decode(result.access_token, "token-secret", algorithms=["HS256"])
    assert decoded["sub"] == "worker_rss_scrapper"
    assert isinstance(result.expires_at, datetime)
    assert result.expires_at.tzinfo == timezone.utc


def test_issue_worker_access_token_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        worker_auth_service_module,
        "_resolve_worker_credentials",
        lambda: {"worker_rss_scrapper": "secret"},
    )

    with pytest.raises(HTTPException) as exception_info:
        worker_auth_service_module.issue_worker_access_token(
            WorkerTokenRequestSchema(
                worker_id="worker_rss_scrapper",
                worker_secret="wrong",
            )
        )

    assert exception_info.value.status_code == 401
