from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
import os
import httpx

from app.schemas import ScrapeJobFeedSchema, ScrapeJobRequestSchema
from app.services.worker_auth_service import ensure_worker_authenticated
from app.clients.networking import fetch_feed_result
from app.errors.worker_exceptions import WorkerAuthenticationError, WorkerQueueError
from app.clients.queue import (
    ack_scrape_job,
    ensure_worker_consumer_group,
    publish_check_result,
    publish_error_result,
    publish_ingest_result,
    read_scrape_jobs,
)

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_READ_COUNT = 20
DEFAULT_COMPANY_MAX_REQUESTS_PER_SECOND = 4
DEFAULT_QUEUE_BLOCK_MS = 5000


class CompanyRateLimiter:
    def __init__(self, *, max_requests_per_second: int) -> None:
        self._semaphore = asyncio.Semaphore(max_requests_per_second)

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        asyncio.get_running_loop().call_later(1.0, self._semaphore.release)


async def run_scrape_worker() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await ensure_worker_consumer_group()
    logger.info("worker_rss_scrapper started")

    queue_read_count = _resolve_queue_read_count()
    company_max_rps = _resolve_company_max_requests_per_second()
    company_rate_limiters: dict[str, CompanyRateLimiter] = {}

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
        while True:
            try:
                await ensure_worker_authenticated()
                jobs = await read_scrape_jobs(
                    count=queue_read_count,
                    block_ms=DEFAULT_QUEUE_BLOCK_MS,
                )
                if not jobs:
                    continue

                await asyncio.gather(
                    *[
                        _process_job_message(
                            message_id=message_id,
                            payload=payload,
                            http_client=http_client,
                            company_rate_limiters=company_rate_limiters,
                            company_max_rps=company_max_rps,
                        )
                        for message_id, payload in jobs
                    ]
                )
            except WorkerAuthenticationError as exception:
                logger.warning("Worker authentication unavailable: %s", exception)
                await asyncio.sleep(1.0)
            except WorkerQueueError as exception:
                logger.warning("Worker queue unavailable: %s", exception)
                await asyncio.sleep(1.0)
            except Exception as exception:
                logger.exception("Worker loop error: %s", exception)
                await asyncio.sleep(1.0)


async def _process_job_message(
    *,
    message_id: str,
    payload: dict,
    http_client: httpx.AsyncClient,
    company_rate_limiters: dict[str, CompanyRateLimiter],
    company_max_rps: int,
) -> None:
    try:
        scrape_job = ScrapeJobRequestSchema.model_validate(payload)
    except Exception as exception:
        logger.error("Invalid scrape job payload for message %s: %s", message_id, exception)
        await ack_scrape_job(message_id)
        return

    feeds_by_company = _group_feeds_by_company(scrape_job.feeds)
    await asyncio.gather(
        *[
            _process_company_feed_pool(
                scrape_job=scrape_job,
                feeds=company_feeds,
                company_key=company_key,
                http_client=http_client,
                company_rate_limiters=company_rate_limiters,
                company_max_rps=company_max_rps,
            )
            for company_key, company_feeds in feeds_by_company.items()
        ]
    )

    await ack_scrape_job(message_id)


async def _process_company_feed_pool(
    *,
    scrape_job: ScrapeJobRequestSchema,
    feeds: list[ScrapeJobFeedSchema],
    company_key: str,
    http_client: httpx.AsyncClient,
    company_rate_limiters: dict[str, CompanyRateLimiter],
    company_max_rps: int,
) -> None:
    limiter = _get_or_create_company_rate_limiter(
        company_key=company_key,
        company_rate_limiters=company_rate_limiters,
        company_max_rps=company_max_rps,
    )
    await asyncio.gather(
        *[
            _process_feed(
                scrape_job=scrape_job,
                feed=feed,
                http_client=http_client,
                limiter=limiter,
            )
            for feed in feeds
        ]
    )


async def _process_feed(
    *,
    scrape_job: ScrapeJobRequestSchema,
    feed: ScrapeJobFeedSchema,
    http_client: httpx.AsyncClient,
    limiter: CompanyRateLimiter,
) -> None:
    await limiter.acquire()

    result = await fetch_feed_result(
        feed=feed,
        ingest=scrape_job.ingest,
        http_client=http_client,
    )
    result = result.model_copy(update={"job_id": scrape_job.job_id, "ingest": scrape_job.ingest})
    result_payload = result.model_dump(mode="json")

    if result.status == "error":
        await publish_error_result(result_payload)
        return

    if scrape_job.ingest:
        await publish_ingest_result(result_payload)
    else:
        await publish_check_result(result_payload)


def _group_feeds_by_company(feeds: list[ScrapeJobFeedSchema]) -> dict[str, list[ScrapeJobFeedSchema]]:
    feeds_by_company: dict[str, list[ScrapeJobFeedSchema]] = defaultdict(list)
    for feed in feeds:
        company_key = _resolve_company_key(feed)
        feeds_by_company[company_key].append(feed)
    return feeds_by_company


def _resolve_company_key(feed: ScrapeJobFeedSchema) -> str:
    if isinstance(feed.company_id, int) and feed.company_id > 0:
        return f"company:{feed.company_id}"
    return f"feed:{feed.feed_id}"


def _get_or_create_company_rate_limiter(
    *,
    company_key: str,
    company_rate_limiters: dict[str, CompanyRateLimiter],
    company_max_rps: int,
) -> CompanyRateLimiter:
    limiter = company_rate_limiters.get(company_key)
    if limiter is None:
        limiter = CompanyRateLimiter(max_requests_per_second=company_max_rps)
        company_rate_limiters[company_key] = limiter
    return limiter


def _resolve_queue_read_count() -> int:
    raw_value = os.getenv("WORKER_QUEUE_READ_COUNT", str(DEFAULT_QUEUE_READ_COUNT))
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_QUEUE_READ_COUNT
    if parsed <= 0:
        return DEFAULT_QUEUE_READ_COUNT
    return parsed


def _resolve_company_max_requests_per_second() -> int:
    raw_value = os.getenv(
        "WORKER_COMPANY_MAX_REQUESTS_PER_SECOND",
        str(DEFAULT_COMPANY_MAX_REQUESTS_PER_SECOND),
    )
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_COMPANY_MAX_REQUESTS_PER_SECOND
    if parsed <= 0:
        return DEFAULT_COMPANY_MAX_REQUESTS_PER_SECOND
    return parsed
