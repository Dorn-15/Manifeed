from __future__ import annotations

import app.services.migration_service as migration_service_module
from app.errors import DBManagerError


def test_run_db_migrations_calls_upgrade(monkeypatch) -> None:
    calls: list[str] = []

    class DummyConfig:
        pass

    def fake_build_alembic_config():
        return DummyConfig()

    def fake_upgrade(config, revision):
        calls.append(revision)
        assert isinstance(config, DummyConfig)

    monkeypatch.setattr(migration_service_module, "_build_alembic_config", fake_build_alembic_config)
    monkeypatch.setattr(migration_service_module.command, "upgrade", fake_upgrade)

    migration_service_module.run_db_migrations(max_attempts=1)

    assert calls == ["head"]


def test_run_db_migrations_retries_then_succeeds(monkeypatch) -> None:
    attempts: list[int] = []
    sleep_calls: list[float] = []

    def fake_build_alembic_config():
        return object()

    def fake_upgrade(config, revision):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("database unavailable")

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(migration_service_module, "_build_alembic_config", fake_build_alembic_config)
    monkeypatch.setattr(migration_service_module.command, "upgrade", fake_upgrade)
    monkeypatch.setattr(migration_service_module.time, "sleep", fake_sleep)

    migration_service_module.run_db_migrations(max_attempts=2, retry_delay_seconds=0.5)

    assert len(attempts) == 2
    assert sleep_calls == [0.5]


def test_run_db_migrations_raises_after_last_attempt(monkeypatch) -> None:
    attempts: list[int] = []

    def fake_build_alembic_config():
        return object()

    def fake_upgrade(config, revision):
        attempts.append(1)
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(migration_service_module, "_build_alembic_config", fake_build_alembic_config)
    monkeypatch.setattr(migration_service_module.command, "upgrade", fake_upgrade)

    try:
        migration_service_module.run_db_migrations(max_attempts=2, retry_delay_seconds=0.0)
    except DBManagerError as exception:
        assert "Unable to run database migrations after 2 attempts" in str(exception)
    else:
        raise AssertionError("run_db_migrations should fail when every attempt fails")

    assert len(attempts) == 2


def test_run_db_migrations_rejects_non_positive_attempts() -> None:
    try:
        migration_service_module.run_db_migrations(max_attempts=0)
    except DBManagerError as exception:
        assert "max_attempts must be greater than zero" in str(exception)
    else:
        raise AssertionError("Expected DBManagerError for non-positive max_attempts")
