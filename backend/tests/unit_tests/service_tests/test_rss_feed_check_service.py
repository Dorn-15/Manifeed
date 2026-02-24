import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

import app.services.rss.rss_feed_check_service as rss_feed_check_service_module


def test_check_rss_feeds_returns_empty_list_when_no_feed(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(rss_feed_check_service_module, "list_rss_feeds", lambda _db, feed_ids=None: [])

    result = asyncio.run(rss_feed_check_service_module.check_rss_feeds(db))

    assert result == []
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_check_rss_feeds_updates_feeds_and_returns_only_invalid(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed_valid = SimpleNamespace(
        id=1,
        url="https://example.com/valid.xml",
        fetchprotection=1,
        last_update=None,
        company=SimpleNamespace(language="en", host="example.com"),
    )
    feed_invalid = SimpleNamespace(
        id=2,
        url="https://example.com/invalid.xml",
        fetchprotection=1,
        last_update=None,
        company=SimpleNamespace(language="fr", host=None),
    )

    monkeypatch.setattr(
        rss_feed_check_service_module,
        "list_rss_feeds",
        lambda _db, feed_ids=None: [feed_valid, feed_invalid],
    )

    class FakeHttpContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(rss_feed_check_service_module, "get_httpx_config", lambda: FakeHttpContext())

    async def fake_check_single_feed(feed, http_client=None):
        if feed.id == 1:
            return "valid", None, 2
        return "invalid", "Request timeout", 0

    monkeypatch.setattr(rss_feed_check_service_module, "_check_single_feed", fake_check_single_feed)

    result = asyncio.run(rss_feed_check_service_module.check_rss_feeds(db, feed_ids=[1, 2]))

    assert len(result) == 1
    assert result[0].feed_id == 2
    assert result[0].status == "invalid"
    assert result[0].error == "Request timeout"
    assert feed_valid.fetchprotection == 2
    assert feed_invalid.fetchprotection == 0
    assert feed_valid.last_update is not None
    assert feed_invalid.last_update is not None
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_check_rss_feeds_rolls_back_when_commit_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    db.commit.side_effect = RuntimeError("write failed")
    feed = SimpleNamespace(id=1, url="https://example.com/rss.xml", fetchprotection=1, last_update=None, company=None)

    monkeypatch.setattr(rss_feed_check_service_module, "list_rss_feeds", lambda _db, feed_ids=None: [feed])

    class FakeHttpContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(rss_feed_check_service_module, "get_httpx_config", lambda: FakeHttpContext())
    monkeypatch.setattr(
        rss_feed_check_service_module,
        "_check_single_feed",
        lambda feed, http_client=None: asyncio.sleep(0, result=("invalid", "bad", 0)),
    )

    with pytest.raises(RuntimeError, match="write failed"):
        asyncio.run(rss_feed_check_service_module.check_rss_feeds(db))

    db.rollback.assert_called_once()


def test_check_single_feed_returns_invalid_when_probe_has_no_content(monkeypatch) -> None:
    feed = SimpleNamespace(
        url="https://example.com/rss.xml",
        company=SimpleNamespace(language="en", host="news.example.com"),
    )

    async def fake_probe(**kwargs):
        return SimpleNamespace(
            fetchprotection=0,
            content=None,
            content_type=None,
            error="Blocked",
        )

    monkeypatch.setattr(rss_feed_check_service_module, "probe_httpx_methods", fake_probe)

    status, error, fetchprotection = asyncio.run(rss_feed_check_service_module._check_single_feed(feed))

    assert status == "invalid"
    assert error == "Blocked"
    assert fetchprotection == 0


def test_resolve_feed_header_returns_origin_and_referer() -> None:
    feed = SimpleNamespace(company=SimpleNamespace(host="https://WWW.Example.com/path"))

    result = rss_feed_check_service_module._resolve_feed_header(feed)

    assert result == {
        "Origin": "https://www.example.com",
        "Referer": "https://www.example.com/",
    }
