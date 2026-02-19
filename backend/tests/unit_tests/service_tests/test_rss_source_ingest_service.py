import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.sources.source_ingest_service as rss_source_ingest_service_module
from app.schemas.sources import (
    RssFeedFetchPayloadSchema,
    RssSourceCandidateSchema,
)


def test_ingest_rss_sources_returns_empty_stats_when_no_feed(monkeypatch) -> None:
    mock_db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "list_enabled_rss_feeds",
        lambda _db, feed_ids=None: [],
    )

    result = asyncio.run(rss_source_ingest_service_module.ingest_rss_sources(mock_db))

    assert result.feeds_processed == 0
    assert result.feeds_skipped == 0
    assert result.sources_created == 0
    assert result.sources_updated == 0
    assert result.errors == []
    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_not_called()


def test_ingest_rss_sources_handles_success_skip_and_error(monkeypatch) -> None:
    mock_db = Mock(spec=Session)
    feed_success = SimpleNamespace(id=1, url="https://example.com/rss/1", country="uk", last_update=None)
    feed_skip = SimpleNamespace(id=2, url="https://example.com/rss/2", country="uk", last_update=None)
    feed_error = SimpleNamespace(id=3, url="https://example.com/rss/3", country="uk", last_update=None)

    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "list_enabled_rss_feeds",
        lambda _db, feed_ids=None: [feed_success, feed_skip, feed_error],
    )

    async def fake_fetch_all_feeds(feeds, max_concurrent_fetches):
        assert feeds == [feed_success, feed_skip, feed_error]
        assert max_concurrent_fetches == 5
        return [
            (
                feed_success,
                RssFeedFetchPayloadSchema(
                    status="success",
                    entries=[{"title": "T1", "url": "https://example.com/s1"}],
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

    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "_fetch_all_feeds",
        fake_fetch_all_feeds,
    )
    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "normalize_rss_source_candidates",
        lambda entries, default_language=None: [
            RssSourceCandidateSchema(title="T1", url="https://example.com/s1", language=default_language)
        ],
    )
    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "_upsert_feed_sources",
        lambda db, feed, candidates: (2, 1),
    )

    result = asyncio.run(rss_source_ingest_service_module.ingest_rss_sources(mock_db))

    assert result.feeds_processed == 1
    assert result.feeds_skipped == 1
    assert result.sources_created == 2
    assert result.sources_updated == 1
    assert len(result.errors) == 1
    assert result.errors[0].feed_id == 3
    assert result.errors[0].error == "timeout"
    mock_db.commit.assert_called_once()
    mock_db.rollback.assert_called_once()


def test_upsert_feed_sources_counts_existing_link_update(monkeypatch) -> None:
    mock_db = Mock(spec=Session)
    feed = SimpleNamespace(id=7)
    existing_source = SimpleNamespace(
        url="https://example.com/source",
        feed_links=[],
    )

    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "list_rss_sources_by_urls",
        lambda db, urls: {"https://example.com/source": existing_source},
    )
    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "update_rss_source",
        lambda source, payload: False,
    )
    monkeypatch.setattr(
        rss_source_ingest_service_module,
        "link_source_to_feed",
        lambda source, feed_id: True,
    )

    created, updated = rss_source_ingest_service_module._upsert_feed_sources(
        db=mock_db,
        feed=feed,
        candidates=[
            RssSourceCandidateSchema(
                title="T",
                url="https://example.com/source",
                language="en",
            )
        ],
    )

    assert created == 0
    assert updated == 1
