from app.domain.rss import (
    normalize_company_name_from_filename,
    normalize_source_feed_entry,
)
from app.schemas.rss import RssSourceFeedSchema


def test_normalize_company_name_from_filename() -> None:
    company_name = normalize_company_name_from_filename("The_Wall_Street_Journal.json")
    assert company_name == "The Wall Street Journal"


def test_normalize_source_feed_entry() -> None:
    source_feed = RssSourceFeedSchema(
        url="https://example.com/rss/ai",
        title="  AI   Coverage ",
        tags=[" Tech ", "tech", "AI Trends"],
        trust_score=0.92,
        language="EN",
        enabled=True,
        img="icons/ai.svg",
        parsing_config={"item_tag": "item"},
    )

    normalized_feed = normalize_source_feed_entry(source_feed)

    assert normalized_feed.section == "AI Coverage"
    assert normalized_feed.language == "en"
    assert normalized_feed.tags == ["tech", "ai-trends"]
    assert normalized_feed.icon_url == "icons/ai.svg"
