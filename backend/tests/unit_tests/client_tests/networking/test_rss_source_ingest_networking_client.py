import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import app.clients.networking.sources.ingest_feed_networking_cli as rss_ingest_networking_module


def test_parse_rss_feed_entries_extracts_basic_item() -> None:
    xml_payload = """
    <rss>
      <channel>
        <lastBuildDate>Mon, 01 Jan 2024 10:00:00 GMT</lastBuildDate>
        <item>
          <title>Example title</title>
          <link>https://example.com/article</link>
          <description>Example summary</description>
          <pubDate>Mon, 01 Jan 2024 09:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    entries, last_modified = rss_ingest_networking_module.parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["title"] == "Example title"
    assert entries[0]["url"] == "https://example.com/article"
    assert entries[0]["summary"] == "Example summary"
    assert last_modified is not None


def test_parse_rss_feed_entries_falls_back_to_content_encoded_when_description_is_empty() -> None:
    xml_payload = """
    <rss xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <item>
          <title>Example title</title>
          <link>https://example.com/article</link>
          <description/>
          <content:encoded><![CDATA[<p>Hello <strong>world</strong>.</p>]]></content:encoded>
          <pubDate>Mon, 01 Jan 2024 09:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    entries, _ = rss_ingest_networking_module.parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["summary"] == "Hello world."


def test_parse_rss_feed_entries_extracts_atom_image_from_content_img_src() -> None:
    xml_payload = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Example title</title>
        <link rel="alternate" type="text/html" href="https://example.com/article" />
        <content type="html">
          <figure>
            <img src="https://example.com/image.jpg?quality=90&#038;strip=all" />
          </figure>
        </content>
      </entry>
    </feed>
    """

    entries, _ = rss_ingest_networking_module.parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["image_url"] == "https://example.com/image.jpg?quality=90&strip=all"


def test_fetch_rss_feed_entries_returns_not_modified(monkeypatch) -> None:
    matching_last_update = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    feed = SimpleNamespace(
        url="https://example.com/rss",
        last_update=matching_last_update,
    )

    async def fake_get_httpx(url, client=None):
        assert url == "https://example.com/rss"
        return "<rss><channel></channel></rss>", "application/rss+xml"

    monkeypatch.setattr(rss_ingest_networking_module, "get_httpx", fake_get_httpx)
    monkeypatch.setattr(
        rss_ingest_networking_module,
        "parse_rss_feed_entries",
        lambda content: ([], matching_last_update),
    )

    result = asyncio.run(rss_ingest_networking_module.fetch_rss_feed_entries(feed))

    assert result.status == "not_modified"
    assert result.error is None
