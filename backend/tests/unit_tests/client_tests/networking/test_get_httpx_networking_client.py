import asyncio

import httpx

from app.clients.networking.get_httpx_networking_cli import get_httpx_config


def test_get_httpx_returns_configured_async_client() -> None:
    async def run_assertions() -> None:
        async with get_httpx_config(
            timeout=3.5,
            follow_redirects=False,
            headers={"X-Test": "1"},
        ) as client:
            assert isinstance(client, httpx.AsyncClient)
            assert client.follow_redirects is False
            assert client.timeout.connect == 3.5
            assert client.timeout.read == 3.5
            assert client.headers["X-Test"] == "1"

    asyncio.run(run_assertions())
