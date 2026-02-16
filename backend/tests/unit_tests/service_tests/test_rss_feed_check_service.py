import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_feed_check_service as rss_feed_check_service_module


def test_check_rss_feeds_returns_empty_response_when_no_feed(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_feed_check_service_module,
        "list_rss_feeds_for_check",
        lambda _db, feed_ids=None: [],
    )

    response = asyncio.run(rss_feed_check_service_module.check_rss_feeds(db))

    assert response.valid_count == 0
    assert response.invalid_count == 0
    assert response.results == []
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_check_rss_feeds_returns_only_invalid_entries_in_results(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        SimpleNamespace(
            id=1,
            url="https://example.com/rss/valid",
            enabled=True,
            status="unchecked",
            last_update=None,
        ),
        SimpleNamespace(
            id=2,
            url="https://example.com/rss/invalid",
            enabled=True,
            status="unchecked",
            last_update=None,
        ),
    ]
    monkeypatch.setattr(
        rss_feed_check_service_module,
        "list_rss_feeds_for_check",
        lambda _db, feed_ids=None: feeds,
    )

    async def fake_check_single_feed(
        url: str,
        http_client=None,
    ):
        if url.endswith("/valid"):
            return "valid", None
        return "invalid", "Request timeout"

    monkeypatch.setattr(
        rss_feed_check_service_module,
        "_check_single_feed",
        fake_check_single_feed,
    )

    response = asyncio.run(rss_feed_check_service_module.check_rss_feeds(db, feed_ids=[1, 2]))

    assert response.valid_count == 1
    assert response.invalid_count == 1
    assert len(response.results) == 1
    assert response.results[0].feed_id == 2
    assert response.results[0].error == "Request timeout"
    assert feeds[0].status == "valid"
    assert feeds[0].enabled is True
    assert feeds[0].last_update is not None
    assert feeds[1].status == "invalid"
    assert feeds[1].enabled is False
    assert feeds[1].last_update is not None
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_check_rss_feeds_rolls_back_when_commit_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    db.commit.side_effect = RuntimeError("db write failure")
    feeds = [
        SimpleNamespace(
            id=1,
            url="https://example.com/rss/invalid",
            enabled=True,
            status="unchecked",
            last_update=None,
        )
    ]
    monkeypatch.setattr(
        rss_feed_check_service_module,
        "list_rss_feeds_for_check",
        lambda _db, feed_ids=None: feeds,
    )

    async def fake_check_single_feed(_url: str, http_client=None):
        return "invalid", "Unknown error"

    monkeypatch.setattr(
        rss_feed_check_service_module,
        "_check_single_feed",
        fake_check_single_feed,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(rss_feed_check_service_module.check_rss_feeds(db))

    db.rollback.assert_called_once()


def test_check_rss_feeds_reuses_same_http_client(monkeypatch) -> None:
    db = Mock(spec=Session)
    feeds = [
        SimpleNamespace(
            id=1,
            url="https://example.com/rss/1",
            enabled=True,
            status="unchecked",
            last_update=None,
        ),
        SimpleNamespace(
            id=2,
            url="https://example.com/rss/2",
            enabled=True,
            status="unchecked",
            last_update=None,
        ),
    ]
    monkeypatch.setattr(
        rss_feed_check_service_module,
        "list_rss_feeds_for_check",
        lambda _db, feed_ids=None: feeds,
    )

    shared_http_client = object()
    context_enter_count = 0

    class FakeHttpxContext:
        async def __aenter__(self):
            nonlocal context_enter_count
            context_enter_count += 1
            return shared_http_client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    monkeypatch.setattr(
        rss_feed_check_service_module,
        "get_httpx_config",
        lambda: FakeHttpxContext(),
    )

    used_clients = []

    async def fake_check_single_feed(url: str, http_client=None):
        used_clients.append(http_client)
        return "valid", None

    monkeypatch.setattr(
        rss_feed_check_service_module,
        "_check_single_feed",
        fake_check_single_feed,
    )

    response = asyncio.run(rss_feed_check_service_module.check_rss_feeds(db))

    assert response.valid_count == 2
    assert response.invalid_count == 0
    assert context_enter_count == 1
    assert used_clients == [shared_http_client, shared_http_client]
