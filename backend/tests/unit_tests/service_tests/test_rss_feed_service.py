from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.rss_feed_service as rss_feed_service_module


def test_get_rss_feeds_maps_database_models_to_api_schema(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(
        rss_feed_service_module,
        "list_rss_feeds",
        lambda db_session: [
            SimpleNamespace(
                id=1,
                url="https://example.com/rss",
                company=SimpleNamespace(name="The Verge"),
                section="Main",
                enabled=True,
                status="unchecked",
                trust_score=0.95,
                language="en",
                icon_url="theVerge/theVerge.svg",
            )
        ],
    )

    feeds = rss_feed_service_module.get_rss_feeds(db)

    assert len(feeds) == 1
    assert feeds[0].id == 1
    assert feeds[0].company_name == "The Verge"
    assert feeds[0].icon_url == "theVerge/theVerge.svg"
