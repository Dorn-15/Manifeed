from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable, TypeVar

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError

from app.errors import DBManagerQueueError

DEFAULT_REDIS_URL = "redis://redis:6379/0"
DEFAULT_REDIS_QUEUE_CHECK = "rss_check_results"
DEFAULT_REDIS_QUEUE_INGEST = "rss_ingest_results"
DEFAULT_REDIS_QUEUE_ERRORS = "error_feeds_parsing"
DEFAULT_REDIS_GROUP_DB_MANAGER = "db_manager_group"
DEFAULT_REDIS_CONSUMER_NAME = "db_manager_1"

_redis_client: Redis | None = None
_REDIS_COMMAND_MAX_ATTEMPTS = 2
_T = TypeVar("_T")

async def ensure_consumer_groups() -> None:
    group_name = DEFAULT_REDIS_GROUP_DB_MANAGER
    for stream_name in (DEFAULT_REDIS_QUEUE_CHECK, DEFAULT_REDIS_QUEUE_INGEST, DEFAULT_REDIS_QUEUE_ERRORS):
        try:
            await _run_redis_command(
                command_name="xgroup_create",
                command=lambda redis_client: redis_client.xgroup_create(
                    stream_name,
                    group_name,
                    id="$",
                    mkstream=True,
                ),
            )
        except ResponseError as exception:
            if "BUSYGROUP" not in str(exception):
                raise DBManagerQueueError(
                    f"Unable to create db_manager consumer group for stream {stream_name}: {exception}"
                ) from exception


async def read_worker_results(
    *,
    count: int = 10,
    block_ms: int = 5000,
) -> list[tuple[str, str, dict[str, Any]]]:
    group_name = DEFAULT_REDIS_GROUP_DB_MANAGER
    consumer_name = DEFAULT_REDIS_CONSUMER_NAME
    streams = {DEFAULT_REDIS_QUEUE_CHECK: ">", DEFAULT_REDIS_QUEUE_INGEST: ">", DEFAULT_REDIS_QUEUE_ERRORS: ">"}
    try:
        records = await _run_redis_command(
            command_name="xreadgroup",
            command=lambda redis_client: redis_client.xreadgroup(
                group_name,
                consumer_name,
                streams,
                count=count,
                block=block_ms,
            ),
        )
    except ResponseError as exception:
        if "NOGROUP" in str(exception):
            await ensure_consumer_groups()
            return []
        raise DBManagerQueueError(f"Unable to read worker results: {exception}") from exception

    if not records:
        return []

    results: list[tuple[str, str, dict[str, Any]]] = []
    for stream_name_raw, messages in records:
        stream_name = (
            stream_name_raw.decode("utf-8")
            if isinstance(stream_name_raw, (bytes, bytearray))
            else str(stream_name_raw)
        )
        for message_id_raw, fields in messages:
            message_id = (
                message_id_raw.decode("utf-8")
                if isinstance(message_id_raw, (bytes, bytearray))
                else str(message_id_raw)
            )
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
                raise DBManagerQueueError(f"Invalid result payload: {exception}") from exception

            results.append((stream_name, message_id, payload))
    return results


async def ack_worker_result(stream_name: str, message_id: str) -> None:
    try:
        await _run_redis_command(
            command_name="xack",
            command=lambda redis_client: redis_client.xack(
                stream_name,
                DEFAULT_REDIS_GROUP_DB_MANAGER,
                message_id,
            ),
        )
    except ResponseError as exception:
        raise DBManagerQueueError(f"Unable to ack worker result {message_id}: {exception}") from exception


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
        raise DBManagerQueueError(f"Redis command '{command_name}' failed")
    raise DBManagerQueueError(
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
