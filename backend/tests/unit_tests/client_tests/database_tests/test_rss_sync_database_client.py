from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy.orm import Session

from app.clients.database.rss import (
    delete_company_feeds_not_in_urls,
    get_or_create_company,
    get_or_create_tags,
    list_rss_feeds_by_urls,
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
    existing_feed.status = "valid"
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_feed

    payload = RssFeedUpsertSchema(
        url="https://example.com/rss",
        section="Tech",
        enabled=True,
        trust_score=0.9,
        country="en",
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
    mock_db.flush.assert_not_called()


def test_upsert_feed_keeps_enabled_for_invalid_existing_feed() -> None:
    mock_db = Mock(spec=Session)
    existing_feed = Mock(spec=RssFeed)
    existing_feed.status = "invalid"
    existing_feed.enabled = False
    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_feed

    payload = RssFeedUpsertSchema(
        url="https://example.com/rss",
        section="Tech",
        enabled=True,
        trust_score=0.9,
        country="en",
        icon_url="icons/tech.svg",
        parsing_config={"item_tag": "item"},
        tags=["tech"],
    )
    company = SimpleNamespace(id=1, name="The Verge")
    tags = [RssTag(name="tech")]

    feed, created = upsert_feed(mock_db, company=company, payload=payload, tags=tags)

    assert feed is existing_feed
    assert created is False
    assert existing_feed.enabled is False
    mock_db.flush.assert_not_called()


def test_upsert_feed_uses_prefetched_feed_without_lookup() -> None:
    mock_db = Mock(spec=Session)
    existing_feed = Mock(spec=RssFeed)
    existing_feed.status = "valid"

    payload = RssFeedUpsertSchema(
        url="https://example.com/rss",
        section="Tech",
        enabled=True,
        trust_score=0.9,
        country="en",
        icon_url="icons/tech.svg",
        parsing_config={"item_tag": "item"},
        tags=["tech"],
    )
    company = SimpleNamespace(id=1, name="The Verge")
    tags = [RssTag(name="tech")]

    feed, created = upsert_feed(
        mock_db,
        company=company,
        payload=payload,
        tags=tags,
        existing_feed=existing_feed,
    )

    assert feed is existing_feed
    assert created is False
    mock_db.execute.assert_not_called()


def test_get_or_create_tags_creates_missing_tags_with_single_flush() -> None:
    mock_db = Mock(spec=Session)
    existing_tag = RssTag(name="ai")
    mock_db.execute.return_value.scalars.return_value.all.return_value = [existing_tag]

    tags, created_count = get_or_create_tags(
        mock_db,
        tag_names=["tech", "ai", "tech"],
    )

    assert [tag.name for tag in tags] == ["tech", "ai"]
    assert created_count == 1
    mock_db.add_all.assert_called_once()
    mock_db.flush.assert_called_once()


def test_list_rss_feeds_by_urls_returns_lookup() -> None:
    mock_db = Mock(spec=Session)
    feed = SimpleNamespace(url="https://example.com/rss")
    mock_db.execute.return_value.scalars.return_value.all.return_value = [feed]

    result = list_rss_feeds_by_urls(
        mock_db,
        urls=["https://example.com/rss", "https://example.com/rss"],
    )

    assert result == {"https://example.com/rss": feed}
    mock_db.execute.assert_called_once()


def test_delete_company_feeds_not_in_urls_uses_bulk_delete() -> None:
    mock_db = Mock(spec=Session)
    mock_db.execute.return_value.rowcount = 2

    deleted_count = delete_company_feeds_not_in_urls(
        mock_db,
        company_id=1,
        expected_urls={"https://example.com/rss/keep"},
    )

    assert deleted_count == 2
    mock_db.execute.assert_called_once()
    mock_db.delete.assert_not_called()
    mock_db.flush.assert_not_called()
