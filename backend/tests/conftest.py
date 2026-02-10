from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import get_db_session
from main import app


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
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
