from app.domain.rss import build_rss_scrape_batches
from app.schemas.rss import RssScrapeFeedPayloadSchema


def test_build_rss_scrape_batches_groups_by_company_and_caps_batch_size() -> None:
    feeds = [
        RssScrapeFeedPayloadSchema(feed_id=1, feed_url="https://alpha.example.com/1.xml", company_id=10),
        RssScrapeFeedPayloadSchema(feed_id=2, feed_url="https://beta.example.com/2.xml", company_id=20),
        RssScrapeFeedPayloadSchema(feed_id=3, feed_url="https://alpha.example.com/3.xml", company_id=10),
        RssScrapeFeedPayloadSchema(feed_id=4, feed_url="https://alpha.example.com/4.xml", company_id=10),
        RssScrapeFeedPayloadSchema(feed_id=5, feed_url="https://gamma.example.com/5.xml", company_id=30),
        RssScrapeFeedPayloadSchema(feed_id=6, feed_url="https://gamma.example.com/6.xml", company_id=30),
    ]

    batches = build_rss_scrape_batches(feeds, batch_size=2, random_seed="job-1")

    assert len(batches) == 4
    assert all(len(batch) <= 2 for batch in batches)
    assert {tuple(feed.feed_id for feed in batch) for batch in batches} == {(1, 3), (4,), (2,), (5, 6)}
    assert len({_host(batch) for batch in batches[:3]}) == 3


def test_build_rss_scrape_batches_keeps_companyless_feeds_isolated() -> None:
    feeds = [
        RssScrapeFeedPayloadSchema(feed_id=1, feed_url="https://example.com/1.xml", company_id=None),
        RssScrapeFeedPayloadSchema(feed_id=2, feed_url="https://example.com/2.xml", company_id=None),
    ]

    batches = build_rss_scrape_batches(feeds, batch_size=20, random_seed="job-2")

    assert {tuple(feed.feed_id for feed in batch) for batch in batches} == {(1,), (2,)}


def _host(batch: list[RssScrapeFeedPayloadSchema]) -> str:
    return batch[0].feed_url.split("/")[2]
