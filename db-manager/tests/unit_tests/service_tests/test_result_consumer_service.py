import asyncio
from unittest.mock import Mock

import app.services.result_consumer_service as result_consumer_service_module


def _valid_worker_payload() -> dict:
    return {
        "job_id": "job-1",
        "ingest": False,
        "feed_id": 10,
        "feed_url": "https://example.com/rss.xml",
        "status": "success",
        "error_message": None,
        "new_etag": "etag-1",
        "new_last_update": "2026-02-26T12:00:00Z",
        "fetchprotection": 1,
        "sources": [],
    }


def test_process_result_message_acks_invalid_payload(monkeypatch) -> None:
    acked_messages: list[tuple[str, str]] = []

    async def fake_ack_worker_result(stream_name: str, message_id: str) -> None:
        acked_messages.append((stream_name, message_id))

    monkeypatch.setattr(result_consumer_service_module, "ack_worker_result", fake_ack_worker_result)
    monkeypatch.setattr(
        result_consumer_service_module,
        "get_db_session",
        lambda: (_ for _ in ()).throw(AssertionError("db session must not be requested")),
    )

    asyncio.run(
        result_consumer_service_module._process_result_message(
            stream_name="rss_check_results",
            message_id="1-0",
            payload_raw={"invalid": "payload"},
        )
    )

    assert acked_messages == [("rss_check_results", "1-0")]


def test_process_result_message_commits_and_acks_on_success(monkeypatch) -> None:
    acked_messages: list[tuple[str, str]] = []
    captured_queue_kind: list[str] = []
    db = Mock()

    async def fake_ack_worker_result(stream_name: str, message_id: str) -> None:
        acked_messages.append((stream_name, message_id))

    def fake_persist_worker_result(db_session, *, payload, queue_kind):
        captured_queue_kind.append(queue_kind)
        assert payload.job_id == "job-1"
        return True

    monkeypatch.setattr(result_consumer_service_module, "ack_worker_result", fake_ack_worker_result)
    monkeypatch.setattr(result_consumer_service_module, "persist_worker_result", fake_persist_worker_result)
    monkeypatch.setattr(result_consumer_service_module, "get_db_session", lambda: db)
    monkeypatch.setattr(result_consumer_service_module, "resolve_queue_kind", lambda *_args, **_kwargs: "check")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    asyncio.run(
        result_consumer_service_module._process_result_message(
            stream_name="rss_check_results",
            message_id="2-0",
            payload_raw=_valid_worker_payload(),
        )
    )

    assert captured_queue_kind == ["check"]
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()
    assert acked_messages == [("rss_check_results", "2-0")]


def test_process_result_message_rolls_back_without_ack_when_persist_fails(monkeypatch) -> None:
    acked_messages: list[tuple[str, str]] = []
    db = Mock()

    async def fake_ack_worker_result(stream_name: str, message_id: str) -> None:
        acked_messages.append((stream_name, message_id))

    def fake_persist_worker_result(db_session, *, payload, queue_kind):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(result_consumer_service_module, "ack_worker_result", fake_ack_worker_result)
    monkeypatch.setattr(result_consumer_service_module, "persist_worker_result", fake_persist_worker_result)
    monkeypatch.setattr(result_consumer_service_module, "get_db_session", lambda: db)
    monkeypatch.setattr(result_consumer_service_module, "resolve_queue_kind", lambda *_args, **_kwargs: "error")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_CHECK", "rss_check_results")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_INGEST", "rss_ingest_results")
    monkeypatch.setattr(result_consumer_service_module, "DEFAULT_REDIS_QUEUE_ERRORS", "error_feeds_parsing")

    asyncio.run(
        result_consumer_service_module._process_result_message(
            stream_name="error_feeds_parsing",
            message_id="3-0",
            payload_raw=_valid_worker_payload(),
        )
    )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()
    assert acked_messages == []
