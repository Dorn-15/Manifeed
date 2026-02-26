import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

import app.clients.queue.redis_queue_client as redis_queue_client_module
from app.errors.worker_exceptions import WorkerQueueError


def test_ensure_worker_consumer_group_ignores_busygroup(monkeypatch) -> None:
    calls: list[tuple[str, str, str, bool]] = []

    class FakeRedis:
        async def xgroup_create(self, stream_name, group_name, id, mkstream):  # noqa: A002
            calls.append((stream_name, group_name, id, mkstream))
            raise ResponseError("BUSYGROUP Consumer Group name already exists")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(redis_queue_client_module, "REDIS_QUEUE_REQUESTS", "rss_scrape_requests")
    monkeypatch.setattr(redis_queue_client_module, "REDIS_GROUP_WORKER", "worker_rss_scrapper_group")

    asyncio.run(redis_queue_client_module.ensure_worker_consumer_group())

    assert calls == [("rss_scrape_requests", "worker_rss_scrapper_group", "$", True)]


def test_ensure_worker_consumer_group_raises_on_non_busygroup(monkeypatch) -> None:
    class FakeRedis:
        async def xgroup_create(self, stream_name, group_name, id, mkstream):  # noqa: A002
            raise ResponseError("ERR stream failure")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())

    with pytest.raises(WorkerQueueError, match="Unable to create worker consumer group"):
        asyncio.run(redis_queue_client_module.ensure_worker_consumer_group())


def test_read_scrape_jobs_decodes_records(monkeypatch) -> None:
    class FakeRedis:
        async def xreadgroup(self, group_name, consumer_name, streams, count, block):
            return [
                (b"rss_scrape_requests", [(b"1-0", {b"payload": b'{"job_id":"job-1","feeds":[]}'})]),
                ("rss_scrape_requests", [("2-0", {"payload": '{"job_id":"job-2","feeds":[]} '})]),
            ]

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())

    jobs = asyncio.run(redis_queue_client_module.read_scrape_jobs(count=5, block_ms=2000))

    assert jobs == [
        ("1-0", {"job_id": "job-1", "feeds": []}),
        ("2-0", {"job_id": "job-2", "feeds": []}),
    ]


def test_read_scrape_jobs_recreates_group_on_nogroup(monkeypatch) -> None:
    ensure_calls: list[str] = []

    class FakeRedis:
        async def xreadgroup(self, group_name, consumer_name, streams, count, block):
            raise ResponseError("NOGROUP No such key")

    async def fake_ensure_worker_consumer_group() -> None:
        ensure_calls.append("called")

    monkeypatch.setattr(redis_queue_client_module, "_get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(
        redis_queue_client_module,
        "ensure_worker_consumer_group",
        fake_ensure_worker_consumer_group,
    )

    jobs = asyncio.run(redis_queue_client_module.read_scrape_jobs())

    assert jobs == []
    assert ensure_calls == ["called"]


def test_ack_scrape_job_retries_after_connection_drop(monkeypatch) -> None:
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

    asyncio.run(redis_queue_client_module.ack_scrape_job("1-0"))

    assert len(xack_attempts) == 2
    assert close_calls == ["closed"]
