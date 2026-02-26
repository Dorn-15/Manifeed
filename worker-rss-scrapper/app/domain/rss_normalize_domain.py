from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.feed_source_schema import FeedSourceSchema

MIN_ARTICLE_PUBLISHED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def normalize_feed_sources(entries: list[dict[str, Any]]) -> list[FeedSourceSchema]:
    normalized: list[FeedSourceSchema] = []
    seen_urls: set[str] = set()

    for entry in entries:
        title = _normalize_text(entry.get("title"))
        url = _normalize_text(entry.get("url"))
        if title is None or url is None:
            continue
        if url in seen_urls:
            continue
        published_at = _normalize_datetime(entry.get("published_at"))
        if not _is_published_from_2026(published_at):
            continue
        seen_urls.add(url)
        normalized.append(
            FeedSourceSchema(
                title=title,
                url=url,
                summary=_normalize_text(entry.get("summary")),
                author=_normalize_text(entry.get("author")),
                published_at=published_at,
                image_url=_normalize_text(entry.get("image_url")),
            )
        )

    return normalized


def _normalize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_published_from_2026(value: datetime | None) -> bool:
    if value is None:
        return False
    return value >= MIN_ARTICLE_PUBLISHED_AT
