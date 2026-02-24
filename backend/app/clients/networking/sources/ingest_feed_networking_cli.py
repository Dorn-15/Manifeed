from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from xml.etree import ElementTree
import httpx

from app.clients.networking import (
    FETCHPROTECTION_BASIC,
    FETCHPROTECTION_BROWSER_REFERER,
    get_httpx_by_method,
)
from app.models.rss import RssFeed
from app.schemas.sources import RssFeedFetchPayloadSchema
from app.utils import normalize_host

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMAGE_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d+")

_WIDTH_QUERY_PARAM_NAMES = {"w", "width"}
_HEIGHT_QUERY_PARAM_NAMES = {"h", "height"}
_STRUCTURED_IMAGE_NODE_NAMES = {"thumbnail", "content", "enclosure", "image"}

_RSS_CHANNEL_LAST_MODIFIED_FIELDS = ("lastbuilddate", "pubdate", "updated")
_ROOT_LAST_MODIFIED_FIELDS = ("updated", "lastbuilddate", "pubdate")
_ENTRY_PUBLISHED_AT_FIELDS = ("pubdate", "published", "updated", "date")


@dataclass(slots=True)
class _ImageCandidate:
    url: str
    width: int | None = None
    height: int | None = None


async def fetch_rss_feed_entries(
    feed: RssFeed,
    http_client: httpx.AsyncClient | None = None,
) -> RssFeedFetchPayloadSchema:
    fetchprotection = _resolve_fetchprotection(feed)
    header = _resolve_feed_header(feed, fetchprotection=fetchprotection)

    try:
        content, _ = await get_httpx_by_method(
            url=feed.url,
            fetchprotection=fetchprotection,
            header=header,
            client=http_client,
        )
    except httpx.TimeoutException:
        return RssFeedFetchPayloadSchema(status="error", error="Request timeout")
    except httpx.RequestError as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Request error: {exception}")
    except Exception as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Unknown fetch error: {exception}")

    try:
        entries, last_modified = _parse_rss_feed_entries(content)
    except Exception as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Feed parse error: {exception}")

    if last_modified is not None and feed.last_update is not None and last_modified == feed.last_update:
        return RssFeedFetchPayloadSchema(status="not_modified", last_modified=last_modified)

    return RssFeedFetchPayloadSchema(
        status="success",
        entries=entries,
        last_modified=last_modified,
    )


def _resolve_fetchprotection(feed: RssFeed) -> int:
    feed_level = getattr(feed, "fetchprotection", None)
    if isinstance(feed_level, int) and 1 <= feed_level <= 3:
        return feed_level

    company = getattr(feed, "company", None)
    company_level = getattr(company, "fetchprotection", None)
    if isinstance(company_level, int) and 1 <= company_level <= 3:
        return company_level

    return FETCHPROTECTION_BASIC


def _resolve_feed_header(feed: RssFeed, *, fetchprotection: int) -> dict[str, str] | None:
    if fetchprotection != FETCHPROTECTION_BROWSER_REFERER:
        return None

    company = getattr(feed, "company", None)
    host = normalize_host(getattr(company, "host", None))
    if host is None:
        return None

    origin = f"https://{host}"
    return {
        "Origin": origin,
        "Referer": f"{origin}/",
    }


def _parse_rss_feed_entries(content: str) -> tuple[list[dict[str, Any]], datetime | None]:
    if not content or not content.strip():
        raise ValueError("Empty feed content")

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exception:
        raise ValueError(f"Invalid XML: {exception}") from exception

    last_modified = _extract_last_modified(root)
    entries = [
        payload
        for node in _extract_entry_nodes(root)
        if (payload := _extract_entry_payload(node)) is not None
    ]
    return entries, last_modified


def _extract_entry_nodes(root: ElementTree.Element) -> list[ElementTree.Element]:
    root_tag = _local_name(root.tag)
    if root_tag == "rss":
        channel = _first_child(root, {"channel"})
        if channel is None:
            return []
        return [child for child in channel if _local_name(child.tag) == "item"]

    if root_tag == "feed":
        return [child for child in root if _local_name(child.tag) == "entry"]

    return [
        node
        for node in root.iter()
        if _local_name(node.tag) in {"item", "entry"}
    ]


def _extract_last_modified(root: ElementTree.Element) -> datetime | None:
    if _local_name(root.tag) == "rss":
        channel = _first_child(root, {"channel"})
        if channel is not None:
            channel_last_modified = _parse_first_datetime(
                channel,
                _RSS_CHANNEL_LAST_MODIFIED_FIELDS,
            )
            if channel_last_modified is not None:
                return channel_last_modified

    return _parse_first_datetime(root, _ROOT_LAST_MODIFIED_FIELDS)


def _extract_entry_payload(entry: ElementTree.Element) -> dict[str, Any] | None:
    title = _first_text(entry, {"title"})
    url = _extract_entry_url(entry)
    if title is None or url is None:
        return None

    return {
        "title": title,
        "summary": _extract_entry_summary(entry),
        "author": _extract_entry_author(entry),
        "url": url,
        "published_at": _extract_entry_published_at(entry),
        "image_url": _extract_entry_image_url(entry),
    }


