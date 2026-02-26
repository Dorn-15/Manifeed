from __future__ import annotations

from datetime import datetime
import os

import httpx

from app.errors.worker_exceptions import WorkerAuthenticationError

DEFAULT_MANIFEED_API_URL = "http://backend:8000"


async def request_worker_token(
    *,
    worker_id: str,
    worker_secret: str,
) -> tuple[str, datetime]:
    api_url = os.getenv("MANIFEED_API_URL", DEFAULT_MANIFEED_API_URL).rstrip("/")
    endpoint = f"{api_url}/internal/workers/token"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                endpoint,
                json={
                    "worker_id": worker_id,
                    "worker_secret": worker_secret,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exception:
            raise WorkerAuthenticationError(f"Token request failed: {exception}") from exception

    payload = response.json()
    access_token = payload.get("access_token")
    expires_at_raw = payload.get("expires_at")
    if not isinstance(access_token, str) or not access_token:
        raise WorkerAuthenticationError("Token response does not contain a valid access_token")
    if not isinstance(expires_at_raw, str) or not expires_at_raw:
        raise WorkerAuthenticationError("Token response does not contain a valid expires_at")

    try:
        expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
    except ValueError as exception:
        raise WorkerAuthenticationError("Token response contains an invalid expires_at") from exception
    return access_token, expires_at
