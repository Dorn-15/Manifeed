from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

DEFAULT_HTTPX_TIMEOUT = 10.0
DEFAULT_HTTPX_FOLLOW_REDIRECTS = True
DEFAULT_HTTPX_LIMITS = httpx.Limits(
    max_connections=50,
    max_keepalive_connections=20,
)

DEFAULT_RSS_CHECK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8,de;q=0.7,es;q=0.6,it;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

STRONG_BROWSER_HEADERS = {
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
}
DEFAULT_BROWSER_HEADERS = {
    **DEFAULT_RSS_CHECK_HEADERS,
    **STRONG_BROWSER_HEADERS,
}

TLS_CERT_REASON_MARKERS = (
    "certificate verify failed",
    "no alternative certificate",
    "certificate",
    "certificat",
)

FETCHPROTECTION_BLOCKED = 0
FETCHPROTECTION_BASIC = 1
FETCHPROTECTION_RSS_HEADERS = 2
FETCHPROTECTION_BROWSER_REFERER = 3
FETCHPROTECTION_METHODS = (
    FETCHPROTECTION_BASIC,
    FETCHPROTECTION_RSS_HEADERS,
    FETCHPROTECTION_BROWSER_REFERER,
)
HttpxProbeValidator = Callable[[str, str], tuple[bool, str | None]]


@dataclass(slots=True)
class HttpxProbeResult:
    fetchprotection: int
    content: str | None = None
    content_type: str | None = None
    error: str | None = None


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


async def get_httpx_basic(
    url: str,
    *,
    header: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
) -> tuple[str, str]:
    return await _fetch_with_headers(
        url=url,
        headers=header,
        timeout=timeout,
        follow_redirects=follow_redirects,
        client=client,
        allowed_status_codes=allowed_status_codes,
    )


async def get_httpx_rss_headers(
    url: str,
    *,
    header: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
) -> tuple[str, str]:
    rss_headers = DEFAULT_RSS_CHECK_HEADERS.copy()
    rss_headers.update(header)
    return await _fetch_with_headers(
        url=url,
        headers=rss_headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
        client=client,
        allowed_status_codes=allowed_status_codes,
    )


async def get_httpx_browser_referer(
    url: str,
    *,
    header: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
) -> tuple[str, str]:
    browser_headers = DEFAULT_BROWSER_HEADERS.copy()
    if header:
        browser_headers.update(header)
    return await _fetch_with_headers(
        url=url,
        headers=browser_headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
        client=client,
        allowed_status_codes=allowed_status_codes,
    )


async def get_httpx_by_method(
    url: str,
    *,
    fetchprotection: int,
    header: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
) -> tuple[str, str]:
    if fetchprotection <= FETCHPROTECTION_BASIC:
        return await get_httpx_basic(
            url=url,
            header=header,
            timeout=timeout,
            follow_redirects=follow_redirects,
            client=client,
            allowed_status_codes=allowed_status_codes,
        )
    if fetchprotection == FETCHPROTECTION_RSS_HEADERS:
        return await get_httpx_rss_headers(
            url=url,
            header=header,
            timeout=timeout,
            follow_redirects=follow_redirects,
            client=client,
            allowed_status_codes=allowed_status_codes,
        )
    return await get_httpx_browser_referer(
        url=url,
        header=header,
        timeout=timeout,
        follow_redirects=follow_redirects,
        client=client,
        allowed_status_codes=allowed_status_codes,
    )


async def get_httpx(
    url: str,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
    fetchprotection: int = FETCHPROTECTION_BASIC,
    header: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    return await get_httpx_by_method(
        url=url,
        fetchprotection=fetchprotection,
        header=header,
        timeout=timeout,
        follow_redirects=follow_redirects,
        client=client,
        allowed_status_codes=allowed_status_codes,
    )


async def probe_httpx_methods(
    url: str,
    *,
    header: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_HTTPX_TIMEOUT,
    follow_redirects: bool = DEFAULT_HTTPX_FOLLOW_REDIRECTS,
    client: httpx.AsyncClient | None = None,
    allowed_status_codes: Collection[int] = (200,),
    methods: Collection[int] = FETCHPROTECTION_METHODS,
    validator: HttpxProbeValidator | None = None,
) -> HttpxProbeResult:
    probe_methods = tuple(methods)
    if not probe_methods:
        raise ValueError("methods must not be empty")

    last_error: str | None = None

    for method in probe_methods:
        try:
            method_header = (
                header
                if method == FETCHPROTECTION_BROWSER_REFERER
                else None
            )
            content, content_type = await get_httpx_by_method(
                url=url,
                fetchprotection=method,
                header=method_header,
                timeout=timeout,
                follow_redirects=follow_redirects,
                client=client,
                allowed_status_codes=allowed_status_codes,
            )
            if validator is not None:
                is_valid, validation_error = validator(content, content_type)
                if not is_valid:
                    last_error = validation_error or "Invalid payload"
                    continue

            return HttpxProbeResult(
                fetchprotection=method,
                content=content,
                content_type=content_type,
            )
        except httpx.TimeoutException:
            last_error = "Request timeout"
        except httpx.RequestError as exception:
            last_error = f"Request error: {exception}"
        except Exception as exception:
            last_error = f"Unknown fetch error: {exception}"

    return HttpxProbeResult(
        fetchprotection=FETCHPROTECTION_BLOCKED,
        error=last_error or "Blocked by fetch protection",
    )


async def _fetch_with_headers(
    *,
    url: str,
    headers: Mapping[str, str] | None,
    timeout: float,
    follow_redirects: bool,
    client: httpx.AsyncClient | None,
    allowed_status_codes: Collection[int],
) -> tuple[str, str]:
    if client is None:
        async with get_httpx_config(
            timeout=timeout,
            follow_redirects=follow_redirects,
        ) as transient_client:
            response = await _get_response(
                client=transient_client,
                url=url,
                headers=headers,
                allowed_status_codes=allowed_status_codes,
            )
    else:
        response = await _get_response(
            client=client,
            url=url,
            headers=headers,
            allowed_status_codes=allowed_status_codes,
        )

    content_type = response.headers.get("content-type", "")
    return response.text, content_type


async def _get_response(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: Mapping[str, str] | None,
    allowed_status_codes: Collection[int],
) -> httpx.Response:
    accepted_status_codes = set(allowed_status_codes)
    if not accepted_status_codes:
        raise ValueError("allowed_status_codes must not be empty")

    try:
        response = await client.get(url, headers=headers)
    except httpx.RequestError as exception:
        if not _is_tls_certificate_error(str(exception)) or not _is_https_url(url):
            raise

        fallback_url = _replace_scheme(url, "http")
        if fallback_url == url:
            raise
        response = await client.get(fallback_url, headers=headers)

    if response.status_code in accepted_status_codes:
        return response

    raise httpx.RequestError(
        f"HTTP {response.status_code} while checking {url}",
        request=response.request,
    )

def _replace_scheme(url: str, scheme: str) -> str:
    try:
        parsed = urlsplit(url)
    except Exception:
        return url

    if not parsed.netloc:
        return url
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _is_https_url(url: str) -> bool:
    try:
        return urlsplit(url).scheme.lower() == "https"
    except Exception:
        return False


def _is_tls_certificate_error(reason: str | None) -> bool:
    normalized_reason = (reason or "").strip().lower()
    if not normalized_reason:
        return False
    return any(marker in normalized_reason for marker in TLS_CERT_REASON_MARKERS)
