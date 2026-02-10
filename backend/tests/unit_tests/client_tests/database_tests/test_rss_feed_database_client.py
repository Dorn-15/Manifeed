from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import list_rss_feeds


def test_list_rss_feeds_returns_database_rows() -> None:
    mock_db = Mock(spec=Session)
    expected_feeds = [object(), object()]
    mock_db.execute.return_value.scalars.return_value.all.return_value = expected_feeds

    feeds = list_rss_feeds(mock_db)

    assert feeds == expected_feeds
    mock_db.execute.assert_called_once()
