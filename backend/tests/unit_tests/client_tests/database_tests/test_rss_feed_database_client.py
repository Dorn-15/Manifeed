from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    list_rss_feeds,
    list_rss_feeds,
    list_rss_feeds_read,
)


def test_list_rss_feeds_returns_database_rows() -> None:
    mock_db = Mock(spec=Session)
    expected_feeds = [object(), object()]
    mock_db.execute.return_value.scalars.return_value.all.return_value = expected_feeds

    feeds = list_rss_feeds(mock_db)

    assert feeds == expected_feeds
    mock_db.execute.assert_called_once()


def test_list_rss_feeds_read_returns_read_schema() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.mappings.return_value.all.return_value = [
        {
            "id": 1,
            "url": "https://example.com/rss",
            "company_id": 10,
            "company_name": "The Verge",
            "company_enabled": True,
            "section": "Main",
            "enabled": True,
            "status": "unchecked",
            "trust_score": 0.95,
            "language": "en",
            "icon_url": "theVerge/theVerge.svg",
        }
    ]

    feeds = list_rss_feeds_read(mock_db)

    assert len(feeds) == 1
    assert feeds[0].id == 1
    assert feeds[0].company_id == 10
    assert feeds[0].company_name == "The Verge"
    assert feeds[0].company_enabled is True
    assert feeds[0].icon_url == "theVerge/theVerge.svg"
    mock_db.execute.assert_called_once()


def test_list_rss_feeds_for_check_returns_database_rows() -> None:
    mock_db = Mock(spec=Session)
    expected_feeds = [object(), object()]
    mock_db.execute.return_value.scalars.return_value.all.return_value = expected_feeds

    feeds = list_rss_feeds(mock_db, feed_ids=[2, 2, 1])

    assert feeds == expected_feeds
    mock_db.execute.assert_called_once()
