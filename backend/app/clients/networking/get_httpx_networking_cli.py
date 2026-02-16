from __future__ import annotations

from collections.abc import Mapping, Collection
import httpx

DEFAULT_HTTPX_TIMEOUT = 10.0
DEFAULT_HTTPX_FOLLOW_REDIRECTS = True
DEFAULT_HTTPX_LIMITS = httpx.Limits(
    max_connections=50,
    max_keepalive_connections=20,
)

DEFAULT_RSS_CHECK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "text/html, application/rss+xml, application/xml, application/atom+xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


def get_httpx_config(
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    headers: Mapping[str, str] | None = None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        headers=headers,
        limits=DEFAULT_HTTPX_LIMITS,
    )


async def get_httpx(
    url: str,
    timeout: float = 10.0,
    follow_redirects: bool = True,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
) -> tuple[str, str]:
    """
    Fetch feed payload and return (content, content_type).
    Tries once without headers, then retries with browser-like headers.
    """
    if client is None:
        async with get_httpx_config(
            timeout=timeout,
            follow_redirects=follow_redirects,
        ) as transient_client:
            response = await _get_with_retry(
                client=transient_client,
                url=url,
                allowed_status_codes=allowed_status_codes,
            )
    else:
        response = await _get_with_retry(
            client=client,
            url=url,
            allowed_status_codes=allowed_status_codes,
        )

    content_type = response.headers.get("content-type", "")
    return response.text, content_type

async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    allowed_status_codes: Collection[int] = (200,),
) -> httpx.Response:
    accepted_status_codes = set(allowed_status_codes)
    if not accepted_status_codes:
        raise ValueError("allowed_status_codes must not be empty")

    try:
        response = await client.get(url)
        if response.status_code in accepted_status_codes:
            return response
    except httpx.RequestError:
        pass

    response = await client.get(url, headers=DEFAULT_RSS_CHECK_HEADERS)
    if response.status_code in accepted_status_codes:
        return response

    raise httpx.RequestError(
        f"HTTP {response.status_code} while checking {url}",
        request=response.request,
    )