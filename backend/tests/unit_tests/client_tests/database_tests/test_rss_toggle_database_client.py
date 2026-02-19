from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    get_company_by_id,
    get_rss_feed_by_id,
    get_rss_feed_read_by_id,
    set_rss_feed_enabled,
)


def test_get_rss_feed_by_id_returns_database_row() -> None:
    mock_db = Mock(spec=Session)
    expected_feed = object()
    mock_db.execute.return_value.scalar_one_or_none.return_value = expected_feed

    feed = get_rss_feed_by_id(mock_db, feed_id=12)

    assert feed is expected_feed
    mock_db.execute.assert_called_once()


def test_get_rss_company_by_id_returns_database_row() -> None:
    mock_db = Mock(spec=Session)
    expected_company = object()
    mock_db.execute.return_value.scalar_one_or_none.return_value = expected_company

    company = get_company_by_id(mock_db, company_id=5)

    assert company is expected_company
    mock_db.execute.assert_called_once()


def test_get_rss_feed_read_by_id_returns_read_schema() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "id": 12,
        "url": "https://example.com/rss",
        "company_id": 3,
        "company_name": "Le Monde",
        "company_enabled": True,
        "section": "Tech",
        "enabled": True,
        "status": "valid",
        "trust_score": 0.8,
        "country": "en",
        "icon_url": "leMonde/leMonde.svg",
    }

    feed = get_rss_feed_read_by_id(mock_db, feed_id=12)

    assert feed is not None
    assert feed.id == 12
    assert feed.company_id == 3
    assert feed.company_name == "Le Monde"
    mock_db.execute.assert_called_once()


def test_set_rss_feed_enabled_returns_true_when_row_updated() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.rowcount = 1

    updated = set_rss_feed_enabled(mock_db, feed_id=12, enabled=False)

    assert updated is True
    mock_db.execute.assert_called_once()


def test_set_rss_feed_enabled_returns_false_when_no_row_updated() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.rowcount = 0

    updated = set_rss_feed_enabled(mock_db, feed_id=999, enabled=False)

    assert updated is False
    mock_db.execute.assert_called_once()
