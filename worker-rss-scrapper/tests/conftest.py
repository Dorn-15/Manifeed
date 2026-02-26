from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


@pytest.fixture(autouse=True)
def reset_worker_auth_cache() -> None:
    worker_auth_service_module = importlib.import_module("app.services.worker_auth_service")
    worker_auth_service_module._cached_token = None
    worker_auth_service_module._cached_expires_at = None


@pytest.fixture(autouse=True)
def reset_queue_client_cache() -> None:
    queue_module = importlib.import_module("app.clients.queue.redis_queue_client")
    queue_module._redis_client = None
