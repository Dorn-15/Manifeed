from datetime import datetime, timezone

from app.domain.rss_parse_domain import parse_rss_feed_entries


def test_parse_rss_feed_entries_parses_rss_item_and_last_modified() -> None:
    xml_payload = """
    <rss version="2.0">
      <channel>
        <lastBuildDate>Thu, 26 Feb 2026 12:00:00 GMT</lastBuildDate>
        <item>
          <title>Article A</title>
          <link>https://example.com/article-a</link>
          <description>Summary A</description>
          <author>Newsroom</author>
          <pubDate>Thu, 26 Feb 2026 11:45:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """.strip()

    entries, last_modified = parse_rss_feed_entries(xml_payload)

    assert len(entries) == 1
    assert entries[0]["title"] == "Article A"
    assert entries[0]["url"] == "https://example.com/article-a"
    assert entries[0]["summary"] == "Summary A"
    assert entries[0]["author"] == "Newsroom"
    assert entries[0]["published_at"] == datetime(2026, 2, 26, 11, 45, tzinfo=timezone.utc)
    assert last_modified == datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
