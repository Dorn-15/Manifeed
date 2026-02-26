import asyncio
from datetime import datetime, timezone

import httpx

import app.clients.networking.rss_fetch_networking_client as rss_fetch_networking_client_module
from app.schemas.feed_source_schema import FeedSourceSchema
from app.schemas.scrape_job_schema import ScrapeJobFeedSchema


def test_build_request_headers_includes_host_and_conditionals_for_fetchprotection_2() -> None:
    feed = ScrapeJobFeedSchema(
        feed_id=1,
        feed_url="https://example.com/rss.xml",
        host_header="Example.COM",
        fetchprotection=2,
        etag='"abc"',
        last_update=datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc),
    )

    headers = rss_fetch_networking_client_module._build_request_headers(feed)

    assert headers is not None
    assert headers["Host"] == "example.com"
    assert headers["Origin"] == "https://example.com"
    assert headers["Referer"] == "https://example.com/"
    assert headers["If-None-Match"] == '"abc"'
    assert headers["If-Modified-Since"] == "Thu, 26 Feb 2026 12:00:00 GMT"


def test_fetch_feed_result_returns_error_when_fetchprotection_is_zero() -> None:
    feed = ScrapeJobFeedSchema(
        feed_id=2,
        feed_url="https://example.com/rss.xml",
        fetchprotection=0,
    )

    result = asyncio.run(
        rss_fetch_networking_client_module.fetch_feed_result(
            feed=feed,
            ingest=False,
        )
    )

    assert result.status == "error"
    assert result.error_message == "Blocked by fetch protection"
    assert result.sources == []


def test_fetch_feed_result_returns_not_modified_on_304(monkeypatch) -> None:
    feed = ScrapeJobFeedSchema(
        feed_id=3,
        feed_url="https://example.com/rss.xml",
        fetchprotection=1,
    )

    async def fake_perform_request_with_retry(*, url, headers, client):
        request = httpx.Request("GET", url)
        return httpx.Response(
            status_code=304,
            request=request,
            headers={
                "etag": "etag-304",
                "last-modified": "Thu, 26 Feb 2026 12:00:00 GMT",
            },
        )

    monkeypatch.setattr(
        rss_fetch_networking_client_module,
        "_perform_request_with_retry",
        fake_perform_request_with_retry,
    )

    result = asyncio.run(
        rss_fetch_networking_client_module.fetch_feed_result(
            feed=feed,
            ingest=True,
            http_client=None,
        )
    )

    assert result.status == "not_modified"
    assert result.new_etag == "etag-304"
    assert result.new_last_update == datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
    assert result.sources == []


def test_fetch_feed_result_returns_success_with_normalized_sources(monkeypatch) -> None:
    parsed_last_modified = datetime(2026, 2, 26, 10, 0, tzinfo=timezone.utc)
    feed = ScrapeJobFeedSchema(
        feed_id=4,
        feed_url="https://example.com/rss.xml",
        fetchprotection=2,
    )

    async def fake_perform_request_with_retry(*, url, headers, client):
        request = httpx.Request("GET", url)
        return httpx.Response(
            status_code=200,
            request=request,
            headers={"etag": "etag-200"},
            text="<rss/>",
        )

    monkeypatch.setattr(
        rss_fetch_networking_client_module,
        "_perform_request_with_retry",
        fake_perform_request_with_retry,
    )
    monkeypatch.setattr(
        rss_fetch_networking_client_module,
        "parse_rss_feed_entries",
        lambda _content: ([{"title": "A", "url": "https://example.com/a"}], parsed_last_modified),
    )
    monkeypatch.setattr(
        rss_fetch_networking_client_module,
        "normalize_feed_sources",
        lambda _entries: [FeedSourceSchema(title="A", url="https://example.com/a")],
    )

    result = asyncio.run(
        rss_fetch_networking_client_module.fetch_feed_result(
            feed=feed,
            ingest=False,
            http_client=None,
        )
    )

    assert result.status == "success"
    assert result.new_etag == "etag-200"
    assert result.new_last_update == parsed_last_modified
    assert [source.url for source in result.sources] == ["https://example.com/a"]
