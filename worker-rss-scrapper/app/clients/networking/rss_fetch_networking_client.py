from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

import httpx

from app.domain import normalize_feed_sources, parse_rss_feed_entries
from app.schemas.scrape_job_schema import ScrapeJobFeedSchema
from app.schemas.scrape_result_schema import ScrapeResultSchema

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 1.0

DEFAULT_RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept": (
        "application/rss+xml, application/atom+xml, "
        "application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
}


async def fetch_feed_result(
    *,
    feed: ScrapeJobFeedSchema,
    ingest: bool,
    http_client: httpx.AsyncClient | None = None,
) -> ScrapeResultSchema:
    if feed.fetchprotection == 0:
        return _error_result(
            job_id="",
            ingest=ingest,
            feed=feed,
            error_message="Blocked by fetch protection",
        )

    request_headers = _build_request_headers(feed)

    try:
        response = await _perform_request_with_retry(
            url=feed.feed_url,
            headers=request_headers,
            client=http_client,
        )
    except httpx.TimeoutException:
        return _error_result(
            job_id="",
            ingest=ingest,
            feed=feed,
            error_message="Request timeout",
        )
    except httpx.RequestError as exception:
        return _error_result(
            job_id="",
            ingest=ingest,
            feed=feed,
            error_message=f"Request error: {exception}",
        )
    except Exception as exception:
        return _error_result(
            job_id="",
            ingest=ingest,
            feed=feed,
            error_message=f"Unknown fetch error: {exception}",
        )

    response_etag = _clean_header_value(response.headers.get("etag"))
    response_last_modified = _parse_http_date(response.headers.get("last-modified"))
    if response.status_code == 304:
        return ScrapeResultSchema(
            job_id="",
            ingest=ingest,
            feed_id=feed.feed_id,
            feed_url=feed.feed_url,
            status="not_modified",
            fetchprotection=feed.fetchprotection,
            new_etag=response_etag,
            new_last_update=response_last_modified,
            sources=[],
        )

    if _is_same_version(
        feed=feed,
        response_etag=response_etag,
        response_last_modified=response_last_modified,
    ):
        return ScrapeResultSchema(
            job_id="",
            ingest=ingest,
            feed_id=feed.feed_id,
            feed_url=feed.feed_url,
            status="not_modified",
            fetchprotection=feed.fetchprotection,
            new_etag=response_etag,
            new_last_update=response_last_modified,
            sources=[],
        )

    try:
        parsed_entries, parsed_last_modified = parse_rss_feed_entries(response.text)
        normalized_sources = normalize_feed_sources(parsed_entries)
    except Exception as exception:
        return _error_result(
            job_id="",
            ingest=ingest,
            feed=feed,
            error_message=f"Feed parse error: {exception}",
            etag=response_etag,
            last_update=response_last_modified,
        )

    return ScrapeResultSchema(
        job_id="",
        ingest=ingest,
        feed_id=feed.feed_id,
        feed_url=feed.feed_url,
        status="success",
        fetchprotection=feed.fetchprotection,
        new_etag=response_etag,
        new_last_update=response_last_modified or parsed_last_modified,
        sources=normalized_sources,
    )


def _build_request_headers(feed: ScrapeJobFeedSchema) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    if feed.fetchprotection == 2:
        headers.update(DEFAULT_RSS_HEADERS)
        if feed.host_header:
            host = feed.host_header.strip().lower()
            origin = f"https://{host}"
            headers["Host"] = host
            headers["Origin"] = origin
            headers["Referer"] = f"{origin}/"

    cleaned_etag = _clean_header_value(feed.etag)
    if cleaned_etag is not None:
        headers["If-None-Match"] = cleaned_etag

    if feed.last_update is not None:
        headers["If-Modified-Since"] = _format_http_date(feed.last_update)

    if not headers:
        return None
    return headers


async def _perform_request_with_retry(
    *,
    url: str,
    headers: dict[str, str] | None,
    client: httpx.AsyncClient | None,
) -> httpx.Response:
    attempt = 0
    last_exception: Exception | None = None

    while attempt < DEFAULT_MAX_ATTEMPTS:
        attempt += 1
        try:
            if client is None:
                async with httpx.AsyncClient(
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                    follow_redirects=True,
                ) as transient_client:
                    response = await transient_client.get(url, headers=headers)
            else:
                response = await client.get(url, headers=headers)

            if response.status_code in {200, 304}:
                return response
            raise httpx.RequestError(
                f"HTTP {response.status_code} while checking {url}",
                request=response.request,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exception:
            last_exception = exception
            if attempt >= DEFAULT_MAX_ATTEMPTS:
                break
            await asyncio.sleep(DEFAULT_BACKOFF_SECONDS * attempt)

    if last_exception is None:
        raise httpx.RequestError("Request failed")
    raise last_exception


def _error_result(
    *,
    job_id: str,
    ingest: bool,
    feed: ScrapeJobFeedSchema,
    error_message: str,
    etag: str | None = None,
    last_update: datetime | None = None,
) -> ScrapeResultSchema:
    return ScrapeResultSchema(
        job_id=job_id,
        ingest=ingest,
        feed_id=feed.feed_id,
        feed_url=feed.feed_url,
        status="error",
        error_message=error_message,
        fetchprotection=feed.fetchprotection,
        new_etag=etag,
        new_last_update=last_update,
        sources=[],
    )


def _is_same_version(
    *,
    feed: ScrapeJobFeedSchema,
    response_etag: str | None,
    response_last_modified: datetime | None,
) -> bool:
    if feed.last_update is not None and response_last_modified is not None:
        if _normalize_datetime(feed.last_update) == _normalize_datetime(response_last_modified):
            return True
    if feed.etag is not None and response_etag is not None:
        if feed.etag.strip() == response_etag:
            return True
    return False


def _format_http_date(value: datetime) -> str:
    normalized = _normalize_datetime(value)
    return format_datetime(normalized, usegmt=True)


def _parse_http_date(value: str | None) -> datetime | None:
    cleaned_value = _clean_header_value(value)
    if cleaned_value is None:
        return None
    try:
        parsed = parsedate_to_datetime(cleaned_value)
    except (TypeError, ValueError):
        return None
    return _normalize_datetime(parsed)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_header_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
