from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import list_enabled_rss_feeds
from app.clients.database.sources import (
    create_rss_source,
    link_source_to_feed,
    list_rss_sources_by_urls,
)
from app.models.sources import RssSourceFeed
from app.schemas.sources import RssSourceCandidateSchema


def test_list_enabled_rss_feeds_for_ingest_returns_rows() -> None:
    mock_db = Mock(spec=Session)
    expected_rows = [object(), object()]
    mock_db.execute.return_value.scalars.return_value.all.return_value = expected_rows

    result = list_enabled_rss_feeds(mock_db, feed_ids=[1, 2, 2])

    assert result == expected_rows
    mock_db.execute.assert_called_once()


def test_list_rss_sources_by_urls_returns_lookup() -> None:
    mock_db = Mock(spec=Session)
    source = SimpleNamespace(url="https://example.com/a", feed_links=[])
    mock_db.execute.return_value.scalars.return_value.all.return_value = [source]

    result = list_rss_sources_by_urls(mock_db, urls=["https://example.com/a", "https://example.com/a"])

    assert result == {"https://example.com/a": source}
    mock_db.execute.assert_called_once()


def test_create_rss_source_does_not_flush() -> None:
    mock_db = Mock(spec=Session)
    payload = RssSourceCandidateSchema(
        title="Example title",
        url="https://example.com/source",
    )

    source = create_rss_source(mock_db, payload=payload)

    assert source.title == "Example title"
    assert source.url == "https://example.com/source"
    mock_db.add.assert_called_once_with(source)
    mock_db.flush.assert_not_called()


def test_link_source_to_feed_is_idempotent() -> None:
    source = SimpleNamespace(feed_links=[])

    linked_first = link_source_to_feed(source=source, feed_id=9)
    linked_second = link_source_to_feed(source=source, feed_id=9)

    assert linked_first is True
    assert linked_second is False
    assert len(source.feed_links) == 1
    assert isinstance(source.feed_links[0], RssSourceFeed)
    assert source.feed_links[0].feed_id == 9
