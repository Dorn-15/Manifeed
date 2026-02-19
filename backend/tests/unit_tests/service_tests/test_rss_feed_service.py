from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.rss.rss_feed_service as rss_feed_service_module
from app.schemas.rss import RssFeedRead


def test_get_rss_feeds_returns_database_reads(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_feed_service_module,
        "list_rss_feeds_read",
        lambda db_session: [
            RssFeedRead(
                id=1,
                url="https://example.com/rss",
                company_id=10,
                company_name="The Verge",
                company_enabled=True,
                section="Main",
                enabled=True,
                status="unchecked",
                trust_score=0.95,
                country="en",
                icon_url="theVerge/theVerge.svg",
            )
        ],
    )

    feeds = rss_feed_service_module.get_rss_feeds(db)

    assert len(feeds) == 1
    assert feeds[0].id == 1
    assert feeds[0].company_id == 10
    assert feeds[0].company_name == "The Verge"
    assert feeds[0].company_enabled is True
    assert feeds[0].icon_url == "theVerge/theVerge.svg"
