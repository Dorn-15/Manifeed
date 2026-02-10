import re
from pathlib import Path

from app.schemas.rss import (
    RssFeedUpsertSchema,
    RssSourceFeedSchema,
)

def normalize_company_name_from_filename(file_name: str) -> str:
    raw_company_name = Path(file_name).stem.replace("_", " ")
    normalized_company_name = re.sub(r"\s+", " ", raw_company_name).strip()
    if not normalized_company_name:
        raise ValueError(f"Could not derive company name from file path: {file_name}")
    return normalized_company_name


def normalize_source_feed_entry(source_feed: RssSourceFeedSchema) -> RssFeedUpsertSchema:
    return RssFeedUpsertSchema(
        url=source_feed.url.strip(),
        section=_normalize_section(source_feed.title),
        enabled=source_feed.enabled,
        trust_score=source_feed.trust_score,
        language=_normalize_language(source_feed.language),
        icon_url=_normalize_icon_url(source_feed.img),
        parsing_config=_normalize_parsing_config(source_feed.parsing_config),
        tags=_normalize_tags(source_feed.tags),
    )


def _normalize_section(section_title: str) -> str | None:
    normalized_section = re.sub(r"\s+", " ", section_title).strip()
    if not normalized_section:
        return None
    return normalized_section[:50]


def _normalize_language(language: str | None) -> str | None:
    if language is None:
        return None

    normalized_language = language.strip().lower()
    if not normalized_language:
        return None
    return normalized_language[:2]


def _normalize_icon_url(icon_url: str | None) -> str | None:
    if icon_url is None:
        return None

    normalized_icon_url = icon_url.strip()
    if not normalized_icon_url:
        return None
    return normalized_icon_url


def _normalize_parsing_config(parsing_config: dict[str, object]) -> dict[str, object]:
    return dict(parsing_config)


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
