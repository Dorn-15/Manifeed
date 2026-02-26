from __future__ import annotations

import json
import os
from typing import Any

from redis.asyncio import Redis

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_REDIS_QUEUE_REQUESTS = "rss_scrape_requests"

_redis_client: Redis | None = None


def get_requests_stream_name() -> str:
    return os.getenv("REDIS_QUEUE_REQUESTS", DEFAULT_REDIS_QUEUE_REQUESTS)


async def publish_rss_scrape_job(payload: dict[str, Any]) -> str:
    redis_client = _get_redis_client()
    stream_name = get_requests_stream_name()
    message_id = await redis_client.xadd(
        stream_name,
        {"payload": json.dumps(payload)},
    )
    if isinstance(message_id, bytes):
        return message_id.decode("utf-8")
    return str(message_id)


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
        _redis_client = Redis.from_url(redis_url, decode_responses=False)
    return _redis_client
