import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.sources.source_ingest_service as source_ingest_service_module
from app.schemas.sources import RssFeedFetchPayloadSchema, RssSourceCandidateSchema


def test_ingest_rss_sources_returns_zero_stats_when_no_feeds(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(source_ingest_service_module, "list_enabled_rss_feeds", lambda _db, feed_ids=None: [])

    result = asyncio.run(source_ingest_service_module.ingest_rss_sources(db))

    assert result.feeds_processed == 0
    assert result.feeds_skipped == 0
    assert result.sources_created == 0
    assert result.sources_updated == 0
    assert result.errors == []
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_ingest_rss_sources_counts_success_skip_and_error(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed_success = SimpleNamespace(id=1, url="https://example.com/feed/1", last_update=None)
    feed_skip = SimpleNamespace(id=2, url="https://example.com/feed/2", last_update=None)
    feed_error = SimpleNamespace(id=3, url="https://example.com/feed/3", last_update=None)

    monkeypatch.setattr(
        source_ingest_service_module,
        "list_enabled_rss_feeds",
        lambda _db, feed_ids=None: [feed_success, feed_skip, feed_error],
    )

    async def fake_fetch_all_feeds(feeds, max_concurrent_fetches):
        assert max_concurrent_fetches == source_ingest_service_module.DEFAULT_MAX_CONCURRENT_FETCHES
        return [
            (
                feed_success,
                RssFeedFetchPayloadSchema(
                    status="success",
                    entries=[{"title": "A", "url": "https://example.com/s/a"}],
                    last_modified=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
            ),
            (
                feed_skip,
                RssFeedFetchPayloadSchema(status="not_modified"),
            ),
            (
                feed_error,
                RssFeedFetchPayloadSchema(status="error", error="timeout"),
            ),
        ]

    monkeypatch.setattr(source_ingest_service_module, "_fetch_all_feeds", fake_fetch_all_feeds)
    monkeypatch.setattr(
        source_ingest_service_module,
        "normalize_rss_source_candidates",
        lambda entries: [RssSourceCandidateSchema(title="A", url="https://example.com/s/a")],
    )
    monkeypatch.setattr(source_ingest_service_module, "_upsert_feed_sources", lambda db, feed, candidates: (2, 1))

    result = asyncio.run(source_ingest_service_module.ingest_rss_sources(db))

    assert result.feeds_processed == 1
    assert result.feeds_skipped == 1
    assert result.sources_created == 2
    assert result.sources_updated == 1
    assert len(result.errors) == 1
    assert result.errors[0].feed_id == 3
    assert result.errors[0].error == "timeout"
    assert feed_success.last_update is not None
    db.commit.assert_called_once()
    db.rollback.assert_called_once()


def test_ingest_rss_sources_rolls_back_and_collects_error_when_normalization_fails(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=8, url="https://example.com/feed/8", last_update=None)

    monkeypatch.setattr(source_ingest_service_module, "list_enabled_rss_feeds", lambda _db, feed_ids=None: [feed])

    async def fake_fetch_all_feeds(feeds, max_concurrent_fetches):
        return [
            (
                feed,
                RssFeedFetchPayloadSchema(
                    status="success",
                    entries=[{"title": "Broken", "url": "https://example.com/b"}],
                ),
            )
        ]

    monkeypatch.setattr(source_ingest_service_module, "_fetch_all_feeds", fake_fetch_all_feeds)
    monkeypatch.setattr(
        source_ingest_service_module,
        "normalize_rss_source_candidates",
        lambda entries: (_ for _ in ()).throw(ValueError("bad payload")),
    )

    result = asyncio.run(source_ingest_service_module.ingest_rss_sources(db))

    assert result.feeds_processed == 0
    assert len(result.errors) == 1
    assert result.errors[0].feed_id == 8
    assert result.errors[0].error == "bad payload"
    db.rollback.assert_called_once()


def test_upsert_feed_sources_creates_new_source_and_links_feed(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=21)
    created_source = SimpleNamespace(url="https://example.com/s/new")

    monkeypatch.setattr(source_ingest_service_module, "list_rss_sources_by_urls", lambda db, urls: {})
    monkeypatch.setattr(source_ingest_service_module, "create_rss_source", lambda db, payload: created_source)

    link_calls: list[tuple[object, int]] = []
    monkeypatch.setattr(
        source_ingest_service_module,
        "link_source_to_feed",
        lambda source, feed_id: link_calls.append((source, feed_id)) or True,
    )

    created, updated = source_ingest_service_module._upsert_feed_sources(
        db=db,
        feed=feed,
        candidates=[RssSourceCandidateSchema(title="New", url="https://example.com/s/new")],
    )

    assert created == 1
    assert updated == 0
    db.flush.assert_called_once_with([created_source])
    assert link_calls == [(created_source, 21)]


def test_upsert_feed_sources_counts_update_when_link_added(monkeypatch) -> None:
    db = Mock(spec=Session)
    feed = SimpleNamespace(id=31)
    existing_source = SimpleNamespace(url="https://example.com/s/existing")

    monkeypatch.setattr(
        source_ingest_service_module,
        "list_rss_sources_by_urls",
        lambda db, urls: {"https://example.com/s/existing": existing_source},
    )
    monkeypatch.setattr(source_ingest_service_module, "update_rss_source", lambda source, payload: False)
    monkeypatch.setattr(source_ingest_service_module, "link_source_to_feed", lambda source, feed_id: True)

    created, updated = source_ingest_service_module._upsert_feed_sources(
        db=db,
        feed=feed,
        candidates=[RssSourceCandidateSchema(title="Existing", url="https://example.com/s/existing")],
    )

    assert created == 0
    assert updated == 1


def test_deduplicate_candidates_keeps_first_item_per_url() -> None:
    candidates = [
        RssSourceCandidateSchema(title="A", url="https://example.com/s/a"),
        RssSourceCandidateSchema(title="A2", url="https://example.com/s/a"),
        RssSourceCandidateSchema(title="B", url="https://example.com/s/b"),
    ]

    result = source_ingest_service_module._deduplicate_candidates(candidates)

    assert [candidate.title for candidate in result] == ["A", "B"]
