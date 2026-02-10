from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    delete_company_feeds_not_in_urls,
    get_or_create_company,
    upsert_feed,
)
from app.models.rss import RssFeed, RssTag
from app.schemas.rss import RssFeedUpsertSchema


def test_get_or_create_company_creates_company_when_missing() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    company, created = get_or_create_company(mock_db, "Le Monde")

    assert company.name == "Le Monde"
    assert created is True
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


def test_upsert_feed_updates_existing_feed() -> None:
    mock_db = Mock(spec=Session)
    existing_feed = Mock(spec=RssFeed)
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_feed

    payload = RssFeedUpsertSchema(
        url="https://example.com/rss",
        section="Tech",
        enabled=True,
        trust_score=0.9,
        language="en",
        icon_url="icons/tech.svg",
        parsing_config={"item_tag": "item"},
        tags=["tech"],
    )
    company = SimpleNamespace(id=1, name="The Verge")
    tags = [RssTag(name="tech")]

    feed, created = upsert_feed(mock_db, company=company, payload=payload, tags=tags)

    assert feed is existing_feed
    assert created is False
    assert existing_feed.company == company
    assert existing_feed.section == "Tech"
    assert existing_feed.tags == tags
    mock_db.add.assert_not_called()
    mock_db.flush.assert_called_once()


def test_delete_company_feeds_not_in_urls_deletes_every_stale_feed() -> None:
    mock_db = Mock(spec=Session)
    stale_feed_a = Mock(spec=RssFeed)
    stale_feed_b = Mock(spec=RssFeed)
    mock_db.execute.return_value.scalars.return_value.all.return_value = [
        stale_feed_a,
        stale_feed_b,
    ]

    deleted_count = delete_company_feeds_not_in_urls(
        mock_db,
        company_id=1,
        expected_urls={"https://example.com/rss/keep"},
    )

    assert deleted_count == 2
    assert mock_db.delete.call_count == 2
    mock_db.flush.assert_called_once()
