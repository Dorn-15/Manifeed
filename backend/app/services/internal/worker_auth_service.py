from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import jwt
from fastapi import HTTPException

from app.schemas.internal import WorkerTokenRead, WorkerTokenRequestSchema

DEFAULT_WORKER_ID = "worker_rss_scrapper"
DEFAULT_WORKER_SECRET = "change-me"
DEFAULT_WORKER_TOKEN_TTL_SECONDS = 3600


def issue_worker_access_token(payload: WorkerTokenRequestSchema) -> WorkerTokenRead:
    credentials = _resolve_worker_credentials()
    expected_secret = credentials.get(payload.worker_id)
    if expected_secret is None or expected_secret != payload.worker_secret:
        raise HTTPException(status_code=401, detail="Invalid worker credentials")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=_resolve_token_ttl_seconds())
    token_payload = {
        "sub": payload.worker_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "scope": "worker",
    }
    token = jwt.encode(
        token_payload,
        _resolve_worker_token_secret(),
        algorithm="HS256",
    )
    return WorkerTokenRead(access_token=token, expires_at=expires_at)


def _resolve_worker_credentials() -> dict[str, str]:
    credentials_env = os.getenv("WORKER_CREDENTIALS", "").strip()
    if credentials_env:
        credentials: dict[str, str] = {}
        for chunk in credentials_env.split(","):
            item = chunk.strip()
            if not item or ":" not in item:
                continue
            worker_id, worker_secret = item.split(":", 1)
            resolved_worker_id = worker_id.strip()
            resolved_worker_secret = worker_secret.strip()
            if resolved_worker_id and resolved_worker_secret:
                credentials[resolved_worker_id] = resolved_worker_secret
        if credentials:
            return credentials

    return {
        os.getenv("WORKER_ID", DEFAULT_WORKER_ID): os.getenv(
            "WORKER_SECRET",
            DEFAULT_WORKER_SECRET,
        )
    }


def _resolve_worker_token_secret() -> str:
    return os.getenv("WORKER_TOKEN_SECRET", "manifeed-worker-token-secret")


def _resolve_token_ttl_seconds() -> int:
    raw_ttl = os.getenv("WORKER_TOKEN_TTL_SECONDS", str(DEFAULT_WORKER_TOKEN_TTL_SECONDS))
    try:
        ttl_seconds = int(raw_ttl)
    except ValueError:
        return DEFAULT_WORKER_TOKEN_TTL_SECONDS
    return max(60, ttl_seconds)
