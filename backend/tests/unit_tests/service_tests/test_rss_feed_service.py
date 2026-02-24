from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.rss.rss_feed_service as rss_feed_service_module
from app.schemas.rss import RssCompanyRead, RssFeedRead


def test_get_rss_feeds_read_returns_database_payload(monkeypatch) -> None:
    db = Mock(spec=Session)
    expected = [
        RssFeedRead(
            id=1,
            url="https://example.com/rss",
            section="Main",
            enabled=True,
            trust_score=0.9,
            fetchprotection=1,
            company=RssCompanyRead(
                id=2,
                name="Example News",
                host="example.com",
                icon_url="example/icon.svg",
                country="us",
                language="en",
                fetchprotection=1,
                enabled=True,
            ),
        )
    ]

    monkeypatch.setattr(rss_feed_service_module, "list_rss_feeds_read", lambda _db: expected)

    result = rss_feed_service_module.get_rss_feeds_read(db)

    assert result == expected