def _extract_entry_url(entry: ElementTree.Element) -> str | None:
    link_text = _first_text(entry, {"link"})
    if link_text:
        return link_text

    fallback_url: str | None = None
    for link in entry:
        if _local_name(link.tag) != "link":
            continue
        href = _clean_text(link.attrib.get("href"))
        if href is None:
            continue
        rel = _clean_text(link.attrib.get("rel"))
        if rel in {None, "alternate"}:
            return href
        if fallback_url is None:
            fallback_url = href
    return fallback_url


def _extract_entry_summary(entry: ElementTree.Element) -> str | None:
    summary = _first_text(entry, {"summary", "description"})
    if summary:
        return summary

    for field_name in ("encoded", "content"):
        summary = _strip_html_text(_first_text(entry, {field_name}))
        if summary:
            return summary

    return None


def _extract_entry_author(entry: ElementTree.Element) -> str | None:
    author_node = _first_child(entry, {"author"})
    if author_node is not None:
        author_name = _strip_html_text(_first_text(author_node, {"name"}))
        if author_name:
            return author_name

        author_inline = _strip_html_text("".join(author_node.itertext()))
        if author_inline:
            return author_inline

    for field_name in ("creator", "author"):
        author_value = _strip_html_text(_first_text(entry, {field_name}))
        if author_value:
            return author_value
    return None


def _extract_entry_published_at(entry: ElementTree.Element) -> datetime | None:
    return _parse_first_datetime(entry, _ENTRY_PUBLISHED_AT_FIELDS)


def _extract_entry_image_url(entry: ElementTree.Element) -> str | None:
    image_candidates: list[_ImageCandidate] = []
    candidate_indexes: dict[str, int] = {}

    for node in entry.iter():
        if node is entry:
            continue

        node_name = _local_name(node.tag)
        if node_name == "img":
            _append_node_image_candidates(
                image_candidates,
                candidate_indexes,
                image_url=node.attrib.get("src"),
                width=node.attrib.get("width"),
                height=node.attrib.get("height"),
                srcset=node.attrib.get("srcset"),
            )
            continue

        if node_name in _STRUCTURED_IMAGE_NODE_NAMES:
            _append_node_image_candidates(
                image_candidates,
                candidate_indexes,
                image_url=node.attrib.get("url") or node.attrib.get("href"),
                width=node.attrib.get("width"),
                height=node.attrib.get("height"),
                srcset=node.attrib.get("srcset"),
            )
            continue

        if node_name == "link":
            rel = _clean_text(node.attrib.get("rel"))
            link_type = _clean_text(node.attrib.get("type"))
            href = _clean_text(node.attrib.get("href"))
            if rel == "enclosure" and href and (link_type or "").startswith("image/"):
                _append_image_candidate(
                    image_candidates,
                    candidate_indexes,
                    image_url=href,
                    width=node.attrib.get("width"),
                    height=node.attrib.get("height"),
                )

    for field_name in ("encoded", "content", "description", "summary"):
        _append_html_image_candidates(
            image_candidates,
            candidate_indexes,
            _first_text(entry, {field_name}),
        )

    return _select_best_image_url(image_candidates)


def _append_node_image_candidates(
    image_candidates: list[_ImageCandidate],
    candidate_indexes: dict[str, int],
    *,
    image_url: str | None,
    width: str | int | None,
    height: str | int | None,
    srcset: str | None,
) -> None:
    _append_image_candidate(
        image_candidates,
        candidate_indexes,
        image_url=image_url,
        width=width,
        height=height,
    )
    _append_srcset_candidates(
        image_candidates,
        candidate_indexes,
        srcset=srcset,
        fallback_height=height,
    )


def _append_image_candidate(
    image_candidates: list[_ImageCandidate],
    candidate_indexes: dict[str, int],
    *,
    image_url: str | None,
    width: str | int | None = None,
    height: str | int | None = None,
) -> None:
    cleaned_image_url = _clean_text(html.unescape(image_url)) if image_url is not None else None
    if cleaned_image_url is None:
        return
    query_width, query_height = _extract_image_dimensions_from_query(cleaned_image_url)
    candidate_width = _max_dimension(_parse_dimension(width), query_width)
    candidate_height = _max_dimension(_parse_dimension(height), query_height)

    existing_index = candidate_indexes.get(cleaned_image_url)
    if existing_index is not None:
        existing = image_candidates[existing_index]
        image_candidates[existing_index] = _ImageCandidate(
            url=existing.url,
            width=_max_dimension(existing.width, candidate_width),
            height=_max_dimension(existing.height, candidate_height),
        )
        return

    image_candidates.append(
        _ImageCandidate(
            url=cleaned_image_url,
            width=candidate_width,
            height=candidate_height,
        )
    )
    candidate_indexes[cleaned_image_url] = len(image_candidates) - 1


