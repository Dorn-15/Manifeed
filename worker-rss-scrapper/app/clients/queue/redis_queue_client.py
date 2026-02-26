from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable, TypeVar

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError

from app.errors.worker_exceptions import WorkerQueueError

DEFAULT_REDIS_URL = "redis://redis:6379/0"
REDIS_QUEUE_REQUESTS = "rss_scrape_requests"
REDIS_QUEUE_CHECK = "rss_check_results"
REDIS_QUEUE_INGEST = "rss_ingest_results"
REDIS_QUEUE_ERRORS = "error_feeds_parsing"
REDIS_GROUP_WORKER = "worker_rss_scrapper_group"
REDIS_CONSUMER_NAME = "worker_rss_scrapper_1"

_redis_client: Redis | None = None
_REDIS_COMMAND_MAX_ATTEMPTS = 2
_T = TypeVar("_T")


async def ensure_worker_consumer_group() -> None:
    try:
        await _run_redis_command(
            command_name="xgroup_create",
            command=lambda redis_client: redis_client.xgroup_create(
                REDIS_QUEUE_REQUESTS,
                REDIS_GROUP_WORKER,
                id="$",
                mkstream=True,
            ),
        )
    except ResponseError as exception:
        if "BUSYGROUP" not in str(exception):
            raise WorkerQueueError(f"Unable to create worker consumer group: {exception}") from exception


async def read_scrape_jobs(
    *,
    count: int = 1,
    block_ms: int = 5000,
) -> list[tuple[str, dict[str, Any]]]:
    try:
        records = await _run_redis_command(
            command_name="xreadgroup",
            command=lambda redis_client: redis_client.xreadgroup(
                REDIS_GROUP_WORKER,
                REDIS_CONSUMER_NAME,
                {REDIS_QUEUE_REQUESTS: ">"},
                count=count,
                block=block_ms,
            ),
        )
    except ResponseError as exception:
        if "NOGROUP" in str(exception):
            await ensure_worker_consumer_group()
            return []
        raise WorkerQueueError(f"Unable to read scrape jobs: {exception}") from exception

    if not records:
        return []

    jobs: list[tuple[str, dict[str, Any]]] = []
    for _, messages in records:
        for message_id, fields in messages:
            payload_raw = fields.get(b"payload") or fields.get("payload")
            if payload_raw is None:
                continue
            try:
                payload_json = (
                    payload_raw.decode("utf-8")
                    if isinstance(payload_raw, (bytes, bytearray))
                    else str(payload_raw)
                )
                payload = json.loads(payload_json)
            except Exception as exception:
                raise WorkerQueueError(f"Invalid queue payload: {exception}") from exception

            resolved_message_id = (
                message_id.decode("utf-8")
                if isinstance(message_id, (bytes, bytearray))
                else str(message_id)
            )
            jobs.append((resolved_message_id, payload))
    return jobs


async def publish_check_result(payload: dict[str, Any]) -> None:
    await _publish_payload(REDIS_QUEUE_CHECK, payload)


async def publish_ingest_result(payload: dict[str, Any]) -> None:
    await _publish_payload(REDIS_QUEUE_INGEST, payload)


async def publish_error_result(payload: dict[str, Any]) -> None:
    await _publish_payload(REDIS_QUEUE_ERRORS, payload)


async def ack_scrape_job(message_id: str) -> None:
    try:
        await _run_redis_command(
            command_name="xack",
            command=lambda redis_client: redis_client.xack(
                REDIS_QUEUE_REQUESTS,
                REDIS_GROUP_WORKER,
                message_id,
            ),
        )
    except ResponseError as exception:
        raise WorkerQueueError(f"Unable to ack scrape job {message_id}: {exception}") from exception


async def _publish_payload(stream_name: str, payload: dict[str, Any]) -> None:
    try:
        await _run_redis_command(
            command_name="xadd",
            command=lambda redis_client: redis_client.xadd(
                stream_name,
                {"payload": json.dumps(payload)},
            ),
        )
    except ResponseError as exception:
        raise WorkerQueueError(f"Unable to publish result to {stream_name}: {exception}") from exception


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
        _redis_client = Redis.from_url(redis_url, decode_responses=False)
    return _redis_client


async def _run_redis_command(
    *,
    command_name: str,
    command: Callable[[Redis], Awaitable[_T]],
) -> _T:
    last_exception: Exception | None = None
    for _ in range(_REDIS_COMMAND_MAX_ATTEMPTS):
        redis_client = _get_redis_client()
        try:
            return await command(redis_client)
        except (RedisConnectionError, RedisTimeoutError) as exception:
            last_exception = exception
            await _reset_redis_client(redis_client)

    if last_exception is None:
        raise WorkerQueueError(f"Redis command '{command_name}' failed")
    raise WorkerQueueError(
        f"Redis command '{command_name}' failed after reconnect: {last_exception}"
    ) from last_exception


async def _reset_redis_client(redis_client: Redis) -> None:
    global _redis_client

    if _redis_client is redis_client:
        _redis_client = None

    try:
        await redis_client.aclose()
    except Exception:
        return
