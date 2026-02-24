import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from xml.etree import ElementTree

import httpx
import pytest

import app.clients.networking.sources.ingest_feed_networking_cli as ingest_feed_networking_cli_module


def test_parse_rss_feed_entries_parses_rss_item_and_last_modified() -> None:
    xml_payload = """
    <rss version="2.0">
      <channel>
        <lastBuildDate>Tue, 24 Feb 2026 10:00:00 GMT</lastBuildDate>
        <item>
          <title>Example title</title>
          <link>https://example.com/articles/1</link>
          <description>Example summary</description>
          <author>Jane Doe</author>
          <pubDate>Tue, 24 Feb 2026 09:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    entries, last_modified = ingest_feed_networking_cli_module._parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["title"] == "Example title"
    assert entries[0]["url"] == "https://example.com/articles/1"
    assert entries[0]["summary"] == "Example summary"
    assert entries[0]["author"] == "Jane Doe"
    assert entries[0]["published_at"] == datetime(2026, 2, 24, 9, 0, tzinfo=timezone.utc)
    assert last_modified == datetime(2026, 2, 24, 10, 0, tzinfo=timezone.utc)


def test_parse_rss_feed_entries_parses_atom_entry_link_href() -> None:
    xml_payload = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <updated>2026-02-24T11:00:00Z</updated>
      <entry>
        <title>Atom entry</title>
        <link rel="alternate" href="https://example.com/atom/1" />
        <summary>Atom summary</summary>
      </entry>
    </feed>
    """.strip()

    entries, last_modified = ingest_feed_networking_cli_module._parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["url"] == "https://example.com/atom/1"
    assert entries[0]["summary"] == "Atom summary"
    assert last_modified == datetime(2026, 2, 24, 11, 0, tzinfo=timezone.utc)


def test_parse_rss_feed_entries_raises_on_invalid_xml() -> None:
    with pytest.raises(ValueError, match="Invalid XML"):
        ingest_feed_networking_cli_module._parse_rss_feed_entries("<rss>")


def test_extract_entry_image_url_prefers_widest_srcset_candidate() -> None:
    entry = ElementTree.fromstring(
        """
        <item>
          <title>Entry with image</title>
          <link>https://example.com/articles/2</link>
          <description><![CDATA[
            <p>With media</p>
            <img
              src="https://cdn.example.com/small.jpg?w=320&amp;h=180"
              srcset="https://cdn.example.com/large.jpg 1280w, https://cdn.example.com/medium.jpg 640w"
            />
          ]]></description>
        </item>
        """.strip()
    )

    image_url = ingest_feed_networking_cli_module._extract_entry_image_url(entry)

    assert image_url == "https://cdn.example.com/large.jpg"


def test_fetch_rss_feed_entries_returns_timeout_error(monkeypatch) -> None:
    async def fake_get_httpx_by_method(**kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(
        ingest_feed_networking_cli_module,
        "get_httpx_by_method",
        fake_get_httpx_by_method,
    )

    feed = SimpleNamespace(
        url="https://example.com/rss.xml",
        fetchprotection=1,
        company=None,
        last_update=None,
    )

    result = asyncio.run(ingest_feed_networking_cli_module.fetch_rss_feed_entries(feed))

    assert result.status == "error"
    assert result.error == "Request timeout"


def test_fetch_rss_feed_entries_returns_not_modified(monkeypatch) -> None:
    last_update = datetime(2026, 2, 24, 10, 0, tzinfo=timezone.utc)

    async def fake_get_httpx_by_method(**kwargs):
        payload = (
            "<rss><channel>"
            "<lastBuildDate>Tue, 24 Feb 2026 10:00:00 GMT</lastBuildDate>"
            "<item><title>T</title><link>https://example.com/articles/3</link></item>"
            "</channel></rss>"
        )
        return payload, "application/rss+xml"

    monkeypatch.setattr(
        ingest_feed_networking_cli_module,
        "get_httpx_by_method",
        fake_get_httpx_by_method,
    )

    feed = SimpleNamespace(
        url="https://example.com/rss.xml",
        fetchprotection=1,
        company=None,
        last_update=last_update,
    )

    result = asyncio.run(ingest_feed_networking_cli_module.fetch_rss_feed_entries(feed))

    assert result.status == "not_modified"
    assert result.last_modified == last_update
