from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

import httpx
from sqlalchemy.orm import Session

from app.clients.database.rss import list_rss_feeds
from app.domain.rss import validate_rss_feed_payload
from app.models.rss import RssFeed
from app.schemas.rss import RssFeedCheckResultRead
from app.clients.networking import (
    get_httpx_config,
    probe_httpx_methods,
)
from app.utils import normalize_host

DEFAULT_MAX_CONCURRENT_CHECKS = 5
CheckStatus = Literal["valid", "invalid"]


async def check_rss_feeds(
    db: Session,
    feed_ids: list[int] | None = None,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT_CHECKS,
) -> list[RssFeedCheckResultRead]:
    feeds = list_rss_feeds(db, feed_ids=feed_ids)
    if not feeds:
        return []

    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    checked_at = datetime.now(timezone.utc)

    async with get_httpx_config() as http_client:
        async def run_check(feed: RssFeed) -> RssFeedCheckResultRead | None:
            async with semaphore:
                status, error, fetchprotection = await _check_single_feed(
                    feed=feed,
                    http_client=http_client,
                )
                feed.fetchprotection = fetchprotection
                feed.last_update = checked_at
                if status == "valid":
                    return None
                return RssFeedCheckResultRead(
                    feed_id=feed.id,
                    url=feed.url,
                    status="invalid",
                    error=error or "Invalid RSS feed",
                    fetchprotection=fetchprotection,
                )

        check_results = await asyncio.gather(*(run_check(feed) for feed in feeds))

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return [result for result in check_results if result is not None]


async def _check_single_feed(
    feed: RssFeed,
    http_client: httpx.AsyncClient | None = None,
) -> tuple[CheckStatus, str | None, int]:
    header = _resolve_feed_header(feed)

    probe_result = await probe_httpx_methods(
        url=feed.url,
        header=header,
        client=http_client,
        validator=_validate_rss_payload,
    )
    if probe_result.content is None or probe_result.content_type is None:
        return (
            "invalid",
            probe_result.error or "Blocked by fetch protection",
            probe_result.fetchprotection,
        )
    return "valid", None, probe_result.fetchprotection


def _validate_rss_payload(content: str, content_type: str) -> tuple[bool, str | None]:
    status, error = validate_rss_feed_payload(content=content, content_type=content_type)
    return status == "valid", error


def _resolve_feed_header(feed: RssFeed) -> dict[str, str] | None:
    company = getattr(feed, "company", None)
    host = normalize_host(getattr(company, "host", None))
    if host is None:
        return None

    origin = f"https://{host}"
    return {
        "Origin": origin,
        "Referer": f"{origin}/",
    }
