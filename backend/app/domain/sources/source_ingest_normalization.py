from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re

from app.schemas.sources import RssSourceCandidateSchema

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_rss_source_candidates(
    entries: list[dict[str, Any]],
) -> list[RssSourceCandidateSchema]:
    candidates: list[RssSourceCandidateSchema] = []
    index = 0

    while index < len(entries):
        entry = entries[index]
        index += 1

        candidate = _normalize_rss_source_candidate(
            entry=entry,
        )
        if candidate is None:
            continue
        candidates.append(candidate)

    return candidates


def _normalize_rss_source_candidate(
    entry: dict[str, Any],
) -> RssSourceCandidateSchema | None:
    url = _normalize_text(entry.get("url"), strip_html=False)
    title = _normalize_text(entry.get("title"), strip_html=True, max_length=500)
    if not url or not title:
        return None
    
    return RssSourceCandidateSchema(
        title=title,
        url=url,
        summary=_normalize_text(entry.get("summary"), strip_html=True, max_length=5000),
        author=_normalize_text(entry.get("author"), strip_html=True, max_length=255),
        published_at=_normalize_datetime(entry.get("published_at")),
        image_url=_normalize_text(entry.get("image_url"), strip_html=False, max_length=1000),
    )


def _normalize_text(
    value: Any,
    strip_html: bool,
    max_length: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if strip_html:
        normalized = _HTML_TAG_RE.sub(" ", normalized)
        normalized = " ".join(normalized.split())
        if not normalized:
            return None

    if max_length is not None and len(normalized) > max_length:
        return normalized[:max_length]
    return normalized


def _normalize_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
