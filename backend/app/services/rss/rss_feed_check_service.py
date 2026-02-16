from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.clients.database.rss import list_rss_feeds_for_check
from app.domain.rss import validate_rss_feed_payload
from app.models.rss import RssFeed
from app.schemas.rss import (
    RssFeedCheckRead,
    RssFeedCheckResultRead,
)
from app.clients.networking import (
    get_httpx_config,
    get_httpx,
)

DEFAULT_MAX_CONCURRENT_CHECKS = 5


async def check_rss_feeds(
    db: Session,
    feed_ids: Optional[list[int]] = None,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT_CHECKS,
) -> RssFeedCheckRead:
    feeds = list_rss_feeds_for_check(db, feed_ids=feed_ids)
    if not feeds:
        return RssFeedCheckRead()

    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    checked_at = datetime.now(timezone.utc)
    async with get_httpx_config() as http_client:
        async def run_check(feed: RssFeed) -> tuple[RssFeed, str, Optional[str]]:
            async with semaphore:
                status, error = await _check_single_feed(feed.url, http_client=http_client)
                feed.status = status
                feed.last_update = checked_at
                if status == "invalid":
                    feed.enabled = False
                return feed, status, error

        check_results = await asyncio.gather(*[run_check(feed) for feed in feeds])

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    valid_count = sum(1 for _, status, _ in check_results if status == "valid")
    invalid_results = [
        RssFeedCheckResultRead(
            feed_id=feed.id,
            url=feed.url,
            status="invalid",
            error=error or "Invalid RSS feed",
        )
        for feed, status, error in check_results
        if status == "invalid"
    ]
    return RssFeedCheckRead(
        results=invalid_results,
        valid_count=valid_count,
        invalid_count=len(invalid_results),
    )


async def _check_single_feed(
    url: str,
    http_client: httpx.AsyncClient | None = None,
) -> tuple[str, Optional[str]]:
    try:
        content, content_type = await get_httpx(url=url, client=http_client)
        return validate_rss_feed_payload(content=content, content_type=content_type)
    except httpx.TimeoutException:
        return "invalid", "Request timeout"
    except httpx.RequestError as exception:
        return "invalid", f"Request error: {exception}"
    except Exception as exception:
        return "invalid", f"Unknown error: {exception}"
