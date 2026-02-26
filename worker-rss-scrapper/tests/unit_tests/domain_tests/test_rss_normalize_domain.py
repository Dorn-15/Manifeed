from datetime import datetime, timezone

from app.domain.rss_normalize_domain import normalize_feed_sources


def test_normalize_feed_sources_filters_invalid_old_missing_dates_and_deduplicates_urls() -> None:
    entries = [
        {
            "title": "A",
            "url": "https://example.com/a",
            "summary": "s1",
            "published_at": datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc),
        },
        {
            "title": "A duplicate",
            "url": "https://example.com/a",
            "summary": "s2",
            "published_at": datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc),
        },
        {
            "title": "B too old",
            "url": "https://example.com/b-old",
            "published_at": datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc),
        },
        {
            "title": "B",
            "url": "https://example.com/b",
            "published_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
        },
        {"title": "Missing published_at", "url": "https://example.com/missing-date"},
        {"title": "Missing URL", "published_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)},
        {"url": "https://example.com/missing-title", "published_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)},
    ]

    result = normalize_feed_sources(entries)

    assert [item.url for item in result] == ["https://example.com/a", "https://example.com/b"]
    assert result[0].summary == "s1"


def test_normalize_feed_sources_keeps_2026_boundary_and_normalizes_naive_datetime() -> None:
    entries = [
        {
            "title": "Boundary",
            "url": "https://example.com/boundary",
            "published_at": datetime(2026, 1, 1, 0, 0),
        },
        {
            "title": "Before boundary",
            "url": "https://example.com/before",
            "published_at": datetime(2025, 12, 31, 23, 59, 59),
        },
    ]

    result = normalize_feed_sources(entries)

    assert len(result) == 1
    assert result[0].url == "https://example.com/boundary"
    assert result[0].published_at == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
