from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

from app.clients.api import request_worker_token
from app.errors.worker_exceptions import WorkerAuthenticationError

DEFAULT_WORKER_ID = "worker_rss_scrapper"
DEFAULT_WORKER_SECRET = "change-me"
_TOKEN_REFRESH_BUFFER = timedelta(seconds=60)

_cached_token: str | None = None
_cached_expires_at: datetime | None = None


async def ensure_worker_authenticated() -> str:
    global _cached_token
    global _cached_expires_at

    now = datetime.now(timezone.utc)
    if _cached_token and _cached_expires_at and now + _TOKEN_REFRESH_BUFFER < _cached_expires_at:
        return _cached_token

    worker_id = os.getenv("WORKER_ID", DEFAULT_WORKER_ID)
    worker_secret = os.getenv("WORKER_SECRET", DEFAULT_WORKER_SECRET)
    if not worker_id.strip() or not worker_secret.strip():
        raise WorkerAuthenticationError("Worker credentials are not configured")

    token, expires_at = await request_worker_token(
        worker_id=worker_id,
        worker_secret=worker_secret,
    )
    _cached_token = token
    _cached_expires_at = _normalize_datetime(expires_at)
    return token


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
