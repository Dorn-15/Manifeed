import asyncio

import httpx
import pytest

import app.clients.networking.get_httpx_networking_cli as get_httpx_module

class _FakeResponse:
    def __init__(self, status_code: int, text: str, content_type: str = "application/xml") -> None:
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type}
        self.request = httpx.Request("GET", "https://example.com/rss")


def test_get_httpx_returns_text_and_content_type(monkeypatch) -> None:
    async def fake_get_with_retry(client, url, allowed_status_codes):
        assert url == "https://example.com/rss"
        assert tuple(allowed_status_codes) == (200,)
        return _FakeResponse(
            status_code=200,
            text="<rss><channel></channel></rss>",
            content_type="application/rss+xml",
        )

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    def fake_get_httpx(timeout: float, follow_redirects: bool):
        assert timeout == 10.0
        assert follow_redirects is True
        return FakeAsyncClient()

    monkeypatch.setattr(get_httpx_module, "_get_with_retry", fake_get_with_retry)
    monkeypatch.setattr(get_httpx_module, "get_httpx_config", fake_get_httpx)

    content, content_type = asyncio.run(
        get_httpx_module.get_httpx("https://example.com/rss")
    )

    assert content == "<rss><channel></channel></rss>"
    assert content_type == "application/rss+xml"


def test_get_httpx_uses_provided_client_without_building_new_one(monkeypatch) -> None:
    provided_client = object()

    async def fake_get_with_retry(client, url, allowed_status_codes):
        assert client is provided_client
        assert url == "https://example.com/rss"
        assert tuple(allowed_status_codes) == (200,)
        return _FakeResponse(
            status_code=200,
            text="<rss/>",
            content_type="application/rss+xml",
        )

    monkeypatch.setattr(get_httpx_module, "_get_with_retry", fake_get_with_retry)

    content, content_type = asyncio.run(
        get_httpx_module.get_httpx(
            "https://example.com/rss",
            client=provided_client,
        )
    )

    assert content == "<rss/>"
    assert content_type == "application/rss+xml"


def test_get_with_retry_raises_request_error_on_non_accepted_response() -> None:
    class FakeClient:
        async def get(self, _url, headers=None):
            if headers is None:
                raise httpx.RequestError("network down")
            return _FakeResponse(status_code=500, text="internal error")

    with pytest.raises(httpx.RequestError):
        asyncio.run(
            get_httpx_module._get_with_retry(
                client=FakeClient(),
                url="https://example.com/rss",
            )
        )


def test_get_with_retry_accepts_custom_status_code_without_retry() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get(self, _url, headers=None):
            self.calls += 1
            return _FakeResponse(status_code=403, text="blocked")

    client = FakeClient()
    response = asyncio.run(
        get_httpx_module._get_with_retry(
            client=client,
            url="https://example.com/rss",
            allowed_status_codes=(403,),
        )
    )

    assert response.status_code == 403
    assert client.calls == 1
