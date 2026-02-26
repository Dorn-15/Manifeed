import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

import app.clients.queue.redis_queue_client as redis_queue_client_module
from app.errors.db_manager_exceptions import DBManagerQueueError


def test_ensure_consumer_groups_ignores_busygroup(monkeypatch) -> None:
    calls: list[tuple[str, str, str, bool]] = []

    class FakeRedis:
        async def xgroup_create(self, stream_name, group_name, id, mkstream):  # noqa: A002
            calls.append((stream_name, group_name, id, mkstream))
            raise ResponseError("BUSYGROUP Consumer Group name already exists")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_GROUP_DB_MANAGER", "db_manager_group")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    asyncio.run(redis_queue_client_module.ensure_consumer_groups())

    assert len(calls) == 3


def test_ensure_consumer_groups_raises_domain_error_on_non_busygroup(monkeypatch) -> None:
    class FakeRedis:
        async def xgroup_create(self, stream_name, group_name, id, mkstream):  # noqa: A002
            raise ResponseError("ERR stream failure")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_GROUP_DB_MANAGER", "db_manager_group")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    with pytest.raises(DBManagerQueueError, match="Unable to create db_manager consumer group"):
        asyncio.run(redis_queue_client_module.ensure_consumer_groups())


def test_read_worker_results_decodes_records(monkeypatch) -> None:
    class FakeRedis:
        async def xreadgroup(self, group_name, consumer_name, streams, count, block):
            return [
                (b"rss_check_results", [(b"1-0", {b"payload": b'{"job_id":"job-1","feed_id":1}'})]),
                (
                    "rss_ingest_results",
                    [("2-0", {"payload": '{"job_id":"job-2","feed_id":2}'})],
                ),
            ]

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_GROUP_DB_MANAGER", "db_manager_group")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_CONSUMER_NAME", "db_manager_1")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    results = asyncio.run(redis_queue_client_module.read_worker_results(count=5, block_ms=3000))

    assert results == [
        ("rss_check_results", "1-0", {"job_id": "job-1", "feed_id": 1}),
        ("rss_ingest_results", "2-0", {"job_id": "job-2", "feed_id": 2}),
    ]


def test_read_worker_results_raises_on_invalid_json(monkeypatch) -> None:
    class FakeRedis:
        async def xreadgroup(self, group_name, consumer_name, streams, count, block):
            return [
                (b"rss_check_results", [(b"1-0", {b"payload": b"not-json"})]),
            ]

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_GROUP_DB_MANAGER", "db_manager_group")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_CONSUMER_NAME", "db_manager_1")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    with pytest.raises(DBManagerQueueError, match="Invalid result payload"):
        asyncio.run(redis_queue_client_module.read_worker_results())


def test_ack_worker_result_uses_group_name(monkeypatch) -> None:
    xack_calls: list[tuple[str, str, str]] = []

    class FakeRedis:
        async def xack(self, stream_name, group_name, message_id):
            xack_calls.append((stream_name, group_name, message_id))

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "DEFAULT_REDIS_GROUP_DB_MANAGER", "db_manager_group")

    asyncio.run(redis_queue_client_module.ack_worker_result("rss_check_results", "1-0"))

    assert xack_calls == [("rss_check_results", "db_manager_group", "1-0")]


def test_read_worker_results_recreates_groups_on_nogroup(monkeypatch) -> None:
    ensure_calls: list[str] = []

    class FakeRedis:
        async def xreadgroup(self, group_name, consumer_name, streams, count, block):
            raise ResponseError("NOGROUP No such key")

    async def fake_ensure_consumer_groups() -> None:
        ensure_calls.append("called")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "ensure_consumer_groups", fake_ensure_consumer_groups)

    results = asyncio.run(redis_queue_client_module.read_worker_results())

    assert results == []
    assert ensure_calls == ["called"]


def test_ack_worker_result_retries_after_connection_drop(monkeypatch) -> None:
    xack_attempts: list[int] = []
    close_calls: list[str] = []

    class FakeRedis:
        async def xack(self, stream_name, group_name, message_id):
            xack_attempts.append(1)
            if len(xack_attempts) == 1:
                raise RedisConnectionError("Connection closed by server.")

        async def aclose(self) -> None:
            close_calls.append("closed")

    fake_redis = FakeRedis()

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: fake_redis)

    asyncio.run(redis_queue_client_module.ack_worker_result("rss_check_results", "1-0"))

    assert len(xack_attempts) == 2
    assert close_calls == ["closed"]
