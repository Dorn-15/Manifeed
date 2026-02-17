from collections.abc import Generator
from unittest.mock import Mock

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from database import get_db_session
from main import app


class SyncASGITestClient:
    def __init__(self, asgi_app) -> None:
        self._app = asgi_app
        self._base_url = "http://testserver"

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def _request() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self._base_url,
            ) as async_client:
                return await async_client.request(method, url, **kwargs)

        return anyio.run(_request)

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)


@pytest.fixture
def mock_db_session() -> Mock:
    return Mock(spec=Session)


@pytest.fixture(autouse=True)
def override_db_session(mock_db_session: Mock) -> Generator[None, None, None]:
    def _override_db_session() -> Generator[Mock, None, None]:
        yield mock_db_session

    app.dependency_overrides[get_db_session] = _override_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Generator[SyncASGITestClient, None, None]:
    yield SyncASGITestClient(app)
