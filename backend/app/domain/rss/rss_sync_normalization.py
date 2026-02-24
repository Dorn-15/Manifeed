import re

from app.schemas.rss import (
    RssFeedUpsertSchema,
    RssSourceFeedSchema,
)


def normalize_source_feed_entry(
    source_feed: RssSourceFeedSchema,
    default_fetchprotection: int,
) -> RssFeedUpsertSchema:
    return RssFeedUpsertSchema(
        url= source_feed.url.strip(),
        section= _normalize_section(source_feed.title),
        enabled= source_feed.enabled,
        trust_score= source_feed.trust_score,
        fetchprotection=_normalize_fetchprotection(
            source_feed.fetchprotection,
            default_value=default_fetchprotection,
        ),
        tags=           _normalize_tags(source_feed.tags),
    )


def _normalize_section(section_title: str) -> str | None:
    normalized_section = re.sub(r"\s+", " ", section_title).strip()
    if not normalized_section:
        return None
    return normalized_section[:50]


def _normalize_fetchprotection(
    fetchprotection: int | None,
    default_value: int,
) -> int:
    if isinstance(fetchprotection, int) and 0 <= fetchprotection <= 3:
        return fetchprotection
    return max(0, min(3, default_value))


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen_tags: set[str] = set()

    for tag in tags:
        normalized_tag = re.sub(r"\s+", "-", tag.strip().lower())
        if not normalized_tag or normalized_tag in seen_tags:
            continue
        seen_tags.add(normalized_tag)
        normalized_tags.append(normalized_tag)

    return normalized_tags
