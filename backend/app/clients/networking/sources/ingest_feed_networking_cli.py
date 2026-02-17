from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
from typing import Any
from xml.etree import ElementTree
import httpx

from app.clients.networking import get_httpx
from app.models.rss import RssFeed
from app.schemas.sources import RssFeedFetchPayloadSchema

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_IMAGE_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


async def fetch_rss_feed_entries(
    feed: RssFeed,
    http_client: httpx.AsyncClient | None = None,
) -> RssFeedFetchPayloadSchema:
    try:
        content, _ = await get_httpx(url=feed.url, client=http_client)
    except httpx.TimeoutException:
        return RssFeedFetchPayloadSchema(status="error", error="Request timeout")
    except httpx.RequestError as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Request error: {exception}")
    except Exception as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Unknown fetch error: {exception}")

    try:
        entries, last_modified = parse_rss_feed_entries(content)
    except Exception as exception:
        return RssFeedFetchPayloadSchema(status="error", error=f"Feed parse error: {exception}")

    if last_modified is not None and feed.last_update is not None and last_modified == feed.last_update:
        return RssFeedFetchPayloadSchema(status="not_modified", last_modified=last_modified)

    return RssFeedFetchPayloadSchema(
        status="success",
        entries=entries,
        last_modified=last_modified,
    )


def parse_rss_feed_entries(content: str) -> tuple[list[dict[str, Any]], datetime | None]:
    if not content or not content.strip():
        raise ValueError("Empty feed content")

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exception:
        raise ValueError(f"Invalid XML: {exception}") from exception

    last_modified = _extract_last_modified(root)
    entry_nodes = _extract_entry_nodes(root)

    entries: list[dict[str, Any]] = []
    index = 0
    while index < len(entry_nodes):
        node = entry_nodes[index]
        index += 1
        payload = _extract_entry_payload(node)
        if payload is None:
            continue
        entries.append(payload)
    return entries, last_modified


def _extract_entry_nodes(root: ElementTree.Element) -> list[ElementTree.Element]:
    root_tag = _local_name(root.tag)
    if root_tag == "rss":
        channel = _first_child(root, {"channel"})
        if channel is None:
            return []
        return [child for child in list(channel) if _local_name(child.tag) == "item"]

    if root_tag == "feed":
        return [child for child in list(root) if _local_name(child.tag) == "entry"]

    return [
        node
        for node in root.iter()
        if _local_name(node.tag) in {"item", "entry"}
    ]


def _extract_last_modified(root: ElementTree.Element) -> datetime | None:
    if _local_name(root.tag) == "rss":
        channel = _first_child(root, {"channel"})
        if channel is not None:
            for field in ("lastbuilddate", "pubdate", "updated"):
                value = _first_text(channel, {field})
                parsed = _parse_datetime(value)
                if parsed is not None:
                    return parsed

    for field in ("updated", "lastbuilddate", "pubdate"):
        value = _first_text(root, {field})
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _extract_entry_payload(entry: ElementTree.Element) -> dict[str, Any] | None:
    title = _first_text(entry, {"title"})
    url = _extract_entry_url(entry)
    if title is None or url is None:
        return None

    return {
        "title": title,
        "summary": _extract_entry_summary(entry),
        "url": url,
        "published_at": _extract_entry_published_at(entry),
        "image_url": _extract_entry_image_url(entry),
    }   


def _extract_entry_url(entry: ElementTree.Element) -> str | None:
    link_text = _first_text(entry, {"link"})
    if link_text:
        return link_text

    links = [node for node in list(entry) if _local_name(node.tag) == "link"]
    index = 0
    fallback_url: str | None = None
    while index < len(links):
        link = links[index]
        index += 1
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

    summary = _strip_html_text(_first_text(entry, {"encoded"}))
    if summary:
        return summary

    summary = _strip_html_text(_first_text(entry, {"content"}))
    if summary:
        return summary

    return None


def _extract_entry_published_at(entry: ElementTree.Element) -> datetime | None:
    for field_name in ("pubdate", "published", "updated", "date"):
        value = _first_text(entry, {field_name})
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _extract_entry_image_url(entry: ElementTree.Element) -> str | None:
    for node in entry.iter():
        if node is entry:
            continue

        node_name = _local_name(node.tag)
        if node_name == "img":
            image_url = _clean_text(node.attrib.get("src"))
            if image_url is not None:
                return html.unescape(image_url)

        if node_name in {"thumbnail", "content", "enclosure", "image"}:
            image_url = _clean_text(node.attrib.get("url") or node.attrib.get("href"))
            if image_url is not None:
                return image_url

        if node_name == "link":
            rel = _clean_text(node.attrib.get("rel"))
            link_type = _clean_text(node.attrib.get("type"))
            href = _clean_text(node.attrib.get("href"))
            if rel == "enclosure" and href and (link_type or "").startswith("image/"):
                return href

    for field_name in ("encoded", "content", "description", "summary"):
        image_url = _extract_first_image_src_from_html(_first_text(entry, {field_name}))
        if image_url is not None:
            return image_url
    return None


def _first_child(
    node: ElementTree.Element,
    names: set[str],
) -> ElementTree.Element | None:
    for child in list(node):
        if _local_name(child.tag) in names:
            return child
    return None


def _first_text(
    node: ElementTree.Element,
    names: set[str],
) -> str | None:
    for child in list(node):
        if _local_name(child.tag) not in names:
            continue
        text = _clean_text("".join(child.itertext()))
        if text:
            return text
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


def _extract_first_image_src_from_html(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None

    match = _IMAGE_SRC_RE.search(cleaned)
    if match is None:
        return None
    return _clean_text(html.unescape(match.group(1)))


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    if ":" in tag:
        return tag.rsplit(":", 1)[-1].lower()
    return tag.lower()
