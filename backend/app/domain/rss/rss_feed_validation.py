from __future__ import annotations

from typing import Optional
from xml.etree import ElementTree

RssValidationResult = tuple[str, Optional[str]]


def validate_rss_feed_payload(content: str, content_type: str) -> RssValidationResult:
    """Return (status, error). Status is valid|invalid."""
    content_type_lower = content_type.lower()
    content_stripped = content.strip()

    looks_like_xml = (
        "xml" in content_type_lower
        or "rss" in content_type_lower
        or "atom" in content_type_lower
        or content_stripped.startswith("<?xml")
        or content_stripped.startswith("<rss")
        or content_stripped.startswith("<feed")
    )
    if not looks_like_xml:
        return "invalid", "Not an XML/RSS feed"

    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exception:
        return "invalid", f"Invalid XML: {exception}"

    tag_lower = root.tag.lower()
    is_rss = "rss" in tag_lower or root.find("channel") is not None
    is_atom = "feed" in tag_lower or "{http://www.w3.org/2005/Atom}" in root.tag
    if not is_rss and not is_atom:
        return "invalid", "XML but not RSS/Atom format"

    return "valid", None
