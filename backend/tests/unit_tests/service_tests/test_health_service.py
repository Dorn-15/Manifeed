from unittest.mock import Mock

from sqlalchemy.orm import Session

import app.services.health.health_service as health_service_module


def test_get_health_status_returns_ok_when_database_is_reachable(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(health_service_module, "check_db_connection", lambda _db: True)

    result = health_service_module.get_health_status(db)

    assert result.status == "ok"
    assert result.database == "ok"


def test_get_health_status_returns_degraded_when_database_is_unreachable(monkeypatch) -> None:
    db = Mock(spec=Session)
    monkeypatch.setattr(health_service_module, "check_db_connection", lambda _db: False)

    result = health_service_module.get_health_status(db)

    assert result.status == "degraded"
    assert result.database == "unavailable"