def _append_srcset_candidates(
    image_candidates: list[_ImageCandidate],
    candidate_indexes: dict[str, int],
    *,
    srcset: str | None,
    fallback_height: str | int | None = None,
) -> None:
    cleaned_srcset = _clean_text(html.unescape(srcset)) if srcset is not None else None
    if cleaned_srcset is None:
        return

    for raw_candidate in cleaned_srcset.split(","):
        cleaned_candidate = _clean_text(raw_candidate)
        if cleaned_candidate is None:
            continue

        image_candidate, *descriptors = cleaned_candidate.split(maxsplit=1)
        image_url = _clean_text(image_candidate)
        descriptor = descriptors[0] if descriptors else None
        _append_image_candidate(
            image_candidates,
            candidate_indexes,
            image_url=image_url,
            width=_parse_srcset_width(descriptor),
            height=fallback_height,
        )


def _append_html_image_candidates(
    image_candidates: list[_ImageCandidate],
    candidate_indexes: dict[str, int],
    value: str | None,
) -> None:
    cleaned_html = _clean_text(value)
    if cleaned_html is None:
        return

    for image_tag_match in _IMAGE_TAG_RE.finditer(cleaned_html):
        image_tag = image_tag_match.group(0)
        width = _extract_html_attribute(image_tag, "width")
        height = _extract_html_attribute(image_tag, "height")
        _append_image_candidate(
            image_candidates,
            candidate_indexes,
            image_url=_extract_html_attribute(image_tag, "src"),
            width=width,
            height=height,
        )
        _append_srcset_candidates(
            image_candidates,
            candidate_indexes,
            srcset=_extract_html_attribute(image_tag, "srcset"),
            fallback_height=height,
        )


def _select_best_image_url(image_candidates: list[_ImageCandidate]) -> str | None:
    if not image_candidates:
        return None

    best_with_width = max(
        (candidate for candidate in image_candidates if candidate.width is not None),
        key=lambda candidate: (candidate.width or 0, candidate.height or 0),
        default=None,
    )
    if best_with_width is not None:
        return best_with_width.url
    return image_candidates[0].url


def _extract_image_dimensions_from_query(image_url: str) -> tuple[int | None, int | None]:
    parsed_url = urlsplit(image_url)
    width: int | None = None
    height: int | None = None

    for key, value in parse_qsl(parsed_url.query, keep_blank_values=False):
        key_lower = key.lower()
        if key_lower in _WIDTH_QUERY_PARAM_NAMES:
            width = _max_dimension(width, _parse_dimension(value))
            continue
        if key_lower in _HEIGHT_QUERY_PARAM_NAMES:
            height = _max_dimension(height, _parse_dimension(value))

    return width, height


def _parse_srcset_width(value: str | None) -> int | None:
    descriptor = _clean_text(value)
    if descriptor is None:
        return None

    descriptor_lower = descriptor.lower()
    if descriptor_lower.endswith("w"):
        return _parse_dimension(descriptor_lower[:-1])
    return None


def _extract_html_attribute(tag: str, attribute_name: str) -> str | None:
    attr_match = re.search(
        rf"""\b{re.escape(attribute_name)}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
        tag,
        flags=re.IGNORECASE,
    )
    if attr_match is None:
        return None

    for group_value in attr_match.groups():
        if group_value is None:
            continue
        return _clean_text(html.unescape(group_value))
    return None


def _parse_dimension(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None

    if not isinstance(value, str):
        return None

    digits_match = _DIGIT_RE.search(value)
    if digits_match is None:
        return None

    parsed_value = int(digits_match.group(0))
    if parsed_value <= 0:
        return None
    return parsed_value


def _max_dimension(*values: int | None) -> int | None:
    max_dimension: int | None = None
    for value in values:
        if value is None or value <= 0:
            continue
        if max_dimension is None or value > max_dimension:
            max_dimension = value
    return max_dimension


def _first_child(
    node: ElementTree.Element,
    names: set[str],
) -> ElementTree.Element | None:
    for child in node:
        if _local_name(child.tag) in names:
            return child
    return None


def _first_text(
    node: ElementTree.Element,
    names: set[str],
) -> str | None:
    for child in node:
        if _local_name(child.tag) not in names:
            continue
        text = _clean_text("".join(child.itertext()))
        if text:
            return text
    return None


def _parse_first_datetime(
    node: ElementTree.Element,
    field_names: tuple[str, ...],
) -> datetime | None:
    for field_name in field_names:
        parsed = _parse_datetime(_first_text(node, {field_name}))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None

    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _strip_html_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None

    without_tags = _HTML_TAG_RE.sub(" ", html.unescape(cleaned))
    normalized = " ".join(without_tags.split())
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    return _clean_text(normalized)


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    if ":" in tag:
        return tag.rsplit(":", 1)[-1].lower()
    return tag.lower()
