from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time

from sqlalchemy.orm import Session

from app.clients.database.rss import list_enabled_rss_feeds
from app.clients.database.sources import (
    create_rss_source,
    link_source_to_feed,
    list_rss_sources_by_urls,
    update_rss_source,
)
from app.clients.networking import get_httpx_config
from app.clients.networking.sources import fetch_rss_feed_entries
from app.domain.sources import normalize_rss_source_candidates
from app.models.rss import RssFeed
from app.schemas.sources import (
    RssFeedFetchPayloadSchema,
    RssSourceCandidateSchema,
    RssSourceIngestErrorRead,
    RssSourceIngestRead,
)
from app.utils import normalize_lang_by_country

DEFAULT_MAX_CONCURRENT_FETCHES = 5


async def ingest_rss_sources(
    db: Session,
    feed_ids: list[int] | None = None,
    max_concurrent_fetches: int = DEFAULT_MAX_CONCURRENT_FETCHES,
) -> RssSourceIngestRead:
    started_at = time.perf_counter()
    counters = _IngestCounters()

    feeds = list_enabled_rss_feeds(db, feed_ids=feed_ids)
    if not feeds:
        return _build_ingest_response(counters, started_at=started_at)

    fetch_results = await _fetch_all_feeds(
        feeds=feeds,
        max_concurrent_fetches=max_concurrent_fetches,
    )
    index = 0
    while index < len(fetch_results):
        feed, fetch_payload = fetch_results[index]
        index += 1

        if fetch_payload.status == "not_modified":
            counters.feeds_skipped += 1
            continue

        if fetch_payload.status == "error":
            counters.errors.append(
                RssSourceIngestErrorRead(
                    feed_id=feed.id,
                    feed_url=feed.url,
                    error=fetch_payload.error or "Unknown feed fetch error",
                )
            )
            db.rollback()
            continue

        if fetch_payload.last_modified is not None:
            feed.last_update = fetch_payload.last_modified

        try:
            candidates = normalize_rss_source_candidates(
                fetch_payload.entries,
                default_language=normalize_lang_by_country(feed.country),
            )
            created_count, updated_count = _upsert_feed_sources(
                db=db,
                feed=feed,
                candidates=candidates,
            )

            db.commit()
            counters.feeds_processed += 1
            counters.sources_created += created_count
            counters.sources_updated += updated_count
        except Exception as exception:
            db.rollback()
            counters.errors.append(
                RssSourceIngestErrorRead(
                    feed_id=feed.id,
                    feed_url=feed.url,
                    error=str(exception),
                )
            )

    return _build_ingest_response(counters, started_at=started_at)


async def _fetch_all_feeds(
    feeds: list[RssFeed],
    max_concurrent_fetches: int,
) -> list[tuple[RssFeed, RssFeedFetchPayloadSchema]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrent_fetches))
    async with get_httpx_config(timeout=15.0, follow_redirects=True) as http_client:
        async def run_fetch(feed: RssFeed) -> tuple[RssFeed, RssFeedFetchPayloadSchema]:
            async with semaphore:
                fetch_payload = await fetch_rss_feed_entries(
                    feed=feed,
                    http_client=http_client,
                )
                return feed, fetch_payload

        return await asyncio.gather(*[run_fetch(feed) for feed in feeds])


def _upsert_feed_sources(
    db: Session,
    feed: RssFeed,
    candidates: list[RssSourceCandidateSchema],
) -> tuple[int, int]:
    sources_created = 0
    sources_updated = 0
    deduplicated_candidates = _deduplicate_candidates(candidates)

    existing_by_url = list_rss_sources_by_urls(
        db=db,
        urls=[candidate.url for candidate in deduplicated_candidates],
    )

    index = 0
    while index < len(deduplicated_candidates):
        candidate = deduplicated_candidates[index]
        index += 1

        source = existing_by_url.get(candidate.url)
        if source is None:
            source = create_rss_source(db=db, payload=candidate)
            existing_by_url[candidate.url] = source
            link_source_to_feed(source=source, feed_id=feed.id)
            sources_created += 1
            continue

        has_changes = update_rss_source(source=source, payload=candidate)
        linked = link_source_to_feed(source=source, feed_id=feed.id)
        if has_changes or linked:
            sources_updated += 1

    return sources_created, sources_updated


def _deduplicate_candidates(
    candidates: list[RssSourceCandidateSchema],
) -> list[RssSourceCandidateSchema]:
    deduplicated: list[RssSourceCandidateSchema] = []
    seen_urls: set[str] = set()

    index = 0
    while index < len(candidates):
        candidate = candidates[index]
        index += 1
        if candidate.url in seen_urls:
            continue
        seen_urls.add(candidate.url)
        deduplicated.append(candidate)
    return deduplicated


def _build_ingest_response(
    counters: "_IngestCounters",
    started_at: float,
) -> RssSourceIngestRead:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    return RssSourceIngestRead(
        status="completed",
        feeds_processed=counters.feeds_processed,
        feeds_skipped=counters.feeds_skipped,
        sources_created=counters.sources_created,
        sources_updated=counters.sources_updated,
        errors=counters.errors,
        duration_ms=duration_ms,
    )


@dataclass
class _IngestCounters:
    feeds_processed: int = 0
    feeds_skipped: int = 0
    sources_created: int = 0
    sources_updated: int = 0
    errors: list[RssSourceIngestErrorRead] = field(default_factory=list)
